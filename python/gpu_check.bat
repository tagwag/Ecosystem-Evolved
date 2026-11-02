@echo off
cd /d "%~dp0"
.venv\Scripts\python.exe -u -m ecosim.gpu_check > gpu_check_log.txt 2>&1
type gpu_check_log.txt
pause
