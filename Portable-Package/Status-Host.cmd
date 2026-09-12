@echo off
"%~dp0..\MSR-Launcher.exe" --host-action status --version enhanced
if errorlevel 1 pause

