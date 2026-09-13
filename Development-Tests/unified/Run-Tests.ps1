$ErrorActionPreference = 'Stop'
$testRoot = $PSScriptRoot
$sourceRoot = & python (Join-Path $testRoot '../package_paths.py') source
if ($LASTEXITCODE -ne 0) { throw 'Packaged source path discovery failed' }
$out = Join-Path $testRoot 'build'
New-Item -ItemType Directory -Force -Path $out | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $testRoot 'fixtures') | Out-Null
& python (Join-Path $testRoot 'extract_entrypoints.py')
if ($LASTEXITCODE -ne 0) { throw 'Entrypoint extraction failed' }
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
$vsRoot = @(& $vswhere -latest -all -products '*' -property installationPath)[0]
$vcvars = Join-Path $vsRoot 'VC/Auxiliary/Build/vcvarsall.bat'
$environmentLines = & $env:ComSpec /d /s /c "`"$vcvars`" x86 >nul && set"
foreach ($line in $environmentLines) {
    $separator = $line.IndexOf('=')
    if ($separator -gt 0) {
        [Environment]::SetEnvironmentVariable($line.Substring(0,$separator), $line.Substring($separator+1), 'Process')
    }
}
Push-Location $out
try {
    & cl.exe /nologo /std:c++20 /EHsc /Od /Zi /RTC1 /MT /DWIN32 /D_CRT_SECURE_NO_WARNINGS `
        "/I$sourceRoot/game/shared" "/I$sourceRoot/game/shared/ms" "/I$sourceRoot/public" "/I$sourceRoot/public/engine" "/I$sourceRoot/common" `
        (Join-Path $testRoot 'unified_tests.cpp') "$sourceRoot/game/shared/stats/stats.cpp" `
        "$sourceRoot/game/shared/ms/stackstring.cpp" /Fe:unified_tests.exe
    if ($LASTEXITCODE -ne 0) { throw 'Test compilation failed' }
    & './unified_tests.exe' (Join-Path $testRoot 'fixtures')
    if ($LASTEXITCODE -ne 0) { throw 'Unified tests failed' }
    & cl.exe /nologo /std:c++20 /EHsc /Od /Zi /RTC1 /MT /DWIN32 /D_CRT_SECURE_NO_WARNINGS `
        "/I$sourceRoot/game/shared" "/I$sourceRoot/game/shared/ms" "/I$sourceRoot/public" "/I$sourceRoot/public/engine" "/I$sourceRoot/common" `
        (Join-Path $testRoot 'entrypoint_tests.cpp') "$sourceRoot/game/shared/stats/stats.cpp" `
        "$sourceRoot/game/shared/ms/stackstring.cpp" /Fe:entrypoint_tests.exe
    if ($LASTEXITCODE -ne 0) { throw 'Entrypoint test compilation failed' }
    & './entrypoint_tests.exe'
    if ($LASTEXITCODE -ne 0) { throw 'Entrypoint tests failed' }
} finally { Pop-Location }
