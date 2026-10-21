@echo off
REM AICascadeWidget - Instalar accesos directos (Escritorio + Barra de tareas)
REM Uso: doble clic. Crea .lnk con icono app.ico apuntando a AICascadeWidget.bat
setlocal
cd /d "%~dp0"
set APPDIR=%~dp0
set APPDIR=%APPDIR:~0,-1%
set ICON=%APPDIR%\app.ico
set TARGET=%APPDIR%\AICascadeWidget.bat
if not exist "%ICON%" (
  echo [INFO] app.ico no existe aun - genera con: venv\Scripts\python.exe tools\make_logo.py
)
if not exist "%TARGET%" (
  echo [ERROR] No existe %TARGET%
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%APPDIR%\tools\install_shortcuts.ps1" -AppDir "%APPDIR%"
echo.
echo Listo. Busca "AICascade Widget" en Escritorio.
echo Para fijar a la barra: clic derecho al acceso ^> "Anclar a la barra de tareas".
pause
endlocal
