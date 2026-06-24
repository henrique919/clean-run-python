@echo off
setlocal
cd /d "%~dp0"

rem Prefer a normal Python install; fall back to the Codex bundled runtime used
rem to validate this translation on this computer.
where python >nul 2>nul
if %errorlevel%==0 (
  set "PYTHON=python"
) else (
  set "PYTHON=C:\Users\Harry\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
)

if not exist "%PYTHON%" if not "%PYTHON%"=="python" (
  echo Python could not be found. Install Python 3.10 or later and try again.
  pause
  exit /b 1
)

start "" "http://127.0.0.1:8000/"
"%PYTHON%" app.py
