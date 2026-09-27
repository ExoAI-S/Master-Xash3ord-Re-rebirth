$ErrorActionPreference='Stop'
$packageRoot=Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
& (Join-Path $packageRoot 'MSR-Launcher.exe') --host-action start
