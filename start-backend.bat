@echo off
REM AICascadeWidget - Solo backend FastAPI :8000
cd /d "%~dp0"
if not exist venv python -m venv venv
call venv\Scripts\activate.bat
python -m pip install -q -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
