@echo off
setlocal
cd /d "%~dp0"
echo.
echo   MURMURE - Installation
echo.
if exist ".venv\Scripts\python.exe" goto install
py -3.12 -m venv .venv 2>nul
if not errorlevel 1 goto install
py -3.11 -m venv .venv 2>nul
if not errorlevel 1 goto install
python -c "import sys; assert (3,11) <= sys.version_info[:2] < (3,14)" 2>nul
if errorlevel 1 goto python_missing
python -m venv .venv
if errorlevel 1 goto failed
:install
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt -e .
if errorlevel 1 goto failed
echo.
echo Installation terminee. Lancez run.bat.
echo Le modele sera prepare automatiquement au premier lancement.
pause
exit /b 0
:python_missing
echo Python 3.11, 3.12 ou 3.13 x64 est requis.
echo Installez Python depuis https://www.python.org/downloads/windows/ puis relancez setup.bat.
pause
exit /b 1
:failed
echo.
echo Installation interrompue. Verifiez la connexion et le message ci-dessus.
pause
exit /b 1
