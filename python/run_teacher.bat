@echo off
rem Teacher experiment (experiments\teacher.toml): ~5-6 h on the GPU. Tiny smoke test first.
rem Don't close this window or click inside it until teacher_log.txt says TEACHER_DONE.
cd /d "%~dp0"
del bench_done.flag 2>nul
start "keep awake" /min .venv\Scripts\pythonw.exe -m ecosim.keepawake bench_done.flag
echo %date% %time% smoke > teacher_log.txt
.venv\Scripts\python.exe -u -m ecosim.bench.run experiments\teacher_smoke.toml > teacher_smoke_log.txt 2>&1
findstr /C:"Traceback" teacher_smoke_log.txt >nul && goto fail
echo %date% %time% teacher start >> teacher_log.txt
.venv\Scripts\python.exe -u -m ecosim.bench.run experiments\teacher.toml > teacher_run_log.txt 2>&1
echo %date% %time% TEACHER_DONE >> teacher_log.txt
goto end
:fail
echo %date% %time% SMOKE TEST FAILED, see teacher_smoke_log.txt. TEACHER_DONE >> teacher_log.txt
:end
type nul > bench_done.flag
exit
