@echo off
echo Stopping FinRecon AI (close the server console window, or Ctrl+C in it).
taskkill /F /IM python.exe /T 2>nul
echo Done.
pause
