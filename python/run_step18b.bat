@echo off
rem Step 18b: shelter-or-trap re-test of the saved Step 18 brains (~10 min, no evolution).
rem Do not close this window until step18b_log.txt says STEP18B_DONE.
cd /d "%~dp0"
echo %date% %time% start > step18b_log.txt
.venv\Scripts\python.exe -u -m ecosim.step18b quick > step18b_quick_log.txt 2>&1
findstr /C:"Traceback" step18b_quick_log.txt >nul && goto fail
.venv\Scripts\python.exe -u -m ecosim.step18b >> step18b_log.txt 2>&1
echo %date% %time% STEP18B_DONE >> step18b_log.txt
goto end
:fail
echo %date% %time% QUICK TEST FAILED, see step18b_quick_log.txt. STEP18B_DONE >> step18b_log.txt
:end
exit
