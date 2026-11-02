@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_gpu.ps1"
echo.
echo Finished. Tell Claude "done".
pause
