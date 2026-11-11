import json
import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime
from .domain import cost, amount, date_value, required

PAYMENT_SCHEMA = [
'''CREATE TABLE IF NOT EXISTS pagamentos (
 id INTEGER PRIMARY KEY AUTOINCREMENT, lot_id INTEGER NOT NULL REFERENCES lotes(id),
 request_key TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL,
 cash_cents INTEGER NOT NULL CHECK(cash_cents>=0), checks_cents INTEGER NOT NULL CHECK(checks_cents>=0),
 total_cents INTEGER NOT NULL CHECK(total_cents>0), balance_cents INTEGER NOT NULL,
 snapshot TEXT NOT NULL, pdf_name TEXT)''',
'''CREATE TABLE IF NOT EXISTS cheques (
 id INTEGER PRIMARY KEY AUTOINCREMENT, payment_id INTEGER NOT NULL REFERENCES pagamentos(id),
 value_cents INTEGER NOT NULL CHECK(value_cents>0), compensation_date TEXT NOT NULL,
 number TEXT NOT NULL, bank TEXT NOT NULL, note TEXT NOT NULL)''',
'CREATE INDEX IF NOT EXISTS payments_lot ON pagamentos(lot_id)',
'CREATE INDEX IF NOT EXISTS checks_payment ON cheques(payment_id)']

def inventory(db):
    counts, hashes = {}, {}
    for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        name=row[0]
        records=[tuple(r) for r in db.execute('SELECT * FROM "'+name.replace('"','""')+'" ORDER BY rowid')]
        counts[name]=len(records)
        hashes[name]=hashlib.sha256(repr(records).encode()).hexdigest()
    return counts,hashes

def migrate_payments(path):
    db=sqlite3.connect(path,timeout=20)
    try:
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='pagamentos'").fetchone(): return
        folder=Path(path).parent.parent/'backups';folder.mkdir(parents=True,exist_ok=True)
        target=folder/f'Antes_pagamentos_{datetime.now():%Y%m%d_%H%M%S_%f}.db'
        dest=sqlite3.connect(target)
        db.backup(dest);dest.close()
        verified=sqlite3.connect(target)
        try:
            if verified.execute('PRAGMA integrity_check').fetchone()[0]!='ok': raise ValueError('Backup inválido; migração cancelada.')
            before,hashes=inventory(verified)
        finally: verified.close()
        db.execute('BEGIN IMMEDIATE')
        if inventory(db)!=(before,hashes): raise ValueError('Dados alterados durante o backup; reinicie para tentar novamente.')
        for statement in PAYMENT_SCHEMA: db.execute(statement)
        after,after_hashes=inventory(db)
        if any(after.get(t)!=n or after_hashes.get(t)!=hashes[t] for t,n in before.items()):
            raise ValueError('Verificação de preservação falhou; migração revertida.')
        target.with_suffix('.json').write_text(json.dumps(dict(database=str(Path(path).resolve()),backup_verified=True,before=before,after=after,hashes_preserved=True),indent=2),encoding='utf-8')
        db.commit()
    except Exception:
        db.rollback();raise
    finally: db.close()

def purchase(lot):
    losses=[]; cumulative=0; allocated=0
    for p in lot['percas']:
        cumulative+=p['weight_g']
        discount=cost(cumulative,lot['cost_cents'])-allocated
        allocated+=discount
        losses.append(dict(date=p['date'],description=p['note'] or 'Perda anteriormente registrada',weight_g=p['weight_g'],discount=discount))
    if cumulative>lot['paid_g']: raise ValueError('As perdas ultrapassam o peso original pago.')
    gross=cost(lot['paid_g'],lot['cost_cents'])
    return dict(lot_id=lot['id'],farm=lot['farm'],withdrawal=lot['withdrawal'],heads=lot['heads'],
        original_g=lot['paid_g'],price_cents=lot['cost_cents'],gross=gross,losses=losses,
        loss_g=cumulative,discount=allocated,net_g=lot['paid_g']-cumulative,net=gross-allocated)

def state(balance):
    return 'Ainda devido ao fornecedor' if balance>0 else 'Pagamento quitado' if balance==0 else 'Crédito/haver'

def parse_payment(form):
    cash=amount(form.get('cash') or '0',100,'Valor em dinheiro')
    values=form.getlist('check_value');dates=form.getlist('check_date')
    numbers=form.getlist('check_number');banks=form.getlist('check_bank');notes=form.getlist('check_note')
    if len(values)>100 or any(len(x)!=len(values) for x in (dates,numbers,banks,notes)):
        raise ValueError('Lista de cheques inválida. Limite de 100 cheques por pagamento.')
    def optional(s,limit):
        return required(s,'Observação/identificação',limit) if s.strip() else ''
    checks=[dict(value_cents=amount(v,100,'Valor do cheque',True),compensation_date=date_value(d),number=optional(n,80),bank=optional(b,120),note=optional(o,300)) for v,d,n,b,o in zip(values,dates,numbers,banks,notes)]
    note=optional(form.get('payment_note',''),2000)
    total=cash+sum(c['value_cents'] for c in checks)
    if total<=0: raise ValueError('Informe um pagamento em dinheiro ou cheque maior que zero.')
    return cash,checks,note,total
