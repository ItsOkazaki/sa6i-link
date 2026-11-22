@echo off
setlocal
cd /d "%~dp0"
echo Applying the Sa6i Clean patch, then packing the candidate folder...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-Sa6i-Clean-Patch.ps1" %*
echo.
echo Everything above is also saved in patch-log.txt.
pause
