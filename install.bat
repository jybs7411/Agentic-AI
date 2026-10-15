@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo === Installing Desktop Agent ===
echo.

where py >nul 2>nul
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")
%PY% --version >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install it from https://www.python.org/downloads/
  echo and tick "Add python.exe to PATH" during installation.
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
findstr /c:"paste-your-key-here" .env >nul
if %errorlevel%==0 (
  echo.
  echo Notepad will open the .env file. Paste your Gemini API key after GEMINI_API_KEY=
  echo then save the file ^(Ctrl+S^) and close Notepad to continue.
  notepad .env
)

echo.
.venv\Scripts\python.exe -m agent.check
pause
