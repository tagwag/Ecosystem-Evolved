@echo off
rem Step 3e: hunger vs no hunger at 4 movement costs, 32 seeds each (~25 min on an RTX 3080). Results in results\step3e_*
rem Do not close this window or click inside it while it runs (a click pauses it).
cd /d "%~dp0"
.venv\Scripts\python.exe -u -m ecosim.step3e run > step3e_log.txt 2>&1
.venv\Scripts\python.exe -u -m ecosim.step3e analyze >> step3e_log.txt 2>&1
exit
