# Start a second, player-less realm on its own port, let the map's spawners run, then save
# entity_info (every live entity with class/origin/model) for comparison. Only stops the
# server it started, so a playtest on 27199 keeps running.
param([Parameter(Mandatory)][string]$Map, [string]$Out, [int]$Seconds = 75, [int]$Port = 27198, [string[]]$ServerArgs = @('-bigworld'))
$ErrorActionPreference = 'Stop'
$w = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$sb = "$w\sandbox\game"
if (-not $Out) { $Out = "$w\analysis\spawn-census-$Map.txt" }
$args = @('-dedicated', '-console', '-log', "bwcensus$Port") + $ServerArgs + @('-game', 'msr', '-port', "$Port", '+ip', '127.0.0.1',
    '+maxplayers', '4', '+sv_lan', '1', '+public', '0', '+exec', 'server_sandbox.cfg', '+map', $Map)
$s = Start-Process -FilePath "$sb\xash3d.exe" -ArgumentList $args -WorkingDirectory $sb -PassThru -WindowStyle Minimized
try {
    Start-Sleep $Seconds
    if ($s.HasExited) { throw "census server for $Map exited early" }
    python "$w\tools\live_npcs.py" $Port $Out
} finally {
    if (-not $s.HasExited) { Stop-Process -Id $s.Id -Force }
}
