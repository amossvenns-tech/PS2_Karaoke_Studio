@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Python hittades inte. Installera Python 3.10 eller 3.11 fran python.org.
  pause
  exit /b 1
)
py -3.11 -m venv .venv
if errorlevel 1 py -3.10 -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
python karaoke_studio.py
pause
