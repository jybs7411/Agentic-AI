@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Starting the agent with a visible console, so you can see errors.
echo Close this window to quit the agent.
.venv\Scripts\python.exe -m agent
pause
