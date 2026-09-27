param([ValidateSet('Release','RelWithDebInfo','Debug')][string]$Configuration='Debug')
& (Join-Path $PSScriptRoot 'Build-MSR-Port.ps1') -Configuration $Configuration
exit $LASTEXITCODE
