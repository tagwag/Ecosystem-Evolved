@echo off
rem Step 19: matched scoring (full-size clone worlds, 2 worlds per brain) - base world vs all-senses world, 300 gens.
rem ~6-8 h. GPU smoke test first. Log: step19_log.txt.
rem Do not close this window or click inside it until step19_log.txt says STEP19_DONE.
cd /d "%~dp0"
del step19_done.flag 2>nul
start "keep awake" /min .venv\Scripts\pythonw.exe -m ecosim.keepawake step19_done.flag
echo %date% %time% smoke test > step19_log.txt
.venv\Scripts\python.exe -u -m ecosim.step19 quick > step19_quick_log.txt 2>&1
findstr /C:"Traceback" step19_quick_log.txt >nul && goto fail
echo %date% %time% base start >> step19_log.txt
.venv\Scripts\python.exe -u -m ecosim.step19 run base > step19_base_log.txt 2>&1
echo %date% %time% rich start >> step19_log.txt
.venv\Scripts\python.exe -u -m ecosim.step19 run rich > step19_rich_log.txt 2>&1
echo %date% %time% analyze >> step19_log.txt
.venv\Scripts\python.exe -u -m ecosim.step19 analyze > step19_analyze_log.txt 2>&1
echo %date% %time% STEP19_DONE >> step19_log.txt
goto end
:fail
echo %date% %time% SMOKE TEST FAILED, see step19_quick_log.txt. STEP19_DONE >> step19_log.txt
:end
type nul > step19_done.flag
exit
