param(
    [ValidateSet('Start','Stop','Status','Play','Browse')][string]$Action = 'Status',
    [ValidateRange(1024,65525)][int]$FirstPort = 27025,
    [string]$Bind = '0.0.0.0'
)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
try { $hostLock = [IO.File]::Open((Join-Path $root 'host.lock'), 'OpenOrCreate', 'ReadWrite', 'None') }
catch { throw 'Another host command is still running. Wait for it to finish.' }

try {
$python = Join-Path $root 'runtime\python.exe'
$game = Join-Path $root 'game'
$statePath = Join-Path $root 'host-state.json'
$settingsPath = Join-Path $root 'host-settings.json'
$queryScript = Join-Path $root 'FN\game_query.py'
$fnConfig = Get-Content -LiteralPath (Join-Path $root 'FN\config.json') -Raw | ConvertFrom-Json
$healthUrl = 'http://127.0.0.1:' + $fnConfig.port + '/health'
$playitRoot = Join-Path $root '.host-private\playit'
$playitExe = Join-Path $playitRoot 'playit-portable.exe'
$playitSecret = Join-Path $playitRoot 'playit-agent.key'
$playitStatePath = Join-Path $playitRoot 'agent-state.json'
if ($fnConfig.bind -ne '127.0.0.1') { throw 'FN must remain on 127.0.0.1; public game servers reach it locally.' }

function New-Secret {
    $buffer = New-Object byte[] 24
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($buffer) } finally { $rng.Dispose() }
    ([BitConverter]::ToString($buffer)).Replace('-','').ToLowerInvariant()
}
function Read-State {
    if (Test-Path -LiteralPath $statePath) { Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json }
}
function Get-OwnedProcess($record) {
    if ($null -eq $record) { return $null }
    $process = Get-Process -Id $record.id -ErrorAction SilentlyContinue
    if ($null -eq $process) { return $null }
    try {
        if ($process.Path -ne $record.path -or $process.StartTime.ToUniversalTime().Ticks.ToString() -ne $record.startTicks) { return $null }
    } catch { return $null }
    $process
}
function Process-Record($process) {
    $processPath = $null
    for ($attempt=0; $attempt -lt 20; $attempt++) {
        try { $process.Refresh(); $processPath = $process.Path } catch { $processPath = $null }
        if ($processPath) { break }
        Start-Sleep -Milliseconds 100
    }
    if (!$processPath) { throw ('Could not verify the path for process ' + $process.Id + '.') }
    @{id=$process.Id; path=$processPath; startTicks=$process.StartTime.ToUniversalTime().Ticks.ToString()}
}
function Read-PlayitState {
    if (Test-Path -LiteralPath $playitStatePath) { Get-Content -LiteralPath $playitStatePath -Raw | ConvertFrom-Json }
}
function Start-Playit {
    if (!(Test-Path -LiteralPath $playitExe -PathType Leaf) -or !(Test-Path -LiteralPath $playitSecret -PathType Leaf)) { return $false }
    $existing = Get-OwnedProcess (Read-PlayitState)
    if ($existing) { return $true }
    New-Item -ItemType Directory -Force -Path (Join-Path $root 'logs') | Out-Null
    $arguments = '--stdout --secret_path="' + $playitSecret + '" start'
    $process = Start-Process -FilePath $playitExe -ArgumentList $arguments -WorkingDirectory $playitRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $root 'logs\playit-stdout.log') -RedirectStandardError (Join-Path $root 'logs\playit-stderr.log')
    (Process-Record $process) | ConvertTo-Json | Set-Content -LiteralPath $playitStatePath -Encoding UTF8
    Start-Sleep -Milliseconds 750
    if ($process.HasExited) { throw 'The private Playit agent stopped during startup. See logs/playit-stderr.log.' }
    return $true
}
function Stop-Playit {
    $process = Get-OwnedProcess (Read-PlayitState)
    if ($process) { Stop-Process -Id $process.Id }
    if (Test-Path -LiteralPath $playitStatePath) { Remove-Item -LiteralPath $playitStatePath }
}
function Get-GameRecords($hostState) {
    if ($null -eq $hostState) { return @() }
    if ($hostState.games) { return @($hostState.games) }
    if ($hostState.game) { return @(@{id='legacy'; port=[int]$hostState.port; hostname='Legacy server'; process=$hostState.game}) }
    @()
}
function Get-LiveRealmProcesses($servers) {
    # The ownership record is deliberately strict, but failure to verify it does
    # not prove that a server exited. Independently check the executable and the
    # configured dedicated-server ports before discarding state or stopping FN.
    $ports = @($servers | ForEach-Object { [int]$_.port })
    $gameExe = [IO.Path]::GetFullPath((Join-Path $game 'xash3d.exe'))
    foreach ($candidate in @(Get-CimInstance Win32_Process -Filter "Name = 'xash3d.exe'" -ErrorAction Stop)) {
        if (!$candidate.ExecutablePath -or ![string]::Equals($candidate.ExecutablePath, $gameExe, [StringComparison]::OrdinalIgnoreCase)) { continue }
        $commandLine = [string]$candidate.CommandLine
        if ($commandLine -notmatch '(?i)(?:^|\s)-dedicated(?=\s|$)') { continue }
        if ($commandLine -notmatch '(?i)(?:^|\s)-port\s+"?([0-9]+)"?(?=\s|$)') { continue }
        $port = [int]$Matches[1]
        if ($ports -contains $port) { [PSCustomObject]@{ id=[int]$candidate.ProcessId; port=$port } }
    }
}
function Assert-NoUntrackedRealms($servers, $ownedGames) {
    $ownedIds = @($ownedGames | ForEach-Object { [int]$_.process.id })
    $untracked = @(Get-LiveRealmProcesses $servers | Where-Object { $ownedIds -notcontains $_.id })
    if ($untracked.Count) {
        $details = @($untracked | ForEach-Object { 'UDP ' + $_.port + ' (PID ' + $_.id + ')' }) -join ', '
        throw ('Existing dedicated server ownership could not be verified: ' + $details + '. No replacement servers were started; existing state is retained.')
    }
}
function Assert-RealmsStopped($servers) {
    $remaining = @(Get-LiveRealmProcesses $servers)
    if ($remaining.Count) {
        $details = @($remaining | ForEach-Object { 'UDP ' + $_.port + ' (PID ' + $_.id + ')' }) -join ', '
        throw ('Dedicated servers are still running: ' + $details + '. FN and host state remain intact to protect saves. Unverified processes were not terminated.')
    }
}
function Test-FN {
    try {
        $response = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
        ($response.data.service -eq 'FN' -and $response.data.private -eq $true)
    } catch { $false }
}
function Read-OrCreateSettings {
    $existing = $null
    if (Test-Path -LiteralPath $settingsPath) {
        $existing = Get-Content -LiteralPath $settingsPath -Raw | ConvertFrom-Json
        if ($existing.servers -and @($existing.servers).Count -eq 2) { return $existing }
    }
    $firstRcon = if ($existing -and $existing.rcon_password) { [string]$existing.rcon_password } else { New-Secret }
    @{
        version=2; public=$true; servers=@(
            @{id='realm-one'; hostname='[FN] MSR Realm One'; port=$FirstPort; map='edana'; maxplayers=10; rcon_password=$firstRcon},
            @{id='realm-two'; hostname='[FN] MSR Realm Two'; port=($FirstPort+10); map='edana'; maxplayers=10; rcon_password=(New-Secret)}
        )
    } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $settingsPath -Encoding UTF8
    Get-Content -LiteralPath $settingsPath -Raw | ConvertFrom-Json
}
function Test-ServerSetting($server) {
    if ($server.id -cnotmatch '^[a-z0-9-]+$') { throw 'Invalid server id.' }
    if ([string]::IsNullOrWhiteSpace($server.hostname) -or $server.hostname -match '["\r\n;]') { throw 'Invalid server hostname.' }
    if ($server.map -cnotmatch '^[A-Za-z0-9_-]+$') { throw 'Invalid map name.' }
    if ([int]$server.port -lt 1024 -or [int]$server.port -gt 65535) { throw 'Invalid server port.' }
    if ([int]$server.maxplayers -lt 1 -or [int]$server.maxplayers -gt 32) { throw 'Invalid maxplayers value.' }
    if ([string]::IsNullOrWhiteSpace($server.rcon_password) -or $server.rcon_password -match '["\r\n;]') { throw 'Invalid RCON password.' }
    if (!(Test-Path -LiteralPath (Join-Path $game ('msr\maps\' + $server.map + '.bsp')))) { throw ('Missing map: ' + $server.map) }
}
function Invoke-ServerQuery($verb, $server, [string]$command='status', [switch]$quiet) {
    $queryArgs = @($queryScript,$verb,'--port',[string]$server.port,'--settings',$settingsPath)
    if ($server.id -ne 'legacy') { $queryArgs += @('--server-id',[string]$server.id) }
    if ($verb -eq 'rcon') { $queryArgs += @('--command',$command) }
    if ($quiet) { $queryArgs += '--quiet' }
    & $python @queryArgs
}

$state = Read-State
if ($Action -eq 'Start') {
    [void][Net.IPAddress]::Parse($Bind)
    & $python (Join-Path $root 'FN\check_content.py')
    if ($LASTEXITCODE -ne 0) { throw 'FN content validation failed. The host will not start with disconnected character persistence.' }
    $settings = Read-OrCreateSettings
    $ownedGames = @(Get-GameRecords $state | Where-Object { Get-OwnedProcess $_.process })
    Assert-NoUntrackedRealms $settings.servers $ownedGames
    $playitRunning = Start-Playit
    if ($ownedGames.Count) {
        Write-Host 'The public MSR servers are already running. Use Status-Host.cmd.'
        if ($playitRunning) { Write-Host 'Private Playit Internet tunnels are running.' }
        exit 0
    }
    foreach ($server in @($settings.servers)) {
        Test-ServerSetting $server
        if (Get-NetUDPEndpoint -LocalPort ([int]$server.port) -ErrorAction SilentlyContinue) { throw ('UDP port ' + $server.port + ' is already in use.') }
    }
    New-Item -ItemType Directory -Force -Path (Join-Path $root 'logs') | Out-Null
    $fnProcess = Get-OwnedProcess $state.fn
    if (!$fnProcess) {
        if (Test-FN) { throw 'FN port is occupied by another service.' }
        $fnArgs = '"' + (Join-Path $root 'FN\fn_server.py') + '" serve'
        $fnProcess = Start-Process -FilePath $python -ArgumentList $fnArgs -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $root 'logs\FN-stdout.log') -RedirectStandardError (Join-Path $root 'logs\FN-stderr.log')
    }
    $state = @{fn=(Process-Record $fnProcess); games=@()}
    $state | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $statePath -Encoding UTF8
    $ready = $false
    for ($attempt=0; $attempt -lt 40; $attempt++) {
        if (Test-FN) { $ready=$true; break }
        if ($fnProcess.HasExited) { throw 'FN stopped during startup. See logs/FN-stderr.log.' }
        Start-Sleep -Milliseconds 250
    }
    if (!$ready) { throw 'FN did not become ready.' }
    $approved = Get-Content -LiteralPath (Join-Path $root 'FN\content-manifest.json') -Raw | ConvertFrom-Json
    $validation = Invoke-RestMethod -Uri ('http://127.0.0.1:' + $fnConfig.port + '/api/v2/internal/sc/' + $approved.scripts_crc32) -TimeoutSec 3
    if ($validation.data -ne $true) { throw 'Running FN rejected the installed scripts. Restart FN after updating its approved manifest.' }
    foreach ($server in @($settings.servers)) {
        $cfgName = 'server_public_' + $server.id + '.cfg'
        @(
            'hostname "' + $server.hostname + '"'
            'sv_password none'
            'rcon_password "' + $server.rcon_password + '"'
            'sv_lan 0'
            'public 1'
            'ms_serverchar 3'
            'ms_central_enabled 1'
            'ms_central_addr "127.0.0.1:' + $fnConfig.port + '"'
            'ms_reset_if_empty 0'
            'ms_timelimit 0'
            'ms_dev_mode 0'
            'exec server_core.cfg'
        ) | Set-Content -LiteralPath (Join-Path $game ('msr\' + $cfgName)) -Encoding ASCII
        $arguments = '-dedicated -console -game msr -port ' + $server.port + ' +ip ' + $Bind + ' +maxplayers ' + $server.maxplayers + ' +sv_lan 0 +public 1 +exec ' + $cfgName + ' +map ' + $server.map
        $gameProcess = Start-Process -FilePath (Join-Path $game 'xash3d.exe') -ArgumentList $arguments -WorkingDirectory $game -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $root ('logs\'+$server.id+'-stdout.log')) -RedirectStandardError (Join-Path $root ('logs\'+$server.id+'-stderr.log'))
        $record = @{id=$server.id; port=[int]$server.port; map=[string]$server.map; hostname=[string]$server.hostname; process=(Process-Record $gameProcess)}
        $state.games += $record
        $state | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $statePath -Encoding UTF8
        $serverReady = $false
        for ($attempt=0; $attempt -lt 40; $attempt++) {
            if ($gameProcess.HasExited) { throw ($server.hostname + ' exited. See logs.') }
            Invoke-ServerQuery probe $server -quiet | Out-Null
            if ($LASTEXITCODE -eq 0) { $serverReady=$true; break }
            Start-Sleep -Milliseconds 500
        }
        if (!$serverReady) { throw ($server.hostname + ' did not answer on UDP ' + $server.port + '.') }
    }
    Write-Host 'Private FN and two password-free WAN game servers are running:'
    foreach ($server in @($settings.servers)) { Write-Host ('  '+$server.hostname+' - UDP '+$server.port+' - map '+$server.map) }
    if ($playitRunning) { Write-Host 'Private Playit Internet tunnels are running.' }
    Write-Host 'LAN uses UDP 27025 and 27035. Internet hosting requires your own router forwarding or UDP tunnel.'
} elseif ($Action -eq 'Stop') {
    $settings = if (Test-Path -LiteralPath $settingsPath) { Get-Content -LiteralPath $settingsPath -Raw | ConvertFrom-Json } else { $null }
    $failed = @()
    foreach ($record in @(Get-GameRecords $state)) {
        if (!(Get-OwnedProcess $record.process)) { continue }
        $queryServer = if ($record.id -eq 'legacy') { $record } else { @($settings.servers | Where-Object id -eq $record.id)[0] }
        Invoke-ServerQuery rcon $queryServer 'quit' | Out-Host
        for ($attempt=0; $attempt -lt 40; $attempt++) {
            if (!(Get-OwnedProcess $record.process)) { break }
            Start-Sleep -Milliseconds 250
        }
        if (Get-OwnedProcess $record.process) { $failed += $record.hostname }
    }
    if ($failed.Count) { throw ('Servers did not stop; FN remains running to protect saves: ' + ($failed -join ', ')) }
    Assert-RealmsStopped (@($settings.servers) + @(Get-GameRecords $state))
    $fnProcess = Get-OwnedProcess $state.fn
    if ($fnProcess) {
        & $python (Join-Path $root 'FN\fn_server.py') backup
        if ($LASTEXITCODE -ne 0) { throw 'Backup failed; FN remains running.' }
        Stop-Process -Id $fnProcess.Id
    }
    Stop-Playit
    if (Test-Path -LiteralPath $statePath) { Remove-Item -LiteralPath $statePath }
    Write-Host 'Public host stopped. FN characters are saved in FN/data.'
} elseif ($Action -eq 'Status') {
    Write-Host ('FN reachable: ' + (Test-FN))
    Write-Host ('Owned FN process: ' + [bool](Get-OwnedProcess $state.fn))
    Write-Host ('Private Playit agent: ' + [bool](Get-OwnedProcess (Read-PlayitState)))
    $settings = if (Test-Path -LiteralPath $settingsPath) { Get-Content -LiteralPath $settingsPath -Raw | ConvertFrom-Json } else { $null }
    foreach ($record in @(Get-GameRecords $state)) {
        $running = [bool](Get-OwnedProcess $record.process)
        Write-Host ($record.hostname+' on UDP '+$record.port+' running: '+$running)
        if ($running) {
            $queryServer = if ($record.id -eq 'legacy') { $record } else { @($settings.servers | Where-Object id -eq $record.id)[0] }
            Invoke-ServerQuery info $queryServer
            Invoke-ServerQuery probe $queryServer
        }
    }
} elseif ($Action -in @('Play','Browse')) {
    $records = @(Get-GameRecords $state)
    if (!$records.Count -or !(Get-OwnedProcess $records[0].process)) { throw 'Start the host with Start-Host.cmd first.' }
    $clientStatePath = Join-Path $root 'client-state.json'
    if (Test-Path -LiteralPath $clientStatePath) {
        $clientState = Get-Content -LiteralPath $clientStatePath -Raw | ConvertFrom-Json
        if (Get-OwnedProcess $clientState) { Write-Host 'The game is already open.'; exit 0 }
    }
    # Seed before the client loads its menu. Editing a live menu's file is unsafe:
    # closing that menu writes its cached list over the changes.
    $favoritePath = Join-Path $game 'msr\favorite_servers.lst'
    $favorites = @()
    if (Test-Path -LiteralPath $favoritePath) { $favorites = @(Get-Content -LiteralPath $favoritePath) }
    foreach ($record in $records) {
        $entry = '127.0.0.1:' + $record.port + ' 49'
        if ($favorites -notcontains $entry) { $favorites += $entry }
    }
    $favorites | Set-Content -LiteralPath $favoritePath -Encoding ASCII
    $profilePath = Join-Path $root 'player-profile.json'
    if (!(Test-Path -LiteralPath $profilePath)) { @{profile_key=(New-Secret).Substring(0,32)} | ConvertTo-Json | Set-Content -LiteralPath $profilePath -Encoding UTF8 }
    $profile = Get-Content -LiteralPath $profilePath -Raw | ConvertFrom-Json
    if ($profile.profile_key -cnotmatch '^[0-9a-f]{32}$') { throw 'Invalid player profile; restore its backup.' }
    @(
        'setinfo _fnid "'+$profile.profile_key+'"'
        'password ""'
        'exec masterpiece.cfg'
        'ms_invtype "1"'
        'ms_alpha_inventory "1"'
        $(if ($Action -eq 'Browse') { 'menu_internetgames' } else { 'connect 127.0.0.1:'+$records[0].port })
    ) | Set-Content -LiteralPath (Join-Path $game 'msr\private_join.cfg') -Encoding ASCII
    $clientProcess = Start-Process -FilePath (Join-Path $game 'xash3d.exe') -WorkingDirectory $game -ArgumentList '-game msr -port 27026 -console -log client.log +exec private_join.cfg' -PassThru
    (Process-Record $clientProcess) | ConvertTo-Json | Set-Content -LiteralPath $clientStatePath -Encoding UTF8
}
} finally { $hostLock.Dispose() }
