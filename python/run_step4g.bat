@echo off
rem Step 4 on the GPU: growth vs no growth, 32 seeds, 60 generations, then fair test. Results in results\step4g_*
rem Do not close this window or click inside it while it runs.
cd /d "%~dp0"
.venv\Scripts\python.exe -u -m ecosim.step4_gpu run > step4g_log.txt 2>&1
.venv\Scripts\python.exe -u -m ecosim.step4_gpu analyze >> step4g_log.txt 2>&1
exit
