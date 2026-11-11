from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files
root=Path(SPECPATH)
a=Analysis([str(root/'desktop.py')],pathex=[str(root)],
    binaries=[],datas=[(str(root/'templates'),'templates'),(str(root/'static'),'static')]+collect_data_files('reportlab')+collect_data_files('webview'),
    hiddenimports=['webview.platforms.edgechromium','webview.platforms.winforms','clr','pythonnet'],
    hookspath=[],hooksconfig={},runtime_hooks=[],excludes=['pytest','tkinter','PyQt5','PyQt6','PySide2','PySide6'],noarchive=False)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,a.binaries,a.datas,[],name='LoteClaro',debug=False,bootloader_ignore_signals=False,strip=False,upx=False,console=False,icon=str(root/'static'/'lote-claro.ico'))
