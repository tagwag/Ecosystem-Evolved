@echo off
rem Fair test + stats for Step 3d (hunger vs no hunger, 32 seeds) on the GPU. Results in results\step3d_*
cd /d "%~dp0"
.venv\Scripts\python.exe -u -m ecosim.step3d_analyze > step3d_analyze_log.txt 2>&1
type step3d_analyze_log.txt
echo Finished. Tell Claude "done".
pause
