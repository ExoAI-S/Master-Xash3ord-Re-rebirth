$ErrorActionPreference='Stop'
$testRoot=$PSScriptRoot
$sourceRoot = & python (Join-Path $testRoot '../package_paths.py') source
if ($LASTEXITCODE -ne 0) { throw 'Packaged source path discovery failed' }
$runtimeRoot = & python (Join-Path $testRoot '../package_paths.py') runtime
if ($LASTEXITCODE -ne 0) { throw 'Packaged runtime path discovery failed' }
$out=Join-Path $testRoot 'build'
New-Item -ItemType Directory -Force -Path $out | Out-Null
& python (Join-Path $testRoot 'extract_game_paths.py')
if ($LASTEXITCODE -ne 0) { throw 'Extraction failed' }
$vswhere=Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
$vsRoot=@(& $vswhere -latest -all -products '*' -property installationPath)[0]
$vcvars=Join-Path $vsRoot 'VC/Auxiliary/Build/vcvarsall.bat'
$environmentLines=& $env:ComSpec /d /s /c "`"$vcvars`" x86 >nul && set"
foreach($line in $environmentLines){$separator=$line.IndexOf('=');if($separator -gt 0){[Environment]::SetEnvironmentVariable($line.Substring(0,$separator),$line.Substring($separator+1),'Process')}}
Push-Location $out
try {
    & cl.exe /nologo /std:c++20 /EHsc /Od /Zi /RTC1 /MT /DWIN32 /DVALVE_DLL /D_CRT_SECURE_NO_WARNINGS `
        "/I$sourceRoot/game/shared" "/I$sourceRoot/game/shared/ms" "/I$sourceRoot/public" "/I$sourceRoot/public/engine" "/I$sourceRoot/common" "/I$sourceRoot/game/client/ui/ms" `
        (Join-Path $testRoot 'equipment_tests.cpp') "$sourceRoot/game/shared/ms/stackstring.cpp" /Fe:equipment_tests.exe
    if($LASTEXITCODE -ne 0){throw 'Equipment test build failed'}
    & './equipment_tests.exe'
    if($LASTEXITCODE -ne 0){throw 'Equipment tests failed'}
    & cl.exe /nologo /std:c++20 /EHsc /Od /Zi /RTC1 /MT "/I$sourceRoot/game/client/ui/ms" `
        (Join-Path $testRoot 'atlas_tests.cpp') /Fe:atlas_tests.exe
    if($LASTEXITCODE -ne 0){throw 'Atlas test build failed'}
    & './atlas_tests.exe' $runtimeRoot
    if($LASTEXITCODE -ne 0){throw 'Atlas tests failed'}
    & cl.exe /nologo /std:c++20 /EHsc /Od /Zi /RTC1 /MT /DWIN32 /D_CRT_SECURE_NO_WARNINGS `
        "/I$sourceRoot/game/shared" "/I$sourceRoot/game/shared/ms" "/I$sourceRoot/public" "/I$sourceRoot/public/engine" "/I$sourceRoot/common" `
        (Join-Path $testRoot 'initialization_tests.cpp') "$sourceRoot/game/shared/ms/stackstring.cpp" /Fe:initialization_tests.exe
    if($LASTEXITCODE -ne 0){throw 'Initialization test build failed'}
    & './initialization_tests.exe'
    if($LASTEXITCODE -ne 0){throw 'Initialization tests failed'}
} finally {Pop-Location}
