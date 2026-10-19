@echo off
REM AICascadeWidget - Arranque FULL-STACK (Backend FastAPI :8000 + HUD :8765)
cd /d "%~dp0"

if not exist venv (
  echo [1/4] Creando entorno virtual...
  python -m venv venv
)
call venv\Scripts\activate.bat

echo [2/4] Instalando dependencias...
python -m pip install -q -r requirements.txt

echo [3/4] Iniciando backend FastAPI :8000 ...
start "AICascade-Backend" /min cmd /c "cd /d "%~dp0" && venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000"
timeout /t 5 /nobreak >nul

echo [4/4] Iniciando HUD :8765 ...
start "AICascade-HUD" /min cmd /c "cd /d "%~dp0" && venv\Scripts\python.exe server.py"
timeout /t 3 /nobreak >nul

if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
  start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --app="http://127.0.0.1:8765" --new-window
) else if exist "C:\Program Files\Microsoft\Edge\Application\msedge.exe" (
  start "" "C:\Program Files\Microsoft\Edge\Application\msedge.exe" --app="http://127.0.0.1:8765" --new-window
) else (
  start "" "http://127.0.0.1:8765"
)

echo.
echo  Backend: http://127.0.0.1:8000  ^(docs: /docs^)
echo  HUD:     http://127.0.0.1:8765
echo.
echo  Si el HUD no abre, entra manual a http://127.0.0.1:8765
echo.
pause
