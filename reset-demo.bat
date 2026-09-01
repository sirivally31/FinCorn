@echo off
echo Resetting FinRecon AI demo data via API (server must already be running)...
curl -X POST http://localhost:8080/api/demo/reset
echo.
echo Done. Refresh the dashboard in your browser.
pause
