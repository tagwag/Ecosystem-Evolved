@echo off
rem Waits for Step 19 to finish, then: test-bench smoke test + the brain_dials experiment on the Step 19 brains.
rem Safe to close while it says "waiting". Don't close it once it starts running (log: bench_after19_log.txt).
cd /d "%~dp0"
:wait
if exist step19_done.flag goto go
echo %time% waiting for Step 19 to finish...
timeout /t 120 /nobreak >nul
goto wait
:go
del bench_done.flag 2>nul
start "keep awake" /min .venv\Scripts\pythonw.exe -m ecosim.keepawake bench_done.flag
echo %date% %time% smoke > bench_after19_log.txt
.venv\Scripts\python.exe -u -m ecosim.bench.run experiments\smoke.toml > bench_smoke_log.txt 2>&1
findstr /C:"Traceback" bench_smoke_log.txt >nul && goto fail
echo %date% %time% brain_dials >> bench_after19_log.txt
.venv\Scripts\python.exe -u -m ecosim.bench.run experiments\brain_dials.toml > bench_brain_dials_log.txt 2>&1
echo %date% %time% BENCH_DONE >> bench_after19_log.txt
goto end
:fail
echo %date% %time% SMOKE TEST FAILED, see bench_smoke_log.txt. BENCH_DONE >> bench_after19_log.txt
:end
type nul > bench_done.flag
exit
