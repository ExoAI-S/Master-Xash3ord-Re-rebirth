@echo off
"%~dp0MSR-Launcher.exe" --host-action play --version stable
if errorlevel 1 pause
