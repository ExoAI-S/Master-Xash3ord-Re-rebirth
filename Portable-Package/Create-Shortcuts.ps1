param([string]$Destination = [Environment]::GetFolderPath('Desktop'))
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
if (!(Test-Path -LiteralPath $Destination -PathType Container)) {
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
}
$entries = @(
    @{Name='Master Sword - Steam Independent'; Launcher='Browse-Servers.cmd'; Description='Start your own two realms and browse servers'},
    @{Name='Master Sword - Join a Server'; Launcher='Join-Server.cmd'; Description='Join a LAN or Internet realm by address'},
    @{Name='Master Sword - Start Realms'; Launcher='Start-Host.cmd'; Description='Host two realms with shared FN character storage'},
    @{Name='Master Sword - Stop Realms'; Launcher='Stop-Host.cmd'; Description='Save and stop your own realms and FN'}
)
$shell = New-Object -ComObject WScript.Shell
foreach ($entry in $entries) {
    $target = Join-Path $root $entry.Launcher
    if (!(Test-Path -LiteralPath $target -PathType Leaf)) { throw "Missing launcher: $target. Extract the whole ZIP first." }
    $shortcut = $shell.CreateShortcut((Join-Path $Destination ($entry.Name + '.lnk')))
    $shortcut.TargetPath = $target
    $shortcut.WorkingDirectory = $root
    $shortcut.IconLocation = (Join-Path $root 'game\xash3d.exe') + ',0'
    $shortcut.Description = $entry.Description
    $shortcut.Save()
}
Write-Host "Created four Master Sword shortcuts in $Destination"
Write-Host 'To join someone else, use Master Sword - Join a Server.'
