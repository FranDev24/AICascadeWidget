@echo off
REM AICascadeWidget - Arranque FULL-STACK robusto (Backend :8000 + HUD :8765)
REM Fix: se evita el bug de comillas anidadas usando /d (directorio) en lugar de cd /d "%~dp0" dentro del cmd /c
setlocal
cd /d "%~dp0"

if not exist venv (
  echo [1/4] Creando entorno virtual...
  python -m venv venv
  if errorlevel 1 (
    echo [ERROR] No se pudo crear venv. Instala Python 3.10+ y reintenta.
    pause
    exit /b 1
  )
)
if not exist "venv\Scripts\python.exe" (
  echo [ERROR] venv corrupto: no existe venv\Scripts\python.exe - borra carpeta venv y reintenta.
  pause
  exit /b 1
)
call "venv\Scripts\activate.bat"

echo [2/4] Instalando dependencias...
python -m pip install -q -r requirements.txt

echo [3/4] Liberando puertos ocupados (si quedaron colgados)...
for %%P in (8000 8765) do (
  for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%%P " ^| findstr LISTENING') do (
    echo   - cerrando PID %%a en puerto %%P
    taskkill /F /PID %%a >nul 2>&1
  )
)

echo [3/4] Iniciando backend FastAPI :8000 ...
start "AICascade-Backend" /min /d "%~dp0" "venv\Scripts\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 8000
REM Espera salud del backend hasta 20s (no abre el HUD a ciegas)
set HEALTH_OK=0
powershell -NoProfile -Command "$ok=0; for($i=0;$i -lt 20;$i++){ try { $r=Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://127.0.0.1:8000/api/health; if($r.StatusCode -eq 200){ $ok=1; break } } catch {}; Start-Sleep -Seconds 1 }; if($ok -eq 1){ exit 0 } else { exit 1 }" >nul 2>&1
if not errorlevel 1 set HEALTH_OK=1
if "%HEALTH_OK%"=="1" ( echo   Backend OK en :8000 ) else ( echo   Aviso: backend aun iniciando, continuo con HUD... )

echo [4/4] Iniciando HUD :8765 ...
start "AICascade-HUD" /min /d "%~dp0" "venv\Scripts\python.exe" server.py
timeout /t 3 /nobreak >nul

REM URL de la app: preferir :8000 si el health paso, si no :8765
set APP_URL=http://127.0.0.1:8765
if "%HEALTH_OK%"=="1" set APP_URL=http://127.0.0.1:8000

if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
  start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --app="%APP_URL%" --new-window
) else if exist "C:\Program Files\Microsoft\Edge\Application\msedge.exe" (
  start "" "C:\Program Files\Microsoft\Edge\Application\msedge.exe" --app="%APP_URL%" --new-window
) else (
  start "" "%APP_URL%"
)

echo.
echo  Backend: http://127.0.0.1:8000  (docs: /docs)
echo  HUD:     http://127.0.0.1:8765
echo  App:     %APP_URL%
echo.
echo  Si el HUD no abre, entra manual a %APP_URL%
echo.
pause
endlocal
