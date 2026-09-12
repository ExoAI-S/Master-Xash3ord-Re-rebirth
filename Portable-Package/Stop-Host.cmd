@echo off
"%~dp0..\MSR-Launcher.exe" --host-action stop --version enhanced
if errorlevel 1 pause

