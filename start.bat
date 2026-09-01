@echo off
echo FinRecon AI - starting...
cd /d "%~dp0backend"

python -c "import flask" 2>nul
if errorlevel 1 (
  echo Installing dependencies (Flask)...
  pip install -r requirements.txt
)

echo Starting server on http://localhost:8080 ...
python app.py
pause
