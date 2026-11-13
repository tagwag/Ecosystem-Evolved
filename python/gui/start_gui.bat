@echo off
rem Experiment GUI. Opens http://127.0.0.1:8765 in your browser. Close this window to stop the GUI.
rem SAFE TO CLOSE any time: the GUI only writes form files and job files; runs are done by the watcher.
title Worm Experiment Lab (GUI)
cd /d "%~dp0"
start "" http://127.0.0.1:8765
..\.venv\Scripts\python.exe server.py
pause
