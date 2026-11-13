@echo off
rem Remote experiment watcher. Leave this window open (minimize it). It starts experiments from python\remote\queue\.
rem SAFE TO CLOSE any time; a running job stops with it and is marked failed.
title Ecosystem remote watcher
cd /d "%~dp0"
..\.venv\Scripts\python.exe -u watcher.py
pause
