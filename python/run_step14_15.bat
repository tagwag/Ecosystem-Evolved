@echo off
rem Step 14a (peptide baggage), 14b (selfish-herd predators), then Step 15 (lineage tournament on the arm that
rem evolved most). ~5.5-6 h. GPU smoke tests first. Log: step14_log.txt.
rem Do not close this window or click inside it until step14_log.txt says STEP15_DONE.
cd /d "%~dp0"
del step15_done.flag 2>nul
start "keep awake" /min .venv\Scripts\pythonw.exe -m ecosim.keepawake step15_done.flag
echo %date% %time% smoke tests > step14_log.txt
.venv\Scripts\python.exe -u -m ecosim.step14 quick > step14_quick_log.txt 2>&1
findstr /C:"Traceback" step14_quick_log.txt >nul && goto fail
.venv\Scripts\python.exe -u -m ecosim.step15 quick > step15_quick_log.txt 2>&1
findstr /C:"Traceback" step15_quick_log.txt >nul && goto fail
for %%p in (a b) do (
  echo %date% %time% Step 14%%p start >> step14_log.txt
  .venv\Scripts\python.exe -u -m ecosim.step14 run %%p > step14%%p_log.txt 2>&1
  .venv\Scripts\python.exe -u -m ecosim.step14 analyze %%p >> step14%%p_log.txt 2>&1
)
echo %date% %time% Step 15 start >> step14_log.txt
.venv\Scripts\python.exe -u -m ecosim.step15 run > step15_log.txt 2>&1
.venv\Scripts\python.exe -u -m ecosim.step15 analyze >> step15_log.txt 2>&1
echo %date% %time% STEP15_DONE >> step14_log.txt
goto end
:fail
echo %date% %time% SMOKE TEST FAILED, see step14_quick_log.txt / step15_quick_log.txt. STEP15_DONE >> step14_log.txt
:end
type nul > step15_done.flag
exit
