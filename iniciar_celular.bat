@echo off
chcp 65001 >nul
cd /d "%~dp0"
".venv\Scripts\python.exe" run.py --tailscale --port 5004
if errorlevel 1 pause
