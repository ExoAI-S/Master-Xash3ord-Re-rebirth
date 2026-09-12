$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot

try {
    & (Join-Path $root 'Host.ps1') -Action Start
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & (Join-Path $root 'Host.ps1') -Action Browse
    exit $LASTEXITCODE
}
catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    Read-Host 'Press Enter to close'
    exit 1
}
