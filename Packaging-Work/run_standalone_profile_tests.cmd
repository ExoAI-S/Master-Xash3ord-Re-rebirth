@echo off
setlocal
call "C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvars32.bat" >nul
if errorlevel 1 exit /b 1
pushd "%~dp0"
cl /nologo /std:c++20 /EHsc /MT /utf-8 /DUNICODE /D_UNICODE /DNOMINMAX /I"..\Full-Source\msr_source\src\game\client" /I"..\Full-Source\external\tracy\import\src" "test_standalone_profile.cpp" "..\Full-Source\msr_source\src\game\client\standalone_profile.cpp" /Fe:"test_standalone_profile.exe" /link bcrypt.lib
if errorlevel 1 exit /b 1
test_standalone_profile.exe
set "profile_test_exit=%errorlevel%"
popd
exit /b %profile_test_exit%
