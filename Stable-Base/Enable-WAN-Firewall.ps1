$ErrorActionPreference = 'Stop'
$resultPath = Join-Path $PSScriptRoot 'logs\firewall-result.json'
try {
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (!$principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run Enable-WAN-Firewall.cmd as Administrator.'
}
$game = Join-Path $PSScriptRoot 'game\xash3d.exe'
if (!(Test-Path -LiteralPath $game)) { throw 'game\xash3d.exe is missing.' }
$ruleName = 'Master Sword Rebirth - Public Realms'
Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule
New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow -Protocol UDP -LocalPort 27025,27035 -Program $game -Profile Any | Out-Null
Write-Host 'Windows Firewall now allows UDP 27025 and 27035 for both public MSR realms.'
Write-Host 'Forward UDP 27025 and 27035 in your router to this PC to accept WAN players.'
@{success=$true; rule=$ruleName; ports=@(27025,27035)} | ConvertTo-Json | Set-Content -LiteralPath $resultPath
} catch {
    @{success=$false; error=$_.Exception.Message} | ConvertTo-Json | Set-Content -LiteralPath $resultPath
    throw
}
