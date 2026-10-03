@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo EcoMate's Python environment is missing.
  echo Run setup.py from this folder first.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" main.py
if errorlevel 1 (
  echo.
  echo EcoMate closed with an error. Check the message above.
  pause
)
