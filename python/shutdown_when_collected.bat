@echo off
rem Waits for collected.flag (written by Claude after the morning report), then shuts the PC down in 2 minutes.
rem Cancel any time: close this window, or after it fires run "shutdown /a" in a command prompt.
cd /d "%~dp0"
del collected.flag 2>nul
:wait
if exist collected.flag goto go
echo %time% waiting for the morning results to be collected (then the PC shuts down). Close this window to cancel.
timeout /t 120 /nobreak >nul
goto wait
:go
del collected.flag 2>nul
shutdown /s /t 120 /c "Ecosystem-Evolved runs finished and collected. Shutting down in 2 minutes. Cancel: shutdown /a"
exit
