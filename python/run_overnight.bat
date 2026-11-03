@echo off
rem OVERNIGHT: Step 11 rerun (clonal + worm scent, 200 gens) then Step 12 (3d and 8c redone under clonal scoring).
rem GPU smoke tests first; full runs only if they pass. ~5 hours on an RTX 3080. Log: overnight_log.txt
rem Do not close this window or click inside it until overnight_log.txt says OVERNIGHT_DONE.
cd /d "%~dp0"
del overnight_done.flag 2>nul
start "keep awake" /min .venv\Scripts\pythonw.exe -m ecosim.keepawake overnight_done.flag
echo %date% %time% smoke tests > overnight_log.txt
.venv\Scripts\python.exe -u -m ecosim.step11 quick > overnight_quick_log.txt 2>&1
.venv\Scripts\python.exe -u -m ecosim.step12 quick >> overnight_quick_log.txt 2>&1
findstr /C:"Traceback" overnight_quick_log.txt >nul && goto fail
echo %date% %time% Step 11 start >> overnight_log.txt
.venv\Scripts\python.exe -u -m ecosim.step11 run > step11_log.txt 2>&1
.venv\Scripts\python.exe -u -m ecosim.step11 analyze >> step11_log.txt 2>&1
echo %date% %time% Step 12 start >> overnight_log.txt
.venv\Scripts\python.exe -u -m ecosim.step12 run > step12_log.txt 2>&1
.venv\Scripts\python.exe -u -m ecosim.step12 analyze >> step12_log.txt 2>&1
echo %date% %time% OVERNIGHT_DONE >> overnight_log.txt
goto end
:fail
echo %date% %time% SMOKE TEST FAILED, see overnight_quick_log.txt. OVERNIGHT_DONE >> overnight_log.txt
:end
type nul > overnight_done.flag
exit
