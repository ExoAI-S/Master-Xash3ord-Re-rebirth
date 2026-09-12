@echo off
"%~dp0runtime\python.exe" "%~dp0FN\fn_server.py" serve
if errorlevel 1 pause
