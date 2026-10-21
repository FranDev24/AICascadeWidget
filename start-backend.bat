@echo off
REM AICascadeWidget - Solo backend FastAPI :8000 (sirve API + widget)
setlocal
cd /d "%~dp0"
if not exist venv python -m venv venv
if not exist "venv\Scripts\python.exe" (
  echo [ERROR] venv corrupto: borra carpeta venv y reintenta.
  pause
  exit /b 1
)
call "venv\Scripts\activate.bat"
python -m pip install -q -r requirements.txt
echo Backend + Widget en: http://127.0.0.1:8000  (docs: /docs)
echo HUD alternativo en:  http://127.0.0.1:8765  (python server.py)
venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
endlocal
