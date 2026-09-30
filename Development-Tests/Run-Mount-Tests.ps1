$ErrorActionPreference='Stop'
$mountTestRoot=$PSScriptRoot
$mountOutput=Join-Path $mountTestRoot 'mount-build'
New-Item -ItemType Directory -Force -Path $mountOutput | Out-Null
$mountVswhere=Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
$mountVsRoot=@(& $mountVswhere -latest -all -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath)[0]
if(-not $mountVsRoot){throw 'Visual Studio C++ build tools were not found.'}
$mountVcvars=Join-Path $mountVsRoot 'VC\Auxiliary\Build\vcvarsall.bat'
foreach($mountLine in (& $env:ComSpec /d /s /c "`"$mountVcvars`" x86 >nul && set")){
    $mountSeparator=$mountLine.IndexOf('=')
    if($mountSeparator -gt 0){[Environment]::SetEnvironmentVariable($mountLine.Substring(0,$mountSeparator),$mountLine.Substring($mountSeparator+1),'Process')}
}
Push-Location $mountOutput
try {
    & cl.exe /nologo /std:c++17 /EHsc /Od /Zi /RTC1 /UNDEBUG (Join-Path $mountTestRoot 'test_mount_policy.cpp') /Fe:mount-policy.exe
    if($LASTEXITCODE){throw 'Mount policy compile failed.'}
    & .\mount-policy.exe
    if($LASTEXITCODE){throw 'Mount policy checks failed.'}
} finally {Pop-Location}
