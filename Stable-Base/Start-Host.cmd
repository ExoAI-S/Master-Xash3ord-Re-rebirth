@echo off
"%~dp0..\MSR-Launcher.exe" --host-action start --version stable
if errorlevel 1 pause

