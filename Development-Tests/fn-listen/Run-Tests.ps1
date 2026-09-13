$ErrorActionPreference='Stop'
$fnTestRoot=$PSScriptRoot
& python (Join-Path $fnTestRoot 'extract_paths.py')
if($LASTEXITCODE -ne 0){throw 'Source extraction failed'}
$fnVswhere=Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
$fnVsRoot=@(& $fnVswhere -latest -all -products '*' -property installationPath)[0]
$fnVcvars=Join-Path $fnVsRoot 'VC/Auxiliary/Build/vcvarsall.bat'
$fnEnvironmentLines=& $env:ComSpec /d /s /c "`"$fnVcvars`" x86 >nul && set"
foreach($fnLine in $fnEnvironmentLines){$fnSeparator=$fnLine.IndexOf('=');if($fnSeparator -gt 0){[Environment]::SetEnvironmentVariable($fnLine.Substring(0,$fnSeparator),$fnLine.Substring($fnSeparator+1),'Process')}}
Push-Location (Join-Path $fnTestRoot 'build')
try {
    foreach($fnVariant in @('baseline-standalone','candidate-standalone','candidate-legacy')){
        $fnDefines=@('/D_DEBUG')
        if($fnVariant -ne 'candidate-legacy'){$fnDefines+='/DMSR_STANDALONE'}
        if($fnVariant -eq 'baseline-standalone'){$fnDefines+='/DTEST_BASELINE'}
        Write-Output "VARIANT $fnVariant"
        & cl.exe /nologo /std:c++20 /EHsc /Od /Zi /RTC1 /MTd /D_CRT_SECURE_NO_WARNINGS @fnDefines (Join-Path $fnTestRoot 'request_manager_tests.cpp') "/Fe:$fnVariant.exe"
        if($LASTEXITCODE -ne 0){throw "Compilation failed: $fnVariant"}
        & "./$fnVariant.exe"
        if($LASTEXITCODE -ne 0){throw "Tests failed: $fnVariant"}
    }
} finally {Pop-Location}
