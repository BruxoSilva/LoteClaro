import io
import sqlite3
from pathlib import Path
from decimal import Decimal
import pytest
from pypdf import PdfReader
from app.db import connect, detail, initialize
from app.domain import calculate
from test_system import system, new_lot, sale, snapshot

def perca(post, weight='5,125', note='Aves descartadas', path='/lote/1/percas/novo', **extra):
    return post(path,dict(date='03/11/2026',weight=weight,note=note,**extra))

def test_percas_financial_effect_and_stock_separation(system):
    app,client,post=system
    new_lot(post); sale(post)
    assert perca(post,'5').status_code==302
    lot,c=snapshot(app)
    assert lot['paid_g']==95000 and c['paid_net_g']==90000
    assert c['percas_g']==5000 and c['percas_credit']==2600
    assert c['paid_cost']==46800 and c['gross']==17200 and c['net']==17200
    assert c['margin']==Decimal('26.88')
    assert c['entry_cost']==52000 and c['remaining_g']==20000 and c['revenue']==64000
    with connect(app.config['DB_PATH']) as db:
        closed=calculate(*detail(db,1),closing=True)
    assert closed['loss_cents']==10400 and closed['net']==6800

def test_perca_crud_persistence_and_confirmations(system):
    app,client,post=system
    new_lot(post)
    assert perca(post).status_code==302
    assert snapshot(app)[1]['paid_net_g']==89875
    for url in ['/percas','/lote/1/percas/novo','/lote/1/percas/1/editar','/lote/1/percas/1/excluir','/lote/1','/lote/1/fechar']:
        assert client.get(url).status_code==200
    assert perca(post,'3',path='/lote/1/percas/1/editar').status_code==400
    assert perca(post,'3',path='/lote/1/percas/1/editar',confirm='sim').status_code==302
    assert snapshot(app)[1]['paid_net_g']==92000
    assert post('/lote/1/percas/1/excluir').status_code==400
    assert post('/lote/1/percas/1/excluir',dict(confirm='sim')).status_code==302
    assert snapshot(app)[1]['paid_net_g']==95000

@pytest.mark.parametrize('weight,note',[('96','Acima do limite'),('0','Zero'),('-1','Negativo'),('1,1234','Precisão'),('1','')])
def test_perca_invalid(system,weight,note):
    app,client,post=system
    new_lot(post)
    assert perca(post,weight,note).status_code==400
    assert snapshot(app)[1]['percas_g']==0

def test_sum_limit_and_edit_paid_weight(system):
    app,client,post=system
    new_lot(post)
    assert perca(post,'90').status_code==302
    assert perca(post,'6').status_code==400
    assert perca(post,'5').status_code==302
    assert snapshot(app)[1]['paid_cost']==0
    assert post('/lote/1/editar',dict(confirm='sim',farm='Teste',withdrawal='03/11/2026',heads='10',entry='100',paid='94',cost='5,20')).status_code==400
    assert snapshot(app)[0]['paid_g']==95000

def test_inline_entry_and_sale_transaction(system):
    app,client,post=system
    assert post('/lote/novo',dict(farm='Granja',withdrawal='03/11/2026',heads='10',entry='100',paid='95',cost='5,20',perca_weight='2',perca_note='Descarte na entrada')).status_code==302
    assert snapshot(app)[1]['paid_net_g']==93000
    assert sale(post,perca_weight='3',perca_note='Descarte na venda').status_code==302
    assert snapshot(app)[1]['paid_net_g']==90000
    before=snapshot(app)
    assert sale(post,perca_weight='1',perca_note='').status_code==400
    assert snapshot(app)[1]==before[1]  # sale, new customer and perca roll back together
    with connect(app.config['DB_PATH']) as db:
        assert db.execute('SELECT COUNT(*) FROM clientes').fetchone()[0]==1

def test_percas_pdf_and_finalized_lock(system):
    app,client,post=system
    new_lot(post); sale(post,'100'); perca(post,'5','Aves descartadas no transporte')
    assert post('/lote/1/fechar',dict(confirm='sim',revision='2')).status_code==302
    response=client.get('/lote/1/pdf')
    text=' '.join(p.extract_text() for p in PdfReader(io.BytesIO(response.data)).pages)
    for value in ['PERCAS','Aves descartadas no transporte','Peso pago original','Peso pago líquido','90,000 kg','468,00']:
        assert value in text
    assert perca(post,'1').status_code==400
    assert perca(post,'1',path='/lote/1/percas/1/editar',confirm='sim').status_code==400
    assert post('/lote/1/percas/1/excluir',dict(confirm='sim')).status_code==400
    with connect(app.config['DB_PATH']) as db:
        with pytest.raises(sqlite3.IntegrityError): db.execute('DELETE FROM percas WHERE id=1')
    assert post('/lote/1/reabrir',dict(confirm='sim')).status_code==302
    assert snapshot(app)[1]['percas_g']==5000

def test_percas_backup_restore(system):
    app,client,post=system
    new_lot(post); perca(post,'5')
    data=post('/backup').data
    perca(post,'2')
    assert post('/restaurar',dict(confirm='sim',backup=(io.BytesIO(data),'backup.db'))).status_code==302
    assert snapshot(app)[1]['percas_g']==5000

def old_database(path):
    legacy=Path(path).with_name('v1_'+Path(path).name)
    with connect(path) as source, connect(legacy) as target:
        objects=source.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY CASE type WHEN 'table' THEN 0 WHEN 'index' THEN 1 ELSE 2 END").fetchall()
        for kind,name,table,sql in objects:
            if table not in ('percas','pagamentos','cheques'):
                target.execute(sql)
        for table in ('lotes','clientes','vendas','despesas'):
            rows=source.execute('SELECT * FROM '+table).fetchall()
            for row in rows:
                target.execute('INSERT INTO '+table+' VALUES('+','.join('?' for _ in row)+')',tuple(row))
        target.execute('PRAGMA user_version=1')
    return legacy

def test_migration_preserves_existing_records_and_backup(system):
    app,client,post=system
    new_lot(post); sale(post)
    app.config['DB_PATH']=old_database(app.config['DB_PATH'])
    before=Path(app.config['DB_PATH']).read_bytes()
    initialize(app.config['DB_PATH'])
    assert snapshot(app)[1]['percas_g']==0
    assert snapshot(app)[1]['revenue']==64000
    with connect(app.config['DB_PATH']) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0]==2
    backups=list((Path(app.config['DB_PATH']).parent.parent/'backups').glob('Antes_migracao_percas*.db'))
    assert backups

def test_restore_v1_backup_migrates_safely(system,tmp_path):
    app,client,post=system
    new_lot(post); sale(post)
    legacy=tmp_path/'legacy.db'
    legacy.write_bytes(post('/backup').data)
    legacy=old_database(legacy)
    perca(post,'5')
    assert post('/restaurar',dict(confirm='sim',backup=(io.BytesIO(legacy.read_bytes()),'legacy.db'))).status_code==302
    assert snapshot(app)[1]['percas_g']==0
    assert snapshot(app)[1]['revenue']==64000
