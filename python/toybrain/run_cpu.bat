@echo off
rem Toy brain experiment on the CPU: 5 brain types x 3 seeds x 300 generations, 10 cores in parallel.
rem SAFE TO INTERRUPT (close window): results are written only at the end. Progress: run_cpu_log.txt
cd /d "%~dp0"
..\.venv\Scripts\python.exe -u run_cpu.py 3 300 10
