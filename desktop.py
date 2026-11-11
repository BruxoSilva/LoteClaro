"""Windows entry point. Application files and user records remain separate."""
import argparse
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
import threading

BASE = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent

def configuration(base=BASE, override=None):
    settings=base/'lote-claro.json'
    config=json.loads(settings.read_text(encoding='utf-8')) if settings.exists() else {}
    root=Path(override or config.get('data_directory') or (Path(os.environ.get('LOCALAPPDATA',str(Path.home()))) / 'LoteClaro')).resolve()
    if config.get('require_existing_database') and not override and not (root/'data'/'calculadora.db').is_file():
        raise ValueError(f'Banco existente não encontrado em {root / "data" / "calculadora.db"}. Nenhum banco novo foi criado. Confira lote-claro.json.')
    port=int(config.get('port',5077))
    if not 1024<=port<=65535: raise ValueError('Porta inválida em lote-claro.json.')
    return root,port

class InstanceLock:
    def __init__(self,path):
        import msvcrt
        path.parent.mkdir(parents=True,exist_ok=True)
        try:
            self.file=path.open('a+b');self.file.seek(0)
            if self.file.read(1)==b'': self.file.write(b'0');self.file.flush()
            self.file.seek(0)
            msvcrt.locking(self.file.fileno(),msvcrt.LK_NBLCK,1)
        except (OSError, PermissionError):
            if getattr(self,'file',None): self.file.close()
            raise ValueError('O Lote Claro já está aberto. Use a janela existente.')
    def close(self):
        import msvcrt
        self.file.seek(0);msvcrt.locking(self.file.fileno(),msvcrt.LK_UNLCK,1);self.file.close()

def create_desktop_app(root):
    from app import create_app
    return create_app(dict(DB_PATH=root/'data'/'calculadora.db',REPORT_DIR=root/'Relatorios',BACKUP_DIR=root/'backups',DESKTOP_MODE=True))

def smoke_test(output):
    import tempfile
    import io
    from PIL import Image
    from app.payment_pdf import build_payment_image
    with tempfile.TemporaryDirectory(prefix='lote-exe-check-') as directory:
        app=create_desktop_app(Path(directory));app.testing=True
        with app.test_client() as client:
            for url in ['/','/calculadora','/lote/novo','/backup','/transferir-calculadora','/static/style.css','/static/math-engine.js']:
                assert client.get(url).status_code==200,url
            with client.session_transaction() as session: token=session['csrf']
            assert client.post('/lote/novo',data=dict(csrf=token,farm='Teste isolado',withdrawal='2026-11-03',heads='1',entry='10',paid='10',cost='5')).status_code==302
            assert client.post('/lote/1/pdf',data=dict(csrf=token)).status_code==302
            assert client.get('/lote/1/pdf').data.startswith(b'%PDF')
            import re
            html=client.get('/lote/1').get_data(as_text=True)
            key=re.search(r'name="payment_key" value="([^"]+)"',html).group(1)
            assert client.post('/lote/1/pagamento',data=dict(csrf=token,payment_key=key,confirm='sim',cash='10')).status_code==302
            response=client.get('/pagamento/1/imagem')
            try:
                assert response.mimetype=='image/png'
                Image.open(io.BytesIO(response.get_data())).verify()
            finally:
                response.close()
        Path(output).write_text(json.dumps({'ok':True,'checks':['templates','static','SQLite','lot','PDF','payment PNG'],'isolated':True}),encoding='utf-8')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--data-dir')
    parser.add_argument('--smoke-test',metavar='RESULT_JSON')
    parser.add_argument('--window-test',metavar='RESULT_JSON')
    args=parser.parse_args()
    if args.smoke_test:
        smoke_test(args.smoke_test);return
    root,port=configuration(override=args.data_dir)
    root.mkdir(parents=True,exist_ok=True)
    lock=InstanceLock(root/'data'/'desktop.lock')
    server=None
    try:
        logdir=root/'logs';logdir.mkdir(exist_ok=True)
        handler=RotatingFileHandler(logdir/'aplicativo.log',maxBytes=2_000_000,backupCount=3,encoding='utf-8')
        logging.basicConfig(level=logging.WARNING,handlers=[handler])
        from waitress import create_server
        import webview
        server=create_server(create_desktop_app(root),host='127.0.0.1',port=port,threads=4)
        threading.Thread(target=server.run,daemon=True).start()
        webview.settings['ALLOW_DOWNLOADS']=True
        webview.settings['ALLOW_FILE_URLS']=False
        window=webview.create_window('Lote Claro — Controle financeiro',f'http://127.0.0.1:{port}',width=1400,height=920,min_size=(900,640),background_color='#f4f6f8',text_select=True,zoomable=True,confirm_close=not bool(args.window_test))
        if args.window_test:
            def check_window():
                try:
                    import time
                    for _ in range(60):
                        title=window.evaluate_js('document.querySelector("h1")?.textContent')
                        if title: break
                        time.sleep(.5)
                    assert title=='Painel inicial',title
                    window.evaluate_js('localStorage.setItem("desktop-check", "ok")')
                    assert window.evaluate_js('localStorage.getItem("desktop-check")')=='ok'
                    Path(args.window_test).write_text(json.dumps({'ok':True,'title':title,'native_window':True}),encoding='utf-8')
                except Exception as exc:
                    Path(args.window_test).write_text(json.dumps({'ok':False,'error':str(exc)}),encoding='utf-8')
                finally: window.destroy()
            window.events.loaded+=check_window
        webview.start(gui='edgechromium',private_mode=False,storage_path=str(root/'perfil-aplicativo'),localization={
            'global.quitConfirmation':'Encerrar o Lote Claro? Salve os lançamentos antes de sair. O acesso pelo telefone também para enquanto o aplicativo estiver fechado.',
            'global.quit':'Encerrar','global.cancel':'Cancelar','global.saveFile':'Salvar arquivo',
            'windows.fileFilter.allFiles':'Todos os arquivos','windows.fileFilter.otherFiles':'Outros arquivos'})
    finally:
        if server: server.close()
        lock.close()

if __name__=='__main__':
    try: main()
    except Exception as exc:
        logging.exception('Falha no aplicativo')
        if '--smoke-test' in sys.argv or '--window-test' in sys.argv:
            raise
        import ctypes
        ctypes.windll.user32.MessageBoxW(None,f'Não foi possível abrir o Lote Claro.\n\n{exc}\n\nSe a porta estiver ocupada, feche a outra instância. Se faltar WebView2, instale o Microsoft Edge WebView2 Runtime.','Lote Claro',0x10)
