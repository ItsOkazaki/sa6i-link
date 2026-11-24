@echo off
setlocal
cd /d "%~dp0"
echo Pointing Sa6i Link at the debranded cleaner...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Retarget-Sa6i-Clean-Digests.ps1" %*
echo.
echo Everything above is also saved in retarget-log.txt.
pause
