@echo off
rem Runs the next experiments in a row (~45 min on an RTX 3080), each with its fair test:
rem   Step 4 on the GPU (growing brains), Step 3f (ASH starvation alarm), Step 8 (predators).
rem Logs: queue_log.txt. Do not close this window or click inside it while it runs.
cd /d "%~dp0"
echo Step 4g > queue_log.txt
.venv\Scripts\python.exe -u -m ecosim.step4_gpu run >> queue_log.txt 2>&1
.venv\Scripts\python.exe -u -m ecosim.step4_gpu analyze >> queue_log.txt 2>&1
echo Step 3f >> queue_log.txt
.venv\Scripts\python.exe -u -m ecosim.step3f run 0.25 >> queue_log.txt 2>&1
.venv\Scripts\python.exe -u -m ecosim.step3f analyze 0.25 >> queue_log.txt 2>&1
echo Step 8 >> queue_log.txt
.venv\Scripts\python.exe -u -m ecosim.step8 run >> queue_log.txt 2>&1
.venv\Scripts\python.exe -u -m ecosim.step8 analyze >> queue_log.txt 2>&1
echo QUEUE_DONE >> queue_log.txt
exit
