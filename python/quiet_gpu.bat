@echo off
rem QUIET MODE for the 3080. Right-click this file -> "Run as administrator".
rem Caps the card at 150 W (normal is 320 W). Steady low heat instead of loud bursts. Safe, and it resets on reboot.
rem Also turns off the burst pauses (gpu_throttle.txt = 0), since the power cap does the slowing.
rem Safe to run any time, even mid-experiment. Undo with normal_gpu.bat.
cd /d "%~dp0"
nvidia-smi -pl 150
echo 0 > gpu_throttle.txt
echo.
echo Done. Temperature logging starts now (gpu_temp_log.txt). Close this window any time to stop logging.
nvidia-smi --query-gpu=timestamp,temperature.gpu,power.draw,power.limit,fan.speed,clocks.gr,utilization.gpu --format=csv -l 10 > gpu_temp_log.txt
