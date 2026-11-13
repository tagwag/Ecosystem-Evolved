@echo off
rem Toy brain experiment on the RTX 3080: 5 brain types x 30 seeds x 300 generations (all seeds at once per type).
rem SAFE TO INTERRUPT (close window): finished brain types are saved; rerunning skips them. Progress: run_gpu_log.txt
cd /d "%~dp0"
..\.venv\Scripts\python.exe -u sim_gpu.py 30 300 all
pause
