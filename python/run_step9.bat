@echo off
rem Step 9 on the GPU: reserved breeding slots, started from the lucky Step 6b lineages (s12, s9, s5).
rem Safe to start now: it first WAITS until no other experiment (any python.exe, e.g. Step 10) is running, so they never share the GPU.
rem Order: wait -> quick self-test (~1 min) -> evolution (2 arms x 30 runs x 60 gens, ~15-30 min) -> fair test.
rem Log: step9_log.txt. Don't close this window while it says RUNNING. Closing it while WAITING is harmless.
cd /d "%~dp0"
echo WAITING for the queue to finish > step9_log.txt
:wait
tasklist /fi "imagename eq python.exe" | find /i "python.exe" >nul && goto sleep
rem no Python running: check again in 15 s (the queue starts a new Python between steps)
timeout /t 15 /nobreak >nul
tasklist /fi "imagename eq python.exe" | find /i "python.exe" >nul || goto go
:sleep
echo WAITING for the running experiment to finish... checking every minute.
timeout /t 60 /nobreak >nul
goto wait
:go
echo RUNNING Step 9 - do not close this window.
echo RUNNING >> step9_log.txt
.venv\Scripts\python.exe -u -m ecosim.step9_gpu test >> step9_log.txt 2>&1 || goto fail
.venv\Scripts\python.exe -u -m ecosim.step9_gpu run >> step9_log.txt 2>&1 || goto fail
.venv\Scripts\python.exe -u -m ecosim.step9_gpu analyze >> step9_log.txt 2>&1 || goto fail
echo STEP9_DONE >> step9_log.txt
echo Finished. Tell Claude "step 9 done".
pause
exit /b
:fail
echo STEP9_FAILED >> step9_log.txt
echo Something failed. Tell Claude "step 9 failed" (details are in step9_log.txt).
pause
