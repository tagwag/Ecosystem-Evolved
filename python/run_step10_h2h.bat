@echo off
rem Step 10 head-to-head: gen-30 vs gen-150 brains sharing worlds (~3 min). Log: step10_h2h_log.txt
cd /d "%~dp0"
.venv\Scripts\python.exe -u -m ecosim.step10 h2h > step10_h2h_log.txt 2>&1
echo H2H_DONE >> step10_h2h_log.txt
exit
