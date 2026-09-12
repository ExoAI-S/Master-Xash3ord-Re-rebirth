param([string]$Destination = [Environment]::GetFolderPath('Desktop'))
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$entries = @(
    @{Name='MSR - Join Realm One'; File='Play-Realm-One.cmd'; Description='Join the shared Internet realm with Enhanced graphics and DM support'},
    @{Name='MSR - Join Realm Two'; File='Play-Realm-Two.cmd'; Description='Join the second shared Internet realm using the same character profile'},
    @{Name='MSR - Enhanced'; File='Play-Enhanced.cmd'; Description='Host your own local FN realms and play Enhanced'},
    @{Name='MSR - Stable Base'; File='Play-Stable.cmd'; Description='Host your own local FN realms and play the preserved Stable game'},
    @{Name='MSR - Dungeon Master'; File='Dungeon-Master.cmd'; Description='Manage Dungeon Master permissions on realms hosted on this PC'}
)
foreach ($entry in $entries) {
    if (!(Test-Path -LiteralPath (Join-Path $root $entry.File) -PathType Leaf)) {
        throw ('Missing ' + $entry.File + '. Extract the entire ZIP before creating shortcuts.')
    }
}
if (!(Test-Path -LiteralPath $Destination -PathType Container)) {
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
}
$shell = New-Object -ComObject WScript.Shell
foreach ($entry in $entries) {
    $shortcut = $shell.CreateShortcut((Join-Path $Destination ($entry.Name + '.lnk')))
    $shortcut.TargetPath = Join-Path $root $entry.File
    $shortcut.WorkingDirectory = $root
    $shortcut.IconLocation = (Join-Path $root 'Portable-Package\game\xash3d.exe') + ',0'
    $shortcut.Description = $entry.Description
    $shortcut.Save()
}
Write-Host ('Created five MSR shortcuts in ' + $Destination)
Write-Host 'Use Join Realm One or Join Realm Two to play on the shared Internet realms.'
Write-Host 'If you move this folder later, run this shortcut creator again.'
