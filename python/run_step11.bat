@echo off
rem Step 11: clonal-group scoring + worm scent. GPU smoke test first, then full run (~1-1.5 h) + analysis.
rem Log: step11_log.txt. Do not close this window or click inside it until the log says STEP11_DONE.
cd /d "%~dp0"
del step11_done.flag 2>nul
start "keep awake" /min .venv\Scripts\pythonw.exe -m ecosim.keepawake step11_done.flag
echo quick test > step11_log.txt
.venv\Scripts\python.exe -u -m ecosim.step11 quick >> step11_log.txt 2>&1
findstr /C:"Traceback" step11_log.txt >nul && goto fail
echo full run >> step11_log.txt
.venv\Scripts\python.exe -u -m ecosim.step11 run >> step11_log.txt 2>&1
.venv\Scripts\python.exe -u -m ecosim.step11 analyze >> step11_log.txt 2>&1
echo STEP11_DONE >> step11_log.txt
goto end
:fail
echo QUICK TEST FAILED, full run skipped. STEP11_DONE >> step11_log.txt
:end
type nul > step11_done.flag
exit
