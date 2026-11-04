@echo off
rem Step 16 (plateau peaks in new worlds), Step 17 (tournament champions in new worlds), Step 18 (selfish herd +
rem obstacles). ~8 h. GPU smoke tests first. Log: step16_log.txt.
rem Do not close this window or click inside it until step16_log.txt says STEP18_DONE.
cd /d "%~dp0"
del step18_done.flag 2>nul
start "keep awake" /min .venv\Scripts\pythonw.exe -m ecosim.keepawake step18_done.flag
echo %date% %time% smoke tests > step16_log.txt
.venv\Scripts\python.exe -u -m ecosim.step16 quick > step16_quick_log.txt 2>&1
findstr /C:"Traceback" step16_quick_log.txt >nul && goto fail
.venv\Scripts\python.exe -u -m ecosim.step18 quick > step18_quick_log.txt 2>&1
findstr /C:"Traceback" step18_quick_log.txt >nul && goto fail
echo %date% %time% Step 16 peaks + run >> step16_log.txt
.venv\Scripts\python.exe -u -m ecosim.step16 peaks > step16_run_log.txt 2>&1
.venv\Scripts\python.exe -u -m ecosim.step16 run 16 >> step16_run_log.txt 2>&1
.venv\Scripts\python.exe -u -m ecosim.step16 analyze 16 >> step16_run_log.txt 2>&1
echo %time% Step 17 start >> step16_log.txt
.venv\Scripts\python.exe -u -m ecosim.step16 run 17 > step17_log.txt 2>&1
.venv\Scripts\python.exe -u -m ecosim.step16 analyze 17 >> step17_log.txt 2>&1
echo %time% Step 18 start >> step16_log.txt
.venv\Scripts\python.exe -u -m ecosim.step18 run > step18_log.txt 2>&1
.venv\Scripts\python.exe -u -m ecosim.step18 analyze >> step18_log.txt 2>&1
echo %date% %time% STEP18_DONE >> step16_log.txt
goto end
:fail
echo %date% %time% SMOKE TEST FAILED, see step16_quick_log.txt / step18_quick_log.txt. STEP18_DONE >> step16_log.txt
:end
type nul > step18_done.flag
exit
