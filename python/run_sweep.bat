@echo off
rem Factor sweep from a config file in python\sweeps\.  Usage: double-click (runs screen1) or  run_sweep.bat screen1
rem Waits for Step 19 to finish first (one GPU experiment at a time), then: smoke test, evolve all arms, test, analyze.
rem Log: sweep_<name>_log.txt. Results: results\sweep_<name>.md and sweep_<name>_effects.png
rem
rem SAFE TO INTERRUPT: closing this window loses only the arm currently evolving (each arm ~20-40 min).
rem Finished arms are skipped when you run it again, so just re-run this file to resume.
rem Do not run two of these at once, and do not start it while another GPU experiment is running.
cd /d "%~dp0"
set NAME=%1
if "%NAME%"=="" set NAME=screen1
del sweep_%NAME%_done.flag 2>nul
echo %date% %time% waiting for Step 19 (if it is running) > sweep_%NAME%_log.txt
:wait19
if not exist step19_log.txt goto go
findstr /C:"STEP19_DONE" step19_log.txt >nul && goto go
timeout /t 120 /nobreak >nul
goto wait19
:go
start "keep awake" /min .venv\Scripts\pythonw.exe -m ecosim.keepawake sweep_%NAME%_done.flag
echo %date% %time% smoke test >> sweep_%NAME%_log.txt
.venv\Scripts\python.exe -u -m ecosim.sweep quick %NAME% > sweep_%NAME%_quick_log.txt 2>&1
findstr /C:"Traceback" sweep_%NAME%_quick_log.txt >nul && goto fail
echo %date% %time% evolving arms >> sweep_%NAME%_log.txt
.venv\Scripts\python.exe -u -m ecosim.sweep run %NAME% > sweep_%NAME%_run_log.txt 2>&1
findstr /C:"Traceback" sweep_%NAME%_run_log.txt >nul && goto fail
echo %date% %time% testing >> sweep_%NAME%_log.txt
.venv\Scripts\python.exe -u -m ecosim.sweep test %NAME% > sweep_%NAME%_test_log.txt 2>&1
.venv\Scripts\python.exe -u -m ecosim.sweep analyze %NAME% > sweep_%NAME%_analyze_log.txt 2>&1
echo %date% %time% SWEEP_DONE >> sweep_%NAME%_log.txt
goto end
:fail
echo %date% %time% FAILED, see the other sweep_%NAME%_*_log.txt files. SWEEP_DONE >> sweep_%NAME%_log.txt
:end
type nul > sweep_%NAME%_done.flag
exit
