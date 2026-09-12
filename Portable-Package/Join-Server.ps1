param([string]$Address)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
if (!$Address) {
    Write-Host '1. MSR Realm One - schmidt-council.tun.ply.gg:48715'
    Write-Host '2. MSR Realm Two - schmidt-once.tun.ply.gg:63800'
    Write-Host '3. Another LAN or Internet server'
    $selection = Read-Host 'Choose 1, 2, or 3'
    $Address = switch ($selection) {
        '1' { 'schmidt-council.tun.ply.gg:48715' }
        '2' { 'schmidt-once.tun.ply.gg:63800' }
        '3' { Read-Host 'Game server address (hostname-or-IP:port)' }
        default { throw 'Choose 1, 2, or 3.' }
    }
}
if ($Address -notmatch '^[a-zA-Z0-9.-]+:[0-9]{1,5}$') {
    throw 'Enter a hostname or IPv4 address followed by :port.'
}
$port = [int]($Address.Split(':')[-1])
if ($port -lt 1024 -or $port -gt 65535) { throw 'Invalid game port.' }
$bundle = Split-Path -Parent $root
$runtimeName = Split-Path -Leaf $root
$otherName = switch ($runtimeName) { 'Portable-Package' { 'Stable-Base' }; 'Stable-Base' { 'Portable-Package' } }
$runtimePaths = @((Join-Path $root 'game\xash3d.exe'))
if ($otherName) { $runtimePaths += Join-Path $bundle ($otherName + '\game\xash3d.exe') }
foreach ($process in Get-CimInstance Win32_Process -Filter "Name = 'xash3d.exe'") {
    if ($runtimePaths -contains $process.ExecutablePath -and $process.CommandLine -notmatch '(^|\s)-dedicated(\s|$)') {
        throw 'Close the current MSR game window first, then use the realm launcher. Your session has not been interrupted.'
    }
}
$path = Join-Path $root 'player-profile.json'
# The Stable and Enhanced clients use one identity when either version has already played.
$otherPath = if ($otherName) { Join-Path $bundle ($otherName + '\player-profile.json') } else { $null }
if ($otherPath -and (Test-Path -LiteralPath $otherPath -PathType Leaf)) {
    $otherProfile = Get-Content -LiteralPath $otherPath -Raw | ConvertFrom-Json
    if ($otherProfile.profile_key -cnotmatch '^[0-9a-f]{32}$') { throw 'The other version has an invalid player profile; restore its backup.' }
    if (!(Test-Path -LiteralPath $path)) { Copy-Item -LiteralPath $otherPath -Destination $path }
    else {
        $currentProfile = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
        if ($currentProfile.profile_key -cne $otherProfile.profile_key) {
            throw 'Stable and Enhanced have different player identities. Keep both profile files and restore the intended profile before joining.'
        }
    }
}
if (!(Test-Path -LiteralPath $path)) {
    $bytes = New-Object byte[] 16
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    @{profile_key=([BitConverter]::ToString($bytes)).Replace('-','').ToLowerInvariant()} | ConvertTo-Json | Set-Content -LiteralPath $path -Encoding UTF8
}
$profile = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
if ($profile.profile_key -cnotmatch '^[0-9a-f]{32}$') { throw 'Invalid player profile; restore your backup.' }
$game = Join-Path $root 'game'
@(
    ('setinfo _fnid "' + $profile.profile_key + '"')
    'password ""'
    'exec masterpiece.cfg'
    'ms_invtype "1"'
    'ms_alpha_inventory "1"'
    ('connect ' + $Address)
) | Set-Content -LiteralPath (Join-Path $game 'msr/private_join.cfg') -Encoding ASCII
Write-Host ('Joining ' + $Address)
Start-Process -FilePath (Join-Path $game 'xash3d.exe') -WorkingDirectory $game -ArgumentList '-game msr -port 27026 -console -log client.log +exec private_join.cfg'
