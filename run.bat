@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Lancez d'abord setup.bat pour installer Murmure.
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" "%~dp0launch.py" %*
