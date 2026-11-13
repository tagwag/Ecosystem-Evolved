@echo off
rem Back to full power (320 W). Right-click -> "Run as administrator".
cd /d "%~dp0"
nvidia-smi -pl 320
echo 0 > gpu_throttle.txt
pause
