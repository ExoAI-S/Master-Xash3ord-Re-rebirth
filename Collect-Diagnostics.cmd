@echo off
setlocal
cd /d "%~dp0"
"%~dp0Portable-Package\runtime\python.exe" "%~dp0Launcher\collect_diagnostics.py"
echo.
pause
