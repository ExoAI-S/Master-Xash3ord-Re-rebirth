@echo off
"%~dp0..\MSR-Launcher.exe" --host-action start --version enhanced
if errorlevel 1 pause

