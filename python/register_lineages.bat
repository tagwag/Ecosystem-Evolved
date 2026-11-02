@echo off
rem Adds every lucky lineage (and the best brain of each condition) from ALL finished steps on this computer
rem to the lineage library (python\lineages\). Takes a few seconds. Safe to run any time, even while an
rem experiment is running (it only reads results and copies genomes).
cd /d "%~dp0"
.venv\Scripts\python.exe -m ecosim.lineages scan
echo.
echo Done. Tell Claude "lineages registered" so the new ones get saved to GitHub.
pause
