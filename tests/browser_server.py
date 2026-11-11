"""Disposable server for optional Playwright UI checks; never uses the real database."""
from pathlib import Path
import sys
import tempfile
import os
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import create_app
from waitress import serve

if __name__=='__main__':
    with tempfile.TemporaryDirectory(prefix='lote-browser-') as directory:
        root=Path(directory)
        app=create_app(dict(DB_PATH=root/'test.db',REPORT_DIR=root/'reports',BACKUP_DIR=root/'backups'))
        serve(app,host='127.0.0.1',port=int(os.environ.get('BROWSER_TEST_PORT','5003')))
