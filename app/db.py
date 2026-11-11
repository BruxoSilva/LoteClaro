import sqlite3
from datetime import datetime
from pathlib import Path

SCHEMA = '''
CREATE TABLE IF NOT EXISTS lotes (
 id INTEGER PRIMARY KEY AUTOINCREMENT, farm TEXT NOT NULL,
 withdrawal TEXT NOT NULL, heads INTEGER NOT NULL CHECK(heads>0),
 entry_g INTEGER NOT NULL CHECK(entry_g>0), paid_g INTEGER NOT NULL CHECK(paid_g>0),
 cost_cents INTEGER NOT NULL CHECK(cost_cents>=0),
 status TEXT NOT NULL DEFAULT 'aberto' CHECK(status IN ('aberto','finalizado')),
 created_at TEXT NOT NULL, closed_at TEXT, revision INTEGER NOT NULL DEFAULT 0,
 pdf_name TEXT, CHECK((status='aberto' AND closed_at IS NULL) OR (status='finalizado' AND closed_at IS NOT NULL))
);
CREATE TABLE IF NOT EXISTS clientes (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS vendas (
 id INTEGER PRIMARY KEY AUTOINCREMENT, lot_id INTEGER NOT NULL REFERENCES lotes(id),
 client_id INTEGER NOT NULL REFERENCES clientes(id), client_name TEXT NOT NULL,
 date TEXT NOT NULL, weight_g INTEGER NOT NULL CHECK(weight_g>0),
 price_cents INTEGER NOT NULL CHECK(price_cents>=0), note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS despesas (
 id INTEGER PRIMARY KEY AUTOINCREMENT, lot_id INTEGER NOT NULL REFERENCES lotes(id),
 description TEXT NOT NULL, date TEXT NOT NULL, value_cents INTEGER NOT NULL CHECK(value_cents>0)
);
CREATE INDEX IF NOT EXISTS sales_lot ON vendas(lot_id);
CREATE INDEX IF NOT EXISTS expenses_lot ON despesas(lot_id);
CREATE TABLE IF NOT EXISTS percas (
 id INTEGER PRIMARY KEY AUTOINCREMENT, lot_id INTEGER NOT NULL REFERENCES lotes(id),
 date TEXT NOT NULL, weight_g INTEGER NOT NULL CHECK(weight_g>0), note TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS percas_lot ON percas(lot_id);
PRAGMA user_version=2;
'''

def connect(path):
    db = sqlite3.connect(str(path), timeout=20)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    return db

def initialize(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as db:
        version = db.execute('PRAGMA user_version').fetchone()[0]
        if version > 2:
            raise ValueError('Banco de versão mais nova. Atualize o sistema antes de abrir.')
        if version == 1:
            backup_dir = Path(path).parent.parent/'backups'
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_path = backup_dir/f'Antes_migracao_percas_{datetime.now():%Y%m%d_%H%M%S_%f}.db'
            with sqlite3.connect(backup_path) as destination:
                db.backup(destination)
            destination.close()
        db.executescript(SCHEMA)
        for table in ('vendas', 'despesas', 'percas'):
            for action in ('INSERT', 'UPDATE', 'DELETE'):
                ref = 'NEW' if action == 'INSERT' else 'OLD'
                db.execute(f'''CREATE TRIGGER IF NOT EXISTS lock_{table}_{action}
                    BEFORE {action} ON {table} WHEN (SELECT status FROM lotes WHERE id={ref}.lot_id)='finalizado'
                    BEGIN SELECT RAISE(ABORT, 'Lote finalizado: reabra antes de alterar.'); END''')
    db.close()
    from .payments import migrate_payments
    migrate_payments(path)

def detail(db, lot_id):
    lot = db.execute('SELECT * FROM lotes WHERE id=?', (lot_id,)).fetchone()
    if not lot:
        raise ValueError('Lote não encontrado.')
    lot = dict(lot)
    lot['percas'] = db.execute('SELECT * FROM percas WHERE lot_id=? ORDER BY date,id', (lot_id,)).fetchall()
    sales = db.execute('SELECT * FROM vendas WHERE lot_id=? ORDER BY date,id', (lot_id,)).fetchall()
    expenses = db.execute('SELECT * FROM despesas WHERE lot_id=? ORDER BY date,id', (lot_id,)).fetchall()
    return lot, sales, expenses

def editable(db, lot_id):
    lot = detail(db, lot_id)[0]
    if lot['status'] != 'aberto':
        raise ValueError('Lote finalizado. Use a ação de reabertura antes de alterar.')
    return lot
