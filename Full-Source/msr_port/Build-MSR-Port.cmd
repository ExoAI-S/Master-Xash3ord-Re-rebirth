@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Build-MSR-Port.ps1" %*
exit /b %errorlevel%
