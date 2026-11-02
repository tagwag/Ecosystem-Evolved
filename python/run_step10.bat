@echo off
rem Step 10 diagnostic: quick GPU smoke test, then the full run (~30 min) + analysis. Log: step10_log.txt
rem Do not close this window or click inside it until step10_log.txt says STEP10_DONE.
cd /d "%~dp0"
start "keep awake" /min .venv\Scripts\pythonw.exe -m ecosim.keepawake step10_done.flag
del step10_done.flag 2>nul
echo quick test > step10_log.txt
.venv\Scripts\python.exe -u -m ecosim.step10 quick >> step10_log.txt 2>&1
findstr /C:"Traceback" step10_log.txt >nul && goto fail
echo full run >> step10_log.txt
.venv\Scripts\python.exe -u -m ecosim.step10 run >> step10_log.txt 2>&1
.venv\Scripts\python.exe -u -m ecosim.step10 analyze >> step10_log.txt 2>&1
echo STEP10_DONE >> step10_log.txt
goto end
:fail
echo QUICK TEST FAILED, full run skipped. STEP10_DONE >> step10_log.txt
:end
type nul > step10_done.flag
exit
