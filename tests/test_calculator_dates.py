import pytest
from app.db import connect
from app.domain import date_value
from test_system import system

@pytest.mark.parametrize('value,expected',[('2026-11-03','2026-11-03'),('03/11/2026','2026-11-03'),('2028-02-29','2028-02-29')])
def test_calendar_dates(value,expected):
    assert date_value(value)==expected

@pytest.mark.parametrize('value',['2026-02-29','2026-13-01','2026-04-31','',None])
def test_calendar_rejects_invalid(value):
    with pytest.raises(ValueError): date_value(value)

def test_all_forms_use_calendar_and_preserve_edit_values(system):
    app,client,post=system
    result=post('/lote/novo',dict(farm='Teste calendário',withdrawal='2026-11-03',heads='10',entry='100',paid='95',cost='5,20'))
    assert result.status_code==302
    assert post('/lote/1/vendas/novo',dict(date='2026-11-04',weight='10',price='8',new_client='Teste')).status_code==302
    assert post('/lote/1/despesas/novo',dict(date='2026-11-05',description='Frete',value='10')).status_code==302
    assert post('/lote/1/percas/novo',dict(date='2026-11-06',weight='1',note='Transporte')).status_code==302
    for path in ['/lote/novo','/lote/1/editar','/lote/1/vendas/novo','/lote/1/despesas/novo','/lote/1/percas/novo','/calculadora']:
        response=client.get(path)
        assert response.status_code==200 and b'type="date"' in response.data
    for path,value in [('/lote/1/editar','2026-11-03'),('/lote/1/vendas/1/editar','2026-11-04'),('/lote/1/despesas/1/editar','2026-11-05'),('/lote/1/percas/1/editar','2026-11-06')]:
        assert f'value="{value}"'.encode() in client.get(path).data
    assert '04/11/2026' in client.get('/lote/1').get_data(as_text=True)

def test_calculator_has_no_database_or_file_mutations(system):
    app,client,post=system
    with connect(app.config['DB_PATH']) as db:
        before=list(db.iterdump())
    assert client.get('/calculadora').status_code==200
    assert post('/calculadora',dict(amount='100')).status_code==405
    with connect(app.config['DB_PATH']) as db:
        assert list(db.iterdump())==before
    assert not list(app.config['REPORT_DIR'].iterdir())
