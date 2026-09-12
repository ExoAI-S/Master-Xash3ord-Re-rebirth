@echo off
setlocal
call "C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvars32.bat" >nul
if errorlevel 1 exit /b 1
"%~dp0..\Portable-Package\runtime\python.exe" -B "%~dp0run_script_effect_tests.py"
exit /b %ERRORLEVEL%
