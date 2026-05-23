@echo off
cd /d "%~dp0"

if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)

.venv\Scripts\python -c "import uvicorn" >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    .venv\Scripts\pip install -r requirements-frozen.txt
)

echo Starting SubScraper at http://localhost:8000
.venv\Scripts\python run.py
