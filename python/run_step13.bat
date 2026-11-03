@echo off
rem Step 13: old null results redone under clonal scoring (13a Step 8, 13b Step 3f, 13c Step 4), ~3.5-4 h.
rem GPU smoke test first. Log: step13_log.txt. Do not close this window or click inside it until it says STEP13_DONE.
cd /d "%~dp0"
del step13_done.flag 2>nul
start "keep awake" /min .venv\Scripts\pythonw.exe -m ecosim.keepawake step13_done.flag
echo %date% %time% smoke test > step13_log.txt
.venv\Scripts\python.exe -u -m ecosim.step13 quick > step13_quick_log.txt 2>&1
findstr /C:"Traceback" step13_quick_log.txt >nul && goto fail
for %%p in (a b c) do (
  echo %date% %time% Step 13%%p start >> step13_log.txt
  .venv\Scripts\python.exe -u -m ecosim.step13 run %%p > step13%%p_log.txt 2>&1
  .venv\Scripts\python.exe -u -m ecosim.step13 analyze %%p >> step13%%p_log.txt 2>&1
)
echo %date% %time% STEP13_DONE >> step13_log.txt
goto end
:fail
echo %date% %time% SMOKE TEST FAILED, see step13_quick_log.txt. STEP13_DONE >> step13_log.txt
:end
type nul > step13_done.flag
exit
