@echo off
rem Makes the watcher start automatically (minimized) every time you log in to Windows. Run once. No admin needed.
rem Undo: delete "Ecosystem watcher.lnk" from the Startup folder (Win+R, type shell:startup).
cd /d "%~dp0"
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Startup')+'\Ecosystem watcher.lnk'); $s.TargetPath='%~dp0start_watcher.bat'; $s.WorkingDirectory='%~dp0'; $s.WindowStyle=7; $s.Save()"
echo Autostart installed. The watcher will start minimized at every login.
pause
