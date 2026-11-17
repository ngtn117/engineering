@echo off
chcp 65001 >nul
cd /d "%~dp0"
python editor_podcast.py %*
if errorlevel 9009 (
  echo.
  echo No encuentro Python. Instalalo desde https://www.python.org/downloads/
  echo y marca la casilla "Add python.exe to PATH" al instalar.
)
pause
