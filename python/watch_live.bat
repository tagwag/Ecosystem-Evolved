@echo off
rem Watch evolution live: 16 seeds of hunger_scarce for 300 generations, first 4 seeds shown in the viewer.
rem Saves to runs\watch (does not touch the Step 3d results). Close this window to stop.
cd /d "%~dp0"
start "Ecosystem viewer" .venv\Scripts\python.exe -m ecosim.viewer hunger_scarce
.venv\Scripts\python.exe -u -m ecosim.batch3_fast run hunger_scarce 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 --gens 300 --watch 4 --out runs\watch
pause
