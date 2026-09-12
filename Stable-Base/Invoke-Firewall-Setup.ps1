$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (!$principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    $shellPath = (Get-Process -Id $PID).Path
    $scriptPath = Join-Path $root 'Invoke-Firewall-Setup.ps1'
    Write-Host 'Windows will request administrator permission to allow this game host through the firewall.'
    $process = Start-Process -FilePath $shellPath -Verb RunAs -WindowStyle Hidden -Wait -PassThru -ArgumentList ('-NoProfile -File "' + $scriptPath + '"')
    exit $process.ExitCode
}
New-Item -ItemType Directory -Force -Path (Join-Path $root 'logs') | Out-Null
& (Join-Path $root 'Enable-WAN-Firewall.ps1')
