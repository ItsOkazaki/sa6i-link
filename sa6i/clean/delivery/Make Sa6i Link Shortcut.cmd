@echo off
setlocal
cd /d "%~dp0"
echo Creating a Sa6i Link shortcut...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Make-Sa6i-Link-Shortcut.ps1" %*
echo.
echo Everything above is also saved in shortcut-log.txt.
pause
