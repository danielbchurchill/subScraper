#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

if ! .venv/bin/python -c "import uvicorn" 2>/dev/null; then
  echo "Installing dependencies..."
  .venv/bin/pip install -r requirements-frozen.txt
fi

echo "Starting SubScraper at http://localhost:8000"
exec .venv/bin/python run.py
