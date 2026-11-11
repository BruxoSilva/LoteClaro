import io
import sqlite3
from decimal import Decimal
from pathlib import Path
import pytest
from pypdf import PdfReader
from app import create_app
from app.db import connect, detail
from app.domain import calculate, cost, amount
from app.report import build_pdf

@pytest.fixture
def system(tmp_path):
    app=create_app(dict(TESTING=True,DB_PATH=tmp_path/'test.db',REPORT_DIR=tmp_path/'reports',BACKUP_DIR=tmp_path/'backups'))
    client=app.test_client()
    client.get('/')
    def post(path, data=None):
        with client.session_transaction() as s: token=s['csrf']
        return client.post(path,data={'csrf':token,**(data or {})})
    return app,client,post

def new_lot(post):
    response=post('/lote/novo',dict(farm='Granja Teste',withdrawal='03/11/2026',heads='10',entry='100,000',paid='95,000',cost='5,20'))
    assert response.status_code==302
    return 1

def sale(post,weight='80',price='8',path='/lote/1/vendas/novo',**extra):
    return post(path,dict(date='03/11/2026',weight=weight,price=price,new_client='Cliente Teste',**extra))

def snapshot(app):
    db=connect(app.config['DB_PATH'])
    try:
        lot,sales,expenses=detail(db,1)
        return dict(lot),calculate(lot,sales,expenses)
    finally: db.close()

def test_calculations():
    lot=dict(entry_g=100000,paid_g=95000,cost_cents=520,status='aberto')
    sales=[dict(weight_g=30000,price_cents=800),dict(weight_g=50000,price_cents=800)]
    c=calculate(lot,sales,[dict(value_cents=1000)])
    assert c['sold_g']==80000
    assert c['remaining_g']==20000
    assert c['loss_g']==0
    assert c['entry_cost']==52000 and c['paid_cost']==49400
    assert c['revenue']==64000 and c['gross']==14600
    assert c['net']==13600 and c['margin']==Decimal('21.25')
    closed=calculate(lot,sales,[dict(value_cents=1000)],closing=True)
    assert closed['loss_g']==20000 and closed['loss_cents']==10400
    assert closed['remaining_g']==0 and closed['net']==3200 and closed['margin']==Decimal('5.00')

def test_excess_not_double_counted():
    c=calculate(dict(entry_g=100000,paid_g=95000,cost_cents=520,status='finalizado'),[dict(weight_g=110000,price_cents=800)],[])
    assert c['excess_g']==10000 and c['excess_cents']==5200
    assert c['remaining_g']==0 and c['loss_cents']==0
    assert c['revenue']==88000 and c['net']==38600

def test_zero_revenue_and_conciliation():
    lot=dict(entry_g=1000,paid_g=1000,cost_cents=100,status='aberto')
    assert calculate(lot,[],[])['margin']==0
    c=calculate(lot,[dict(weight_g=1000,price_cents=0)],[])
    assert c['difference_g']==0 and c['loss_g']==0 and c['excess_g']==0

def test_rounding():
    assert cost(1005,100)==101
    assert cost(1,500)==1
    assert amount('1,234',1000)==1234

@pytest.mark.parametrize('bad',['NaN','Infinity','-1','1e3','1.000,00','0.0001','',None])
def test_invalid_amounts(bad):
    with pytest.raises(ValueError): amount(bad,1000)

def test_sale_crud_stock_and_persistence(system):
    app,client,post=system
    new_lot(post)
    assert sale(post).status_code==302
    assert snapshot(app)[1]['remaining_g']==20000
    assert sale(post,'60',path='/lote/1/vendas/1/editar',confirm='sim').status_code==302
    assert snapshot(app)[1]['remaining_g']==40000
    assert post('/lote/1/vendas/1/excluir').status_code==400
    assert post('/lote/1/vendas/1/excluir',{'confirm':'sim'}).status_code==302
    assert snapshot(app)[1]['remaining_g']==100000
    app2=create_app(dict(TESTING=True,DB_PATH=app.config['DB_PATH'],REPORT_DIR=app.config['REPORT_DIR'],BACKUP_DIR=app.config['BACKUP_DIR']))
    assert snapshot(app2)[0]['farm']=='Granja Teste'
    assert snapshot(app2)[1]['sold_g']==0

def test_closing_lock_reopen_pdf(system):
    app,client,post=system
    new_lot(post); sale(post)
    assert post('/lote/1/despesas/novo',dict(date='03/11/2026',description='Frete',value='10')).status_code==302
    revision=str(snapshot(app)[0]['revision'])
    assert post('/lote/1/fechar',dict(confirm='sim',physical='sim',revision=revision)).status_code==400
    assert post('/lote/1/fechar',dict(confirm='sim',physical='nao',revision='0')).status_code==400
    assert post('/lote/1/fechar',dict(confirm='sim',physical='nao',revision=revision)).status_code==302
    lot,c=snapshot(app)
    assert lot['status']=='finalizado' and c['net']==3200
    pdf=Path(app.config['REPORT_DIR'])/lot['pdf_name']
    text=' '.join(p.extract_text() for p in PdfReader(pdf).pages)
    for term in ['DEMONSTRATIVO DE FECHAMENTO','Granja Teste','Cliente Teste','Frete','32,00','Gerado em']:
        assert term in text
    assert client.get('/lote/1/pdf').data.startswith(b'%PDF')
    assert sale(post).status_code==400
    assert post('/lote/1/vendas/1/excluir',dict(confirm='sim')).status_code==400
    assert client.get('/lote/1/editar').status_code==400
    assert post('/lote/1/despesas/novo',dict(date='03/11/2026',description='Frete',value='10')).status_code==400
    assert post('/lote/1/reabrir',dict(confirm='sim')).status_code==302
    assert snapshot(app)[1]['loss_g']==0
    assert pdf.exists()
    assert sale(post,'20').status_code==302

def test_backup_restore(system):
    app,client,post=system
    new_lot(post); sale(post)
    backup=post('/backup')
    assert backup.status_code==200 and backup.data.startswith(b'SQLite format 3')
    sale(post,'10')
    response=post('/restaurar',dict(confirm='sim',backup=(io.BytesIO(backup.data),'backup.db')))
    assert response.status_code==302
    assert snapshot(app)[1]['sold_g']==80000
    assert list(Path(app.config['BACKUP_DIR']).glob('Antes_da_restauracao*.db'))
    assert sale(post).status_code==400  # stale form after restoring
    client.get('/')
    assert post('/restaurar',dict(confirm='sim',backup=(io.BytesIO(b'bad'),'bad.db'))).status_code==400
    assert snapshot(app)[1]['sold_g']==80000

def test_all_pages_and_validation(system):
    app,client,post=system
    new_lot(post); sale(post)
    for url in ['/','/lotes','/clientes','/vendas','/despesas','/estoque','/historico','/backup','/lote/novo','/lote/1','/lote/1/editar','/lote/1/vendas/novo','/lote/1/despesas/novo','/lote/1/fechar','/lote/1/vendas/1/editar','/lote/1/vendas/1/excluir']:
        assert client.get(url).status_code==200,url
    assert client.post('/clientes',data={'name':'Sem token'}).status_code==400
    assert post('/clientes',dict(name='')).status_code==400
    assert post('/lote/1/despesas/novo',dict(date='31/02/2026',description='Frete',value='10')).status_code==400
    assert client.get('/',headers={'Host':'evil.example'}).status_code==400

def test_pdf_long_tables(tmp_path):
    lot=dict(id=1,farm='Granja de conferência',withdrawal='2026-11-03',heads=20,entry_g=200000,paid_g=190000,cost_cents=520,status='finalizado',created_at='2026-11-03T10:00:00-03:00',closed_at='2026-11-03T12:00:00-03:00')
    sales=[dict(date='2026-11-03',client_name=f'Cliente {i:03d} com nome extenso',weight_g=1000,price_cents=800,note='Observação de conferência '+('texto longo '*30 if i==5 else '')) for i in range(120)]
    expenses=[dict(date='2026-11-03',description=f'Despesa {i:03d}',value_cents=100) for i in range(60)]
    result=build_pdf(lot,sales,expenses,calculate(lot,sales,expenses),lot['closed_at'])
    reader=PdfReader(io.BytesIO(result))
    text=' '.join(p.extract_text() for p in reader.pages)
    assert len(reader.pages)>3
    for i in range(120): assert f'Cliente {i:03d}' in text
    for i in range(60): assert f'Despesa {i:03d}' in text
    assert text.count('Preço / kg')>1
    assert text.count('Página ')==len(reader.pages)

def test_pdf_failure_rolls_back_closing(system,monkeypatch):
    app,client,post=system
    new_lot(post)
    def fail(*args): raise OSError('disco cheio')
    monkeypatch.setattr('app.web.build_pdf',fail)
    with pytest.raises(OSError): post('/lote/1/fechar',dict(confirm='sim',physical='nao',revision='0'))
    assert snapshot(app)[0]['status']=='aberto'

def test_database_lock_and_foreign_keys(system):
    app,client,post=system
    new_lot(post); sale(post,'100')
    post('/lote/1/fechar',dict(confirm='sim',revision='1'))
    db=connect(app.config['DB_PATH'])
    try:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute('DELETE FROM vendas WHERE id=1')
        db.rollback()
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO despesas(lot_id,date,description,value_cents) VALUES(999,'2026-11-03','x',1)")
    finally: db.close()

def test_expense_crud_recalculates(system):
    app,client,post=system
    new_lot(post)
    post('/lote/1/despesas/novo',dict(date='03/11/2026',description='Frete',value='10'))
    assert snapshot(app)[1]['expenses']==1000
    post('/lote/1/despesas/1/editar',dict(date='03/11/2026',description='Frete',value='12,50',confirm='sim'))
    assert snapshot(app)[1]['expenses']==1250
    post('/lote/1/despesas/1/excluir',dict(confirm='sim'))
    assert snapshot(app)[1]['expenses']==0

def test_report_invalidated_on_changes(system):
    app,client,post=system
    new_lot(post)
    assert post('/lote/1/pdf').status_code==302
    first=snapshot(app)[0]['pdf_name']
    assert first
    sale(post)
    assert snapshot(app)[0]['pdf_name'] is None
    assert (Path(app.config['REPORT_DIR'])/first).exists()
    assert client.get('/lote/1/pdf').status_code==400

def test_old_csrf_form_rejected_after_restore_and_refresh(system):
    app,client,post=system
    new_lot(post)
    with client.session_transaction() as session: old=session['csrf']
    data=post('/backup').data
    assert post('/restaurar',dict(confirm='sim',backup=(io.BytesIO(data),'backup.db'))).status_code==302
    client.get('/')
    assert client.post('/clientes',data=dict(csrf=old,name='Formulario antigo')).status_code==400

def test_cross_lot_item_cannot_be_modified(system):
    app,client,post=system
    new_lot(post); sale(post)
    new_lot(post)
    assert sale(post,path='/lote/2/vendas/1/editar',confirm='sim').status_code==404
    assert post('/lote/2/vendas/1/excluir',dict(confirm='sim')).status_code==404
    assert snapshot(app)[1]['sold_g']==80000
