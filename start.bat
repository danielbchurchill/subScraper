@echo off
cd /d "%~dp0"

if not exist ".venv" (
    echo Setting up virtual environment...
    python -m venv .venv
    .venv\Scripts\pip install -r requirements-frozen.txt
)

.venv\Scripts\python run.py
