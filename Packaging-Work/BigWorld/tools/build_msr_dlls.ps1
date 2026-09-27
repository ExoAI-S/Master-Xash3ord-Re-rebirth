# Build MSR's game DLLs (ms.dll, client.dll) from MSR-BigWorld\src with the
# same toolchain the shipped Debug DLLs were built with (VS 18 Build Tools x86,
# CMake 4.4.3, Ninja). vcpkg dependencies are reused from build-bw\vcpkg_installed,
# so nothing is downloaded.
param(
    [string]$BuildDirectory = 'build-bw',
    [switch]$Reconfigure
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$src = Join-Path $root 'src'
$build = Join-Path $src $BuildDirectory
$toolchainDir = 'C:\Users\cptki\Documents\Codex\2026-09-10\https-github-com-msrevive-masterswordrebirth-https\work\toolchain'
$cmake = Join-Path $toolchainDir 'cmake-4.4.3-windows-x86_64\bin\cmake.exe'
$ninja = Join-Path $toolchainDir 'ninja\ninja.exe'
$vcvars = 'C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvarsall.bat'
foreach ($p in $cmake, $ninja, $vcvars) { if (-not (Test-Path $p)) { throw "missing tool: $p" } }

foreach ($line in (& $env:ComSpec /d /s /c "`"$vcvars`" x86 >nul && set")) {
    $i = $line.IndexOf('=')
    if ($i -gt 0) { [Environment]::SetEnvironmentVariable($line.Substring(0, $i), $line.Substring($i + 1), 'Process') }
}

if ($Reconfigure -or -not (Test-Path (Join-Path $build 'build.ninja'))) {
    & $cmake -S $src -B $build -G Ninja "-DCMAKE_MAKE_PROGRAM=$ninja" '-DCMAKE_BUILD_TYPE=Debug' `
        "-DCMAKE_TOOLCHAIN_FILE=$src\external\vcpkg\scripts\buildsystems\vcpkg.cmake" `
        '-DVCPKG_TARGET_TRIPLET=x86-windows' '-DVCPKG_MANIFEST_INSTALL=OFF' "-DVCPKG_INSTALLED_DIR=$build\vcpkg_installed" `
        '-DVCPKG_APPLOCAL_DEPS=OFF' `
        '-DBUILD_CLIENT=OFF' '-DBUILD_SERVER=OFF' '-DBUILD_UTILS=OFF' '-DBUILD_GAME_LAUNCHER=OFF' `
        '-DBUILD_MSR_PORT=ON' '-DENABLE_PHYSX=OFF' '-DGAMEDIR=msr' '-DMSR_NATIVE_EVENT_PILOT=OFF'
    if ($LASTEXITCODE) { throw "configure failed ($LASTEXITCODE)" }
}
& $cmake --build $build --parallel
if ($LASTEXITCODE) { throw "build failed ($LASTEXITCODE)" }
Get-ChildItem (Join-Path $build 'Debug\msr\bin') -Include ms.dll, client.dll -Recurse | Select-Object FullName, Length, LastWriteTime
