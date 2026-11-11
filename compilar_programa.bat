@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" -m pip install -r requirements-desktop.txt
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --distpath Programa --workpath tmp\build-desktop LoteClaro.spec
if errorlevel 1 exit /b 1
echo Programa pronto em Programa\LoteClaro.exe.
