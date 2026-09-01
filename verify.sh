#!/usr/bin/env bash
# FinRecon AI - automated quality check
set -e
cd "$(dirname "$0")/backend"

echo "1) Checking Python syntax..."
python3 -m py_compile app.py database.py seed.py reconciliation.py cash.py ai_provider.py
echo "   OK"

echo "2) Running unit tests..."
python3 -m unittest tests.test_reconciliation -v
echo "   OK"

echo "3) Checking frontend JS syntax..."
node -c ../frontend/app.js
echo "   OK"

echo "4) Starting server and checking health + key endpoints..."
rm -f ../data/*.db
python3 app.py > /tmp/finrecon_verify.log 2>&1 &
PID=$!
sleep 3
curl -sf localhost:8080/api/health > /dev/null && echo "   /api/health OK"
curl -sf localhost:8080/api/dashboard/summary > /dev/null && echo "   /api/dashboard/summary OK"
curl -sf localhost:8080/api/reconciliations > /dev/null && echo "   /api/reconciliations OK"
curl -sf localhost:8080/api/exceptions > /dev/null && echo "   /api/exceptions OK"
curl -sf localhost:8080/api/cash-position > /dev/null && echo "   /api/cash-position OK"
curl -sf localhost:8080/api/cash-forecast > /dev/null && echo "   /api/cash-forecast OK"
curl -sf localhost:8080/ > /dev/null && echo "   / (frontend) OK"
kill $PID 2>/dev/null || true

echo ""
echo "All checks passed."
