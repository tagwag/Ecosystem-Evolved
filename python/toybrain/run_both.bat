@echo off
rem Starts BOTH runs: CPU version (3 seeds, original code) in its own window, then the 3080 version (30 seeds) here.
rem Both are safe to interrupt. Logs: run_cpu_log.txt and run_gpu_log.txt
cd /d "%~dp0"
start "toy brain CPU" ..\.venv\Scripts\python.exe -u run_cpu.py 3 300 8
..\.venv\Scripts\python.exe -u sim_gpu.py 30 300 all
pause
