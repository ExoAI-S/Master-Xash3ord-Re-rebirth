param(
    [ValidateSet('Release', 'RelWithDebInfo', 'Debug')]
    [string]$Configuration = 'Release',
    [string]$BuildDirectory = 'build-msr-local'
)

$ErrorActionPreference = 'Stop'

$sourceRoot = Split-Path -Parent $PSScriptRoot
$buildRoot = Join-Path $sourceRoot $BuildDirectory
$vcpkgToolchain = Join-Path $sourceRoot 'external\vcpkg\scripts\buildsystems\vcpkg.cmake'
$sharedInstalled = Join-Path $sourceRoot 'build-msr\vcpkg_installed'

function Find-Tool([string]$Name, [string[]]$Candidates) {
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }

    foreach ($candidate in $Candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    throw "Unable to find $Name. Install it or add it to PATH."
}

$cmake = Find-Tool 'cmake.exe' @(
    (Join-Path $env:ProgramFiles 'CMake\bin\cmake.exe'),
    (Join-Path $env:USERPROFILE 'Documents\Codex\2026-09-10\https-github-com-msrevive-masterswordrebirth-https\work\toolchain\cmake-4.4.3-windows-x86_64\bin\cmake.exe')
)
$ninja = Find-Tool 'ninja.exe' @(
    (Join-Path $env:USERPROFILE 'Documents\Codex\2026-09-10\https-github-com-msrevive-masterswordrebirth-https\work\toolchain\ninja\ninja.exe')
)

$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
if (!(Test-Path -LiteralPath $vswhere)) {
    throw 'Visual Studio Build Tools were not found.'
}

$vsRoot = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (!$vsRoot) {
    # vswhere may hide a usable installation while its installer is incomplete.
    $vsRoot = & $vswhere -latest -all -products '*' -property installationPath
}
$vsRoot = @($vsRoot)[0]
$vcvars = Join-Path $vsRoot 'VC\Auxiliary\Build\vcvarsall.bat'
if (!(Test-Path -LiteralPath $vcvars)) {
    throw 'The x86 MSVC environment script was not found.'
}

# Import vcvarsall's environment into this PowerShell process without tying the
# generated CMake cache to the machine where the handoff archive was created.
$environmentLines = & $env:ComSpec /d /s /c "`"$vcvars`" x86 >nul && set"
foreach ($line in $environmentLines) {
    $separator = $line.IndexOf('=')
    if ($separator -gt 0) {
        [Environment]::SetEnvironmentVariable(
            $line.Substring(0, $separator),
            $line.Substring($separator + 1),
            'Process'
        )
    }
}

$configure = @(
    '-S', $sourceRoot,
    '-B', $buildRoot,
    '-G', 'Ninja',
    "-DCMAKE_MAKE_PROGRAM=$ninja",
    "-DCMAKE_BUILD_TYPE=$Configuration",
    "-DCMAKE_TOOLCHAIN_FILE=$vcpkgToolchain",
    '-DVCPKG_TARGET_TRIPLET=x86-windows',
    '-DBUILD_CLIENT=OFF',
    '-DBUILD_SERVER=OFF',
    '-DBUILD_UTILS=OFF',
    '-DBUILD_GAME_LAUNCHER=OFF',
    '-DBUILD_MSR_PORT=ON',
    '-DENABLE_PHYSX=OFF',
    '-DGAMEDIR=msr'
)

if (Test-Path -LiteralPath $sharedInstalled) {
    $configure += "-DVCPKG_INSTALLED_DIR=$sharedInstalled"
}

& $cmake @configure
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $cmake --build $buildRoot --target msr_client msr_server --parallel
exit $LASTEXITCODE
