@echo off
rem Test bench: drag a settings file (experiments\*.toml) onto this file, or: run_experiment.bat experiments\NAME.toml [--quick]
rem Runs on your GPU only. Report: runs\bench\NAME\summary.md (+ charts). Don't close this window until it says done.
cd /d "%~dp0"
if "%~1"=="" (
  echo Drag a .toml file from the experiments folder onto run_experiment.bat
  pause
  exit /b
)
start "keep awake" /min .venv\Scripts\pythonw.exe -m ecosim.keepawake bench_done.flag
del bench_done.flag 2>nul
.venv\Scripts\python.exe -u -m ecosim.bench.run "%~1" %2 2>&1 | .venv\Scripts\python.exe -c "import sys; f=open('bench_log.txt','w'); [ (sys.stdout.write(l), f.write(l), f.flush()) for l in sys.stdin ]"
type nul > bench_done.flag
echo.
echo Done. Report: runs\bench\  (newest folder) - summary.md
pause
