@echo off
cd /d "C:\Users\MT-110326\Documents\Programas\AICascadeWidget"

:: Iniciar backend FastAPI (API + Widget en un solo puerto: 8000)
:: y abrir el widget en Chrome/Edge en modo app
echo ==========================================
echo   AICascade Widget - Iniciando
echo   API + Widget:  http://127.0.0.1:8000
echo   Docs:          http://127.0.0.1:8000/docs
echo ==========================================

:: Buscar Chrome
set "CHROME="
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" set "CHROME=C:\Program Files\Google\Chrome\Application\chrome.exe"
if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" set "CHROME=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"

:: Buscar Edge como fallback
set "EDGE="
if exist "C:\Program Files\Microsoft\Edge\Application\msedge.exe" set "EDGE=C:\Program Files\Microsoft\Edge\Application\msedge.exe"
if exist "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" set "EDGE=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

:: Usar python del venv si existe; si no, python del sistema
set "PY=venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

:: Abrir navegador en modo app
if defined CHROME (
    start "" "%CHROME%" --app="http://127.0.0.1:8000" --new-window
) else if defined EDGE (
    start "" "%EDGE%" --app="http://127.0.0.1:8000" --new-window
) else (
    start "" "http://127.0.0.1:8000"
)

:: Arrancar backend (quedara corriendo en esta consola)
"%PY%" -m uvicorn main:app --host 127.0.0.1 --port 8000

pause