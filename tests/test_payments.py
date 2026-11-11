import io,json,re,sqlite3
from pathlib import Path
import pytest
from pypdf import PdfReader
from PIL import Image
from app.payment_pdf import build_payment_pdf
from app.db import connect,detail
from app.payments import purchase,inventory,migrate_payments
from test_system import system,new_lot,sale

def key(client):
    html=client.get('/lote/1').get_data(as_text=True)
    return re.search(r'name="payment_key" value="([^"]+)"',html).group(1)

def pay(client,post,**data):
    return post('/lote/1/pagamento',{'payment_key':key(client),'confirm':'sim','cash':'0',**data})

def rows(app):
    with connect(app.config['DB_PATH']) as db:
        return [dict(x) for x in db.execute('SELECT * FROM pagamentos ORDER BY id')]

def test_purchase_rounding_and_loss_limit():
    lot=dict(id=1,farm='Granja',withdrawal='2026-11-03',heads=1,paid_g=10,cost_cents=50,percas=[dict(date='2026-11-03',note='',weight_g=1)])
    c=purchase(lot)
    assert c['gross']==1 and c['discount']==0 and c['net']==1
    assert c['losses'][0]['description']=='Perda anteriormente registrada'
    lot['percas'][0]['weight_g']=11
    with pytest.raises(ValueError):purchase(lot)

def test_cash_partial_duplicate_snapshot_pdf(system):
    app,client,post=system;new_lot(post);sale(post)
    token=key(client)
    data=dict(payment_key=token,confirm='sim',cash='100')
    assert post('/lote/1/pagamento',data).status_code==302
    assert post('/lote/1/pagamento',data).status_code==302
    assert len(rows(app))==1
    row=rows(app)[0];assert row['balance_cents']==39400
    before=row['snapshot']
    assert post('/lote/1/editar',dict(confirm='sim',farm='Nova granja',withdrawal='03/11/2026',heads='10',entry='100',paid='90',cost='7')).status_code==302
    response=post('/pagamento/1/pdf')
    assert response.status_code==200
    assert response.mimetype=='image/png'
    image=Image.open(io.BytesIO(response.data));image.verify()
    text=' '.join(p.extract_text() for p in PdfReader(io.BytesIO(build_payment_pdf(json.loads(before),'2026-11-03T12:00:00',single_page=True))).pages)
    assert 'Granja Teste' in text and 'Nova granja' not in text
    for forbidden in ['Cliente Teste','Lucro','Margem','Receita','Peso vendido','Estoque','Valor de venda']:
        assert forbidden not in text
    assert rows(app)[0]['snapshot']==before and len(rows(app))==1
    assert len(list((app.config['REPORT_DIR']/'Pagamentos').glob('*.png')))==2

def test_mixed_checks_multiple_dates_history_credit(system):
    app,client,post=system;new_lot(post)
    assert pay(client,post,**{'cash':'100','check_value':['50','75,50'],'check_date':['2026-12-10','2027-01-15'],'check_number':['001',''],'check_bank':['Banco',''],'check_note':['Pré-datado','']}).status_code==302
    first=rows(app)[0];assert first['total_cents']==22550 and first['checks_cents']==12550 and first['balance_cents']==26850
    assert pay(client,post,**{'cash':'300'}).status_code==400
    assert pay(client,post,**{'cash':'300','confirm_credit':'sim'}).status_code==302
    assert rows(app)[1]['balance_cents']==-3150
    s=json.loads(rows(app)[1]['snapshot']);assert s['previous_total']==22550 and len(s['previous'])==1
    with connect(app.config['DB_PATH']) as db:
        assert [r[0] for r in db.execute('SELECT compensation_date FROM cheques ORDER BY id')]==['2026-12-10','2027-01-15']

def test_cheque_only_quitado(system):
    app,client,post=system;new_lot(post)
    assert pay(client,post,**{'check_value':['494'],'check_date':['2027-01-01'],'check_number':[''],'check_bank':[''],'check_note':['']}).status_code==302
    assert rows(app)[0]['balance_cents']==0

@pytest.mark.parametrize('data',[{'cash':'-1'},{'cash':'0'},{'cash':'1,001'},{'check_value':['10'],'check_date':[''],'check_number':[''],'check_bank':[''],'check_note':['']},{'check_value':['0'],'check_date':['2027-01-01'],'check_number':[''],'check_bank':[''],'check_note':['']},{'check_value':['10'],'check_date':['2027-02-30'],'check_number':[''],'check_bank':[''],'check_note':['']}])
def test_invalid_payments(system,data):
    app,client,post=system;new_lot(post)
    assert pay(client,post,**data).status_code==400
    assert rows(app)==[]

def test_stale_payment_quote(system):
    app,client,post=system;new_lot(post);old=key(client)
    assert pay(client,post,cash='10').status_code==302
    assert post('/lote/1/pagamento',dict(payment_key=old,confirm='sim',cash='20')).status_code==400
    assert len(rows(app))==1

def test_pdf_failure_payment_survives(system,monkeypatch):
    app,client,post=system;new_lot(post)
    import app.web as web
    original=web.build_payment_image
    def failure(*a): raise OSError('PDF indisponível')
    monkeypatch.setattr(web,'build_payment_image',failure)
    assert pay(client,post,cash='10').status_code==302
    assert len(rows(app))==1 and rows(app)[0]['pdf_name'] is None
    monkeypatch.setattr(web,'build_payment_image',original)
    assert post('/pagamento/1/pdf').status_code==200
    assert len(rows(app))==1

def test_preservation_backup_incremental(tmp_path):
    path=tmp_path/'data'/'old.db';path.parent.mkdir()
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE lotes(id INTEGER PRIMARY KEY, note TEXT)')
        db.execute("INSERT INTO lotes VALUES(42,'Observação preservada')")
    with sqlite3.connect(path) as db: before=inventory(db)
    migrate_payments(path)
    with sqlite3.connect(path) as db:
        after=inventory(db);assert db.execute('PRAGMA foreign_key_check').fetchall()==[]
    for table in before[0]:
        assert before[0][table]==after[0][table] and before[1][table]==after[1][table]
    backup=next((tmp_path/'backups').glob('*.db'))
    with sqlite3.connect(backup) as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert inventory(db)==before
    assert json.loads(backup.with_suffix('.json').read_text())['hashes_preserved']

def test_loss_discount_and_payment_backup(system):
    app,client,post=system;new_lot(post)
    post('/lote/1/percas/novo',dict(date='03/11/2026',weight='5',note='Descarte'))
    assert pay(client,post,cash='468').status_code==302
    snapshot=json.loads(rows(app)[0]['snapshot'])
    assert snapshot['gross']==49400 and snapshot['discount']==2600 and snapshot['net']==46800 and snapshot['balance']==0
    data=post('/backup').data
    assert post('/restaurar',dict(confirm='sim',backup=(io.BytesIO(data),'backup.db'))).status_code==302
    assert len(rows(app))==1 and json.loads(rows(app)[0]['snapshot'])==snapshot
