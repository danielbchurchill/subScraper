#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d ".venv" ]; then
  echo "Setting up virtual environment..."
  python3 -m venv .venv
  .venv/bin/pip install -r requirements-frozen.txt
fi

exec .venv/bin/python run.py
