@echo off
"%~dp0..\Version-Tools\powershell\pwsh.exe" -NoProfile -File "%~dp0Host.ps1" -Action Start
if errorlevel 1 goto failed
"%~dp0..\Version-Tools\powershell\pwsh.exe" -NoProfile -File "%~dp0Host.ps1" -Action Browse
if errorlevel 1 goto failed
exit /b 0
:failed
pause
exit /b 1

