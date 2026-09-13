param([string]$Destination = [Environment]::GetFolderPath('Desktop'))
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$launcher = Join-Path $root 'MSR-Launcher.exe'
if (!(Test-Path -LiteralPath $launcher -PathType Leaf)) { throw 'Missing MSR-Launcher.exe. Extract the complete package first.' }
$entries = @(
    @{Name='MSR'; Arguments=''; Description='Open MSR: join a realm, play locally, or use Dungeon Master controls.'},
    @{Name='MSR - Join Realm One'; Arguments='--realm one'; Description='Join MSR Realm One.'},
    @{Name='MSR - Join Realm Two'; Arguments='--realm two'; Description='Join MSR Realm Two with the same character profile.'},
    @{Name='MSR - Dungeon Master'; Arguments='--dm'; Description='Manage Dungeon Master permissions on realms hosted on this PC.'}
)
New-Item -ItemType Directory -Path $Destination -Force | Out-Null
$shell = New-Object -ComObject WScript.Shell
try {
    foreach ($entry in $entries) {
        $shortcut = $shell.CreateShortcut((Join-Path $Destination ($entry.Name + '.lnk')))
        try {
            $shortcut.TargetPath = $launcher
            $shortcut.Arguments = $entry.Arguments
            $shortcut.WorkingDirectory = $root
            $shortcut.IconLocation = (Join-Path $root 'Portable-Package\game\xash3d.exe') + ',0'
            $shortcut.Description = $entry.Description
            $shortcut.Save()
        } finally { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($shortcut) }
    }
    foreach ($legacy in @(@{Name='MSR - Enhanced'; File='Play-Enhanced.cmd'}, @{Name='MSR - Stable Base'; File='Play-Stable.cmd'})) {
        $oldPath = Join-Path $Destination ($legacy.Name + '.lnk')
        if (!(Test-Path -LiteralPath $oldPath -PathType Leaf)) { continue }
        $oldShortcut = $shell.CreateShortcut($oldPath)
        try { $owned = $oldShortcut.TargetPath -ieq $launcher -or $oldShortcut.TargetPath -ieq (Join-Path $root $legacy.File) }
        finally { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($oldShortcut) }
        if ($owned) {
            $backup = Join-Path $root ('Recovery\Desktop-Shortcut-Backups\' + [guid]::NewGuid().ToString('N'))
            New-Item -ItemType Directory -Path $backup -Force | Out-Null
            Copy-Item -LiteralPath $oldPath -Destination (Join-Path $backup ($legacy.Name + '.lnk'))
            Remove-Item -LiteralPath $oldPath
        }
    }
} finally { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($shell) }
Write-Host ('Created MSR and three direct-access shortcuts in ' + $Destination)
Write-Host 'Run this again if you move the game folder.'