#!/usr/bin/env bash
# FinRecon AI - single command startup
set -e
cd "$(dirname "$0")/backend"

echo "FinRecon AI - starting..."

if ! python3 -c "import flask" 2>/dev/null; then
  echo "Installing dependencies (Flask)..."
  pip3 install -r requirements.txt --break-system-packages 2>/dev/null || pip3 install -r requirements.txt
fi

echo "Starting server on http://localhost:8080 ..."
python3 app.py
