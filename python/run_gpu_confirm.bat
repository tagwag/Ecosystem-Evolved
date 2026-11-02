@echo off
rem Step 3d fully on the GPU: hunger vs no hunger, scarce food, seeds 1-32, 60 generations (~15 min on an RTX 3080).
cd /d "%~dp0"
.venv\Scripts\python.exe -u -m ecosim.batch3_gpu confirm > run_gpu_confirm_log.txt 2>&1
echo Finished. Tell Claude "done".
pause
