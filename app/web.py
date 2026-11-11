from pathlib import Path
from datetime import datetime
from decimal import Decimal
from contextlib import contextmanager
import os, re, secrets, sqlite3, threading, unicodedata
import json, hashlib
from itsdangerous import URLSafeSerializer, BadSignature
from .payments import purchase, state as payment_state, parse_payment
from .payment_pdf import build_payment_image
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, abort
from .db import connect, initialize, detail, editable
from .domain import amount, required, date_value, calculate, money, kg, number, brdate, metrics, cost
from .report import build_pdf

ROOT = Path(__file__).resolve().parent.parent

def now():
    return datetime.now().astimezone().isoformat(timespec='seconds')

def create_app(config=None):
    app = Flask(__name__, template_folder=str(ROOT/'templates'), static_folder=str(ROOT/'static'))
    app.config.update(DB_PATH=ROOT/'data'/'calculadora.db', REPORT_DIR=ROOT/'Relatorios', BACKUP_DIR=ROOT/'backups',
        SECRET_KEY=secrets.token_hex(32), MAX_CONTENT_LENGTH=100*1024*1024, SESSION_COOKIE_SAMESITE='Strict', SESSION_COOKIE_HTTPONLY=True)
    if config: app.config.update(config)
    for key in ('REPORT_DIR','BACKUP_DIR'):
        Path(app.config[key]).mkdir(parents=True,exist_ok=True)
    initialize(app.config['DB_PATH'])
    lock=threading.RLock()
    epoch={'value':secrets.token_hex(16)}

    @contextmanager
    def database(write=False):
        with lock:
            db=connect(app.config['DB_PATH'])
            try:
                if write: db.execute('BEGIN IMMEDIATE')
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise
            finally: db.close()

    @app.before_request
    def protect():
        if request.host.split(':')[0] not in ('127.0.0.1','localhost','[::1]', *app.config.get('REMOTE_HOSTS', [])):
            abort(400)
        if request.method=='POST':
            if not secrets.compare_digest(session.get('csrf','missing'), request.form.get('csrf','')) or session.get('epoch')!=epoch['value']:
                abort(400,description='Sessão expirada. Atualize a página antes de tentar novamente.')
        else:
            if session.get('epoch')!=epoch['value']:
                session['csrf']=secrets.token_hex(32)
            session.setdefault('csrf',secrets.token_hex(32))
            session['epoch']=epoch['value']

    @app.after_request
    def headers(response):
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; form-action 'self'; base-uri 'self'"
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Cache-Control']='no-store'
        return response

    @app.context_processor
    def helpers():
        return dict(csrf=session.get('csrf',''),money=money,kg=kg,number=number,brdate=brdate,metrics=metrics,cost=cost,today=datetime.now().strftime('%d/%m/%Y'),decimal_input=lambda v,s: str(Decimal(v)/s).replace('.',','))

    @app.errorhandler(ValueError)
    def invalid(exc):
        return render_template('error.html',message=str(exc)),400

    @app.errorhandler(sqlite3.Error)
    def storage_error(exc):
        app.logger.exception('Erro SQLite')
        return render_template('error.html',message='Não foi possível salvar os dados. Confira os vínculos e tente novamente. Nenhuma alteração desta operação foi aplicada.'),400

    @app.errorhandler(500)
    def failure(exc):
        return render_template('error.html',message='Não foi possível concluir a operação. Verifique espaço em disco e permissões. Consulte o registro no terminal.'),500

    @app.errorhandler(400)
    @app.errorhandler(413)
    def bad_request(exc):
        return render_template('error.html',message=exc.description),exc.code

    def revision(db,lot_id):
        db.execute('UPDATE lotes SET revision=revision+1,pdf_name=NULL WHERE id=?',(lot_id,))

    def confirm():
        if request.form.get('confirm')!='sim':
            raise ValueError('Confirme a operação para continuar.')

    def validate_percas(db, lot_id, weight_g, excluding=None):
        lot = editable(db, lot_id)
        total = sum(p['weight_g'] for p in lot['percas'] if p['id'] != excluding)
        if total + weight_g > lot['paid_g']:
            raise ValueError('O total de PERCAS não pode ultrapassar o peso pago original. Confira os kg informados.')

    def optional_perca(db, lot_id, date):
        weight = request.form.get('perca_weight', '').strip()
        note = request.form.get('perca_note', '').strip()
        if not weight and not note:
            return
        weight_g = amount(weight, 1000, 'PERCAS (kg)', True)
        note = required(note, 'Observação da PERCA', 500)
        validate_percas(db, lot_id, weight_g)
        db.execute('INSERT INTO percas(lot_id,date,weight_g,note) VALUES(?,?,?,?)', (lot_id,date,weight_g,note))

    @app.get('/')
    @app.get('/lotes')
    @app.get('/historico')
    @app.get('/estoque')
    def dashboard():
        history=request.path=='/historico'
        with database() as db:
            lots=db.execute('SELECT * FROM lotes ORDER BY id DESC').fetchall()
            rows=[(l,calculate(*detail(db,l['id']))) for l in lots if not history or l['status']=='finalizado']
        title={'/':'Painel inicial','/lotes':'Lotes','/historico':'Histórico de lotes finalizados','/estoque':'Consulta do estoque'}[request.path]
        return render_template('dashboard.html',title=title,rows=rows,stock=request.path=='/estoque')

    @app.route('/lote/novo',methods=['GET','POST'])
    @app.route('/lote/<int:lot_id>/editar',methods=['GET','POST'])
    def lot_form(lot_id=None):
        with database(request.method=='POST') as db:
            lot=editable(db,lot_id) if lot_id else None
            if request.method=='POST':
                if lot: confirm()
                farm=required(request.form.get('farm'),'Nome da granja')
                withdrawal=date_value(request.form.get('withdrawal'))
                heads=request.form.get('heads','')
                if not heads.isdigit() or not 0<int(heads)<=1000000000: raise ValueError('Cabeças: informe um inteiro maior que zero.')
                values=(farm,withdrawal,int(heads),amount(request.form.get('entry'),1000,'Entrada',True),amount(request.form.get('paid'),1000,'Peso pago',True),amount(request.form.get('cost'),100,'Custo por kg'))
                if lot:
                    if sum(p['weight_g'] for p in lot['percas']) > values[4]:
                        raise ValueError('O peso pago original não pode ser menor que as PERCAS já registradas.')
                    earliest=db.execute('SELECT MIN(date) FROM (SELECT date FROM vendas WHERE lot_id=? UNION ALL SELECT date FROM despesas WHERE lot_id=? UNION ALL SELECT date FROM percas WHERE lot_id=?)',(lot_id,lot_id,lot_id)).fetchone()[0]
                    if earliest and withdrawal>earliest: raise ValueError('A retirada não pode ser posterior aos lançamentos existentes.')
                    db.execute('UPDATE lotes SET farm=?,withdrawal=?,heads=?,entry_g=?,paid_g=?,cost_cents=?,revision=revision+1,pdf_name=NULL WHERE id=?',(*values,lot_id))
                else:
                    lot_id=db.execute('INSERT INTO lotes(farm,withdrawal,heads,entry_g,paid_g,cost_cents,created_at) VALUES(?,?,?,?,?,?,?)',(*values,now())).lastrowid
                    optional_perca(db, lot_id, withdrawal)
                flash('Lote salvo com sucesso.','success')
                return redirect(url_for('lot_detail',lot_id=lot_id))
        return render_template('lot_form.html',lot=lot)

    @app.get('/lote/<int:lot_id>')
    def lot_detail(lot_id):
        with database() as db:
            lot,sales,expenses=detail(db,lot_id)
            buy,payments,quote=payment_context(db,lot)
        key=URLSafeSerializer(app.secret_key,salt='payment').dumps(dict(lot=lot_id,quote=quote,nonce=secrets.token_hex(16)))
        return render_template('detail.html',lot=lot,sales=sales,expenses=expenses,c=calculate(lot,sales,expenses),closing=False,buy=buy,payments=payments,payment_key=key,payment_state=payment_state)

    def payment_context(db,lot):
        buy=purchase(lot)
        payments=[dict(r) for r in db.execute('SELECT id,created_at,cash_cents,checks_cents,total_cents,balance_cents,pdf_name FROM pagamentos WHERE lot_id=? ORDER BY id',(lot['id'],))]
        buy['previous_total']=sum(p['total_cents'] for p in payments)
        buy['balance']=buy['net']-buy['previous_total']
        quote=hashlib.sha256(json.dumps([buy,[(p['id'],p['total_cents']) for p in payments]],sort_keys=True).encode()).hexdigest()
        return buy,payments,quote

    def payment_report(payment_id):
        with database() as db:
            row=db.execute('SELECT * FROM pagamentos WHERE id=?',(payment_id,)).fetchone()
            if not row: abort(404)
            snapshot=json.loads(row['snapshot'])
        folder=Path(app.config['REPORT_DIR'])/'Pagamentos';folder.mkdir(parents=True,exist_ok=True)
        name=f"Pagamento_{payment_id:04d}_Lote_{row['lot_id']:04d}_{datetime.now():%Y%m%d_%H%M%S}_{secrets.token_hex(4)}.png"
        target=folder/name
        content=build_payment_image(snapshot,now())
        with target.open('xb') as output: output.write(content)
        with database(True) as db:
            db.execute('UPDATE pagamentos SET pdf_name=? WHERE id=?',(name,payment_id))
        return target

    @app.post('/lote/<int:lot_id>/pagamento')
    def save_payment(lot_id):
        confirm()
        key=request.form.get('payment_key','')
        try: signed=URLSafeSerializer(app.secret_key,salt='payment').loads(key)
        except BadSignature: raise ValueError('Formulário de pagamento inválido. Abra o lote novamente.')
        if signed.get('lot')!=lot_id: raise ValueError('Pagamento não pertence a este lote.')
        with database(True) as db:
            existing=db.execute('SELECT id FROM pagamentos WHERE request_key=?',(key,)).fetchone()
            if existing:
                flash('Este pagamento já foi confirmado. Nenhum registro duplicado foi criado.','success')
                return redirect(url_for('lot_detail',lot_id=lot_id))
            lot=detail(db,lot_id)[0]
            buy,previous,quote=payment_context(db,lot)
            if quote!=signed.get('quote'): raise ValueError('O lote ou seus pagamentos mudaram. Reabra a janela e confira o saldo atualizado.')
            cash,checks,note,total=parse_payment(request.form)
            balance=buy['balance']-total
            if balance<0 and request.form.get('confirm_credit')!='sim': raise ValueError('Confirme o valor excedente como crédito/haver antes de continuar.')
            snapshot=dict(buy,created_at=now(),cash=cash,checks=checks,checks_total=total-cash,total=total,balance=balance,note=note,previous=[{k:p[k] for k in ('created_at','cash_cents','checks_cents','total_cents')} for p in previous])
            payment_id=db.execute('INSERT INTO pagamentos(lot_id,request_key,created_at,cash_cents,checks_cents,total_cents,balance_cents,snapshot) VALUES(?,?,?,?,?,?,?,?)',(lot_id,key,snapshot['created_at'],cash,total-cash,total,balance,json.dumps(snapshot,ensure_ascii=False))).lastrowid
            for c in checks:
                db.execute('INSERT INTO cheques(payment_id,value_cents,compensation_date,number,bank,note) VALUES(?,?,?,?,?,?)',(payment_id,c['value_cents'],c['compensation_date'],c['number'],c['bank'],c['note']))
        try:
            payment_report(payment_id)
            flash('Pagamento confirmado e imagem PNG gerada em uma única página. Baixe pelo histórico de pagamentos.','success')
        except Exception:
            app.logger.exception('Pagamento salvo; falha na imagem')
            flash('Pagamento já salvo. A imagem falhou; use Gerar imagem no histórico, sem repetir o pagamento.','error')
        return redirect(url_for('lot_detail',lot_id=lot_id))

    @app.post('/pagamento/<int:payment_id>/pdf')
    @app.post('/pagamento/<int:payment_id>/imagem')
    def regenerate_payment(payment_id):
        path=payment_report(payment_id)
        return send_file(path,as_attachment=True)

    @app.get('/pagamento/<int:payment_id>/pdf')
    @app.get('/pagamento/<int:payment_id>/imagem')
    def download_payment(payment_id):
        with database() as db:
            row=db.execute('SELECT pdf_name FROM pagamentos WHERE id=?',(payment_id,)).fetchone()
        if not row or not row['pdf_name']: raise ValueError('Relatório indisponível. Use Gerar imagem no histórico de pagamentos.')
        name=row['pdf_name'];path=Path(app.config['REPORT_DIR'])/'Pagamentos'/name
        if Path(name).name!=name or not path.is_file(): raise ValueError('Arquivo não encontrado. Gere novamente pelo histórico.')
        return send_file(path,as_attachment=True)

    @app.get('/calculadora')
    def calculator():
        return render_template('calculator.html',title='Calculadora')

    @app.get('/transferir-calculadora')
    def transfer_calculator():
        return render_template('calculator_transfer.html',title='Transferir calculadora')

    @app.route('/clientes',methods=['GET','POST'])
    def clients():
        with database(request.method=='POST') as db:
            if request.method=='POST':
                name=required(request.form.get('name'),'Nome do cliente')
                db.execute('INSERT INTO clientes(name) VALUES(?)',(name,))
                flash('Cliente cadastrado.','success')
                return redirect(url_for('clients'))
            rows=db.execute('SELECT * FROM clientes ORDER BY name,id').fetchall()
        return render_template('clients.html',rows=rows)

    @app.get('/vendas')
    @app.get('/despesas')
    @app.get('/percas')
    def choose_lot():
        with database() as db:
            lots=db.execute("SELECT * FROM lotes WHERE status='aberto' ORDER BY id DESC").fetchall()
        return render_template('choose.html',lots=lots,kind=request.path.strip('/'))

    @app.route('/lote/<int:lot_id>/<kind>/novo',methods=['GET','POST'])
    @app.route('/lote/<int:lot_id>/<kind>/<int:item_id>/editar',methods=['GET','POST'])
    def entry(lot_id,kind,item_id=None):
        if kind not in ('vendas','despesas','percas'): abort(404)
        with database(request.method=='POST') as db:
            lot=editable(db,lot_id)
            item=db.execute(f'SELECT * FROM {kind} WHERE id=? AND lot_id=?',(item_id,lot_id)).fetchone() if item_id else None
            if item_id and not item: abort(404)
            clients=db.execute('SELECT * FROM clientes ORDER BY name,id').fetchall()
            if request.method=='POST':
                if item: confirm()
                date=date_value(request.form.get('date'))
                if date<lot['withdrawal']: raise ValueError('A data não pode ser anterior à retirada do lote.')
                if kind=='vendas':
                    weight=amount(request.form.get('weight'),1000,'Peso vendido',True)
                    price=amount(request.form.get('price'),100,'Valor por kg')
                    note=request.form.get('note','').strip()
                    if len(note)>500 or any(ord(c)<32 for c in note): raise ValueError('Observação: use até 500 caracteres sem quebras de linha.')
                    new=request.form.get('new_client','').strip()
                    if new:
                        name=required(new,'Novo cliente')
                        client_id=db.execute('INSERT INTO clientes(name) VALUES(?)',(name,)).lastrowid
                    else:
                        client=db.execute('SELECT * FROM clientes WHERE id=?',(request.form.get('client_id'),)).fetchone()
                        if not client: raise ValueError('Selecione um cliente ou informe o nome de um novo cliente.')
                        client_id,name=client['id'],client['name']
                    columns='client_id=?,client_name=?,date=?,weight_g=?,price_cents=?,note=?'
                    values=(client_id,name,date,weight,price,note)
                    fields='client_id,client_name,date,weight_g,price_cents,note'
                elif kind=='percas':
                    weight_g=amount(request.form.get('weight'),1000,'PERCAS (kg)',True)
                    note=required(request.form.get('note'),'Observação da PERCA',500)
                    validate_percas(db,lot_id,weight_g,item_id)
                    values=(date,weight_g,note)
                    columns='date=?,weight_g=?,note=?'
                    fields='date,weight_g,note'
                else:
                    values=(required(request.form.get('description'),'Descrição',300),date,amount(request.form.get('value'),100,'Valor',True))
                    columns='description=?,date=?,value_cents=?'
                    fields='description,date,value_cents'
                if item:
                    db.execute(f'UPDATE {kind} SET {columns} WHERE id=? AND lot_id=?',(*values,item_id,lot_id))
                else:
                    db.execute(f'INSERT INTO {kind}({fields},lot_id) VALUES({",".join("?" for _ in range(len(values)+1))})',(*values,lot_id))
                if kind=='vendas' and not item:
                    optional_perca(db,lot_id,date)
                revision(db,lot_id)
                flash('Lançamento salvo. Totais recalculados.','success')
                return redirect(url_for('lot_detail',lot_id=lot_id))
        return render_template('entry.html',kind=kind,lot=lot,item=item,clients=clients)

    @app.route('/lote/<int:lot_id>/<kind>/<int:item_id>/excluir',methods=['GET','POST'])
    def delete(lot_id,kind,item_id):
        if kind not in ('vendas','despesas','percas'): abort(404)
        with database(request.method=='POST') as db:
            lot=editable(db,lot_id)
            item=db.execute(f'SELECT * FROM {kind} WHERE id=? AND lot_id=?',(item_id,lot_id)).fetchone()
            if not item: abort(404)
            if request.method=='POST':
                confirm()
                db.execute(f'DELETE FROM {kind} WHERE id=? AND lot_id=?',(item_id,lot_id))
                revision(db,lot_id)
                flash('Lançamento excluído. Totais recalculados.','success')
                return redirect(url_for('lot_detail',lot_id=lot_id))
        return render_template('confirm.html',title='Excluir lançamento',message=f"Excluir definitivamente o lançamento {item_id} ({kind}), de {brdate(item['date'])}? Esta ação recalcula o lote.",lot=lot)

    def write_report(lot,sales,expenses,c):
        generated=now()
        slug=unicodedata.normalize('NFKD',lot['farm']).encode('ascii','ignore').decode()
        slug=re.sub(r'[^A-Za-z0-9]+','-',slug).strip('-')[:60] or 'Granja'
        name=f"Lote_{lot['id']:04d}_{slug}_{datetime.now():%d-%m-%Y_%H%M%S}_{secrets.token_hex(3)}.pdf"
        content=build_pdf(lot,sales,expenses,c,generated)
        target=Path(app.config['REPORT_DIR'])/name
        temp=target.with_suffix('.tmp')
        try:
            temp.write_bytes(content)
            os.replace(temp,target)
        finally:
            temp.unlink(missing_ok=True)
        return name

    @app.route('/lote/<int:lot_id>/fechar',methods=['GET','POST'])
    def close(lot_id):
        with database(request.method=='POST') as db:
            lot=editable(db,lot_id)
            lot,sales,expenses=detail(db,lot_id)
            c=calculate(lot,sales,expenses,closing=True)
            if request.method=='POST':
                confirm()
                if request.form.get('revision')!=str(lot['revision']): raise ValueError('O lote mudou desde a conferência. Abra o resumo de fechamento novamente.')
                if c['loss_g'] and request.form.get('physical')!='nao': raise ValueError('Não é possível encerrar enquanto houver estoque físico ou sem confirmar sua ausência.')
                required(lot['farm'],'Granja')
                if lot['entry_g']<=0 or lot['paid_g']<=0 or lot['heads']<=0: raise ValueError('Complete os campos obrigatórios do lote.')
                closed=dict(lot,status='finalizado',closed_at=now())
                name=write_report(closed,sales,expenses,c)
                db.execute("UPDATE lotes SET status='finalizado',closed_at=?,pdf_name=?,revision=revision+1 WHERE id=?",(closed['closed_at'],name,lot_id))
                flash('Lote finalizado. PDF gerado e salvo em Relatorios. Use Baixar PDF para obtê-lo.','success')
                return redirect(url_for('lot_detail',lot_id=lot_id))
        return render_template('detail.html',lot=lot,sales=sales,expenses=expenses,c=c,closing=True)

    @app.route('/lote/<int:lot_id>/reabrir',methods=['GET','POST'])
    def reopen(lot_id):
        with database(request.method=='POST') as db:
            lot=detail(db,lot_id)[0]
            if lot['status']!='finalizado': raise ValueError('Este lote já está aberto.')
            if request.method=='POST':
                confirm()
                db.execute("UPDATE lotes SET status='aberto',closed_at=NULL,pdf_name=NULL,revision=revision+1 WHERE id=?",(lot_id,))
                flash('Lote reaberto. PDFs anteriores foram preservados como registros históricos.','success')
                return redirect(url_for('lot_detail',lot_id=lot_id))
        return render_template('confirm.html',title='Reabrir lote',message='A reabertura libera alterações e volta a tratar a quebra como estoque restante. PDFs anteriores continuarão na pasta, mas não representarão novas alterações. Confirmar?',lot=lot)

    @app.post('/lote/<int:lot_id>/pdf')
    def generate(lot_id):
        with database(True) as db:
            lot,sales,expenses=detail(db,lot_id)
            name=write_report(lot,sales,expenses,calculate(lot,sales,expenses))
            db.execute('UPDATE lotes SET pdf_name=? WHERE id=?',(name,lot_id))
        return redirect(url_for('download',lot_id=lot_id))

    @app.get('/lote/<int:lot_id>/pdf')
    def download(lot_id):
        with database() as db: lot=detail(db,lot_id)[0]
        name=lot['pdf_name']
        if not name or Path(name).name!=name or not (Path(app.config['REPORT_DIR'])/name).is_file():
            raise ValueError('PDF não encontrado. Use Gerar novamente para criar o arquivo.')
        return send_file(Path(app.config['REPORT_DIR'])/name,as_attachment=True)

    def backup(db,prefix='Backup'):
        name=f'{prefix}_{datetime.now():%Y-%m-%d_%H%M%S}_{secrets.token_hex(3)}.db'
        target=Path(app.config['BACKUP_DIR'])/name
        dest=sqlite3.connect(target)
        try: db.backup(dest)
        finally: dest.close()
        return target

    @app.route('/backup',methods=['GET','POST'])
    def backups():
        if request.method=='POST':
            with database() as db: path=backup(db)
            return send_file(path,as_attachment=True)
        return render_template('backup.html')

    @app.post('/restaurar')
    def restore():
        confirm()
        file=request.files.get('backup')
        if not file or not file.filename: raise ValueError('Selecione um backup .db deste sistema.')
        temp=Path(app.config['BACKUP_DIR'])/f'upload_{secrets.token_hex(12)}.tmp'
        source=None
        try:
            file.save(temp)
            source=sqlite3.connect(f'{temp.as_uri()}?mode=ro',uri=True)
            source.execute('PRAGMA trusted_schema=OFF')
            source.execute('PRAGMA query_only=ON')
            if source.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or source.execute('PRAGMA foreign_key_check').fetchall():
                raise ValueError('Backup corrompido ou com vínculos inválidos.')
            with database() as db:
                schema="SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
                expected=[tuple(r) for r in db.execute(schema).fetchall()]
                version=source.execute('PRAGMA user_version').fetchone()[0]
                legacy_payments=not source.execute("SELECT 1 FROM sqlite_master WHERE name='pagamentos'").fetchone()
                if legacy_payments:
                    expected=[r for r in expected if r[2] not in ('pagamentos','cheques')]
                if version==1:
                    expected=[r for r in expected if r[2]!='percas']
                if source.execute(schema).fetchall()!=expected or version not in (1,2):
                    raise ValueError('Backup incompatível. Selecione um arquivo criado por esta versão do sistema.')
                if version==1 or legacy_payments:
                    source.close()
                    source=None
                    initialize(temp)
                    source=sqlite3.connect(f'{temp.as_uri()}?mode=ro',uri=True)
                backup(db,'Antes_da_restauracao')
                source.backup(db)
                epoch['value']=secrets.token_hex(16)
            flash('Backup restaurado. A cópia anterior está em backups. PDFs são preservados separadamente; gere novamente se necessário.','success')
        finally:
            if source: source.close()
            temp.unlink(missing_ok=True)
        return redirect(url_for('dashboard'))

    return app
