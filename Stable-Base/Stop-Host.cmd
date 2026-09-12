@echo off
"%~dp0..\MSR-Launcher.exe" --host-action stop --version stable
if errorlevel 1 pause

