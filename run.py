import argparse
import threading
import webbrowser
import subprocess
import json
from pathlib import Path
from waitress import serve
from app import create_app

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--no-browser',action='store_true')
    parser.add_argument('--port',type=int,default=5000)
    parser.add_argument('--init-db',action='store_true')
    parser.add_argument('--tailscale',action='store_true')
    args=parser.parse_args()
    remote=[]
    if args.tailscale:
        executable=Path('C:/Program Files/Tailscale/tailscale.exe')
        state=json.loads(subprocess.check_output([str(executable),'status','--json'],text=True))
        if state.get('BackendState')!='Running':
            raise SystemExit('Conecte o Tailscale neste computador antes de iniciar.')
        remote=[state['Self']['DNSName'].rstrip('.'),*state['TailscaleIPs']]
        subprocess.run([str(executable),'serve','--bg','--http=8500',f'http://127.0.0.1:{args.port}'],check=True)
        print(f'Acesso pelo celular com Tailscale: http://{remote[0]}:8500',flush=True)
    app=create_app({'REMOTE_HOSTS':remote})
    if not args.init_db:
        address=f'http://127.0.0.1:{args.port}'
        if not args.no_browser:
            threading.Timer(1.5,lambda:webbrowser.open(address)).start()
        print(f'Controle de lotes: {address}\nMantenha esta janela aberta. Ctrl+C para encerrar.',flush=True)
        serve(app,host='127.0.0.1',port=args.port,threads=4)
