param([ValidateSet('Stable','Enhanced')][string]$Version, [switch]$Play)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$versions = @{Stable=(Join-Path $root 'Stable-Base'); Enhanced=(Join-Path $root 'Portable-Package')}
$statePath = Join-Path $root 'active-version.json'
$lock = [IO.File]::Open((Join-Path $root 'version-switch.lock'),'OpenOrCreate','ReadWrite','None')
$hostShell = (Get-Process -Id $PID).Path
function Invoke-VersionHost([string]$folder,[string]$action) {
    & $hostShell -NoProfile -File (Join-Path $folder 'Host.ps1') -Action $action
    if ($LASTEXITCODE -ne 0) { throw ('Host '+$action+' failed. The base and save backups remain intact.') }
}
function Initialize-NewVersionStores([string]$sourceFolder,[string]$targetFolder) {
    $sourceDb = Join-Path $sourceFolder 'FN\data\FN.sqlite3'
    $targetDb = Join-Path $targetFolder 'FN\data\FN.sqlite3'
    if (!(Test-Path -LiteralPath $sourceDb -PathType Leaf) -and (Test-Path -LiteralPath $targetDb -PathType Leaf)) {
        throw 'The current version has no FN database, but the selected version has saves. Launch the selected host directly with its Start-Host.cmd first; no existing saves were replaced.'
    }
    foreach ($folder in @($sourceFolder,$targetFolder)) {
        if (!(Test-Path -LiteralPath (Join-Path $folder 'FN\data\FN.sqlite3') -PathType Leaf)) {
            # The list command initializes a fresh schema and never starts a service.
            & (Join-Path $folder 'runtime\python.exe') (Join-Path $folder 'FN\fn_server.py') list | Out-Null
            if ($LASTEXITCODE -ne 0) { throw 'Could not initialize the new local FN database. Existing saves have not been transferred.' }
            if (!(Test-Path -LiteralPath (Join-Path $folder 'FN\data\FN.sqlite3') -PathType Leaf)) {
                throw 'FN did not create the expected local database. Check FN/config.json before switching.'
            }
        }
    }
}
try {
    if (!$Version) { throw 'Choose Stable or Enhanced.' }
    $current = if (Test-Path -LiteralPath $statePath) { (Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json).version } else { 'Enhanced' }
    if (!$versions.ContainsKey($current)) { throw 'Invalid active version record.' }
    $target = $versions[$Version]
    if (!(Test-Path -LiteralPath (Join-Path $target 'Host.ps1'))) { throw 'Selected version is missing.' }
    if ($Version -eq 'Stable') {
        & (Join-Path $target 'runtime\python.exe') (Join-Path $root 'Packaging-Work\verify_stable_base.py')
        if ($LASTEXITCODE -ne 0) { throw 'Stable base verification failed. Current game files and saves have not been changed.' }
    }
    # Refuse a switch while a client is open; closing the game finishes its save/disconnect.
    $clientPaths = @($versions.Values | ForEach-Object { Join-Path $_ 'game\xash3d.exe' })
    $runningVersions = @()
    foreach ($process in Get-CimInstance Win32_Process -Filter "Name = 'xash3d.exe'") {
        if ($clientPaths -contains $process.ExecutablePath -and $process.CommandLine -notmatch '(^|\s)-dedicated(\s|$)') {
            throw 'Close the game first, then switch versions. Your current session has not been interrupted.'
        }
        foreach ($entry in $versions.GetEnumerator()) {
            if ($process.ExecutablePath -eq (Join-Path $entry.Value 'game\xash3d.exe')) { $runningVersions += $entry.Key }
        }
    }
    $runningVersions = @($runningVersions | Select-Object -Unique)
    if ($runningVersions.Count -gt 1) { throw 'Both versions are running. Stop one host before switching save sets.' }
    if ($runningVersions.Count -eq 1) { $current = $runningVersions[0] }
    $source = $versions[$current]
    if ($current -ne $Version) {
        Invoke-VersionHost $source 'Stop'
        Initialize-NewVersionStores $source $target
        & (Join-Path $source 'runtime\python.exe') (Join-Path $root 'Packaging-Work\transfer_fn_state.py') $source $target (Join-Path $root 'Version-Backups')
        if ($LASTEXITCODE -ne 0) { throw 'Save transfer failed. The original version and backups remain intact.' }
    }
    Invoke-VersionHost $target 'Start'
    @{version=$Version; switched=(Get-Date).ToUniversalTime().ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding UTF8
    Write-Host ('Active version: '+$Version)
    if ($Play) { Invoke-VersionHost $target 'Play' }
} finally { $lock.Dispose() }

