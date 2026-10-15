@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo === Installing Desktop Agent ===
echo.

echo %~dp0 | findstr /i /c:"\Temp\" /c:"\AppData\Local\Temp" >nul
if %errorlevel%==0 (
  echo It looks like you opened this from inside a ZIP file.
  echo Right-click the ZIP, choose "Extract All", then run install.bat from the extracted folder.
  pause
  exit /b 1
)

where py >nul 2>nul
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")
%PY% --version >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install it from https://www.python.org/downloads/
  echo and tick "Add python.exe to PATH" during installation.
  pause
  exit /b 1
)
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 (
  echo Your Python is too old. Install Python 3.10 or newer from https://www.python.org/downloads/
  pause
  exit /b 1
)

if not exist .venv (
  echo Creating a private Python environment in .venv ...
  %PY% -m venv .venv
  if errorlevel 1 (
    echo Could not create the environment.
    pause
    exit /b 1
  )
)

echo Installing libraries (this can take a few minutes the first time) ...
.venv\Scripts\python.exe -m pip install --upgrade pip >nul
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Installation failed. Scroll up to see the error, or send it to Claude.
  pause
  exit /b 1
)

if not exist .env copy .env.example .env >nul
.venv\Scripts\python.exe -m agent.setup_finish
echo.
pause
