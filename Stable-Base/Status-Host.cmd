@echo off
"%~dp0..\MSR-Launcher.exe" --host-action status --version stable
if errorlevel 1 pause

