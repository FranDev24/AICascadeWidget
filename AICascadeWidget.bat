@echo off
REM AICascade Widget - Launcher principal (doble clic / acceso directo)
setlocal
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
  echo [setup] Creando entorno virtual...
  python -m venv venv
  call "venv\Scripts\activate.bat"
  python -m pip install -q -r requirements.txt
)
if not exist app.ico (
  echo [logo] Generando app.ico...
  venv\Scripts\python.exe tools\make_logo.py
)
REM Ventana nativa (pywebview) con fallback automatico a Chrome/Edge --app
start "" "venv\Scripts\pythonw.exe" desktop_app.py
endlocal
