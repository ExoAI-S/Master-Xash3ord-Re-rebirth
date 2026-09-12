$stage='C:\Users\chels\Documents\Codex\2026-09-11\thi-2\work\MSR-PrimeXT-Port-v1'
$vs='C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\Common7\Tools\VsDevCmd.bat'
$env:PYTHONPATH='C:\Users\chels\Documents\Codex\2026-09-11\thi-2\work\build-tools'
$cmdLine='call "'+$vs+'" -arch=x86 -host_arch=x64 && "C:\Python314\python.exe" -m cmake --build "'+$stage+'\build-msr" --parallel 6'
& cmd.exe /d /s /c $cmdLine *> "$PSScriptRoot\build-resume.log"
$buildExit=$LASTEXITCODE
Get-Content "$PSScriptRoot\build-resume.log" -Tail 35
exit $buildExit
