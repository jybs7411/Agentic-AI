@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$s = (New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Startup') + '\Desktop Agent.lnk');" ^
  "$s.TargetPath = '%~dp0.venv\Scripts\pythonw.exe';" ^
  "$s.Arguments = '-m agent';" ^
  "$s.WorkingDirectory = '%~dp0';" ^
  "$s.Save()"
echo The agent will now start automatically when you sign in to Windows.
echo To undo: press Win+R, type shell:startup, and delete "Desktop Agent".
pause
