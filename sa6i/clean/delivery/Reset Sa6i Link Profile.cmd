@echo off
setlocal
cd /d "%~dp0"
echo Starting Sa6i Link with a fresh profile...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Reset-Sa6i-Link-Profile.ps1" %*
echo.
echo Everything above is also saved in reset-log.txt.
pause
