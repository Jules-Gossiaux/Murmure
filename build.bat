@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Lancez setup.bat avant de construire l'application.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install pyinstaller==6.22.3
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m PyInstaller --noconfirm murmure.spec
if errorlevel 1 goto failed
echo Application construite : dist\Murmure\Murmure.exe
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0create_shortcut.ps1"
if errorlevel 1 echo Le raccourci n'a pas pu être créé automatiquement.
pause
exit /b 0
:failed
echo Construction interrompue. Consultez le message ci-dessus.
pause
exit /b 1
