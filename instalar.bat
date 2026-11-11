@echo off
chcp 65001 >nul
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
 echo Instale Python 3.11 ou superior e marque Add Python to PATH.
 pause
 exit /b 1
)
if not exist ".venv\Scripts\python.exe" python -m venv .venv
if errorlevel 1 goto erro
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto erro
".venv\Scripts\python.exe" run.py --init-db
if errorlevel 1 goto erro
echo Instalacao concluida. Execute iniciar.bat.
pause
exit /b 0
:erro
echo Falha na instalacao. Confira a mensagem acima.
pause
exit /b 1
