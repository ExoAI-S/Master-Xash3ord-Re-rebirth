# Server-only reload benchmark: start the sandbox realm with a short unload time, let the
# empty regions unload, then reload each one over rcon and print the MSR timing lines.
param([string]$Name = 'bench', [int]$UnloadSeconds = 10, [string[]]$Regions = @('thornlands', 'thornlands_north', 'edanasewers'), [switch]$Ahead)
$ErrorActionPreference = 'Stop'
$Regions = @($Regions | ForEach-Object { $_ -split ',' } | Where-Object { $_ })   # 'a,b' via powershell -File arrives as one string
$w = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$sb = "$w\sandbox\game"; $logs = "$w\sandbox\logs"
powershell -NoProfile -ExecutionPolicy Bypass -File "$w\Stop-BigWorld-Test.ps1" | Out-Null
$args = @('-dedicated', '-console', '-log', 'bwserver', '-bigworld', '-game', 'msr', '-port', '27199', '+ip', '127.0.0.1',
    '+maxplayers', '4', '+sv_lan', '1', '+public', '0', '+exec', 'server_sandbox.cfg', '+ms_region_unload_time', "$UnloadSeconds", '+map', 'edana')
$s = Start-Process -FilePath "$sb\xash3d.exe" -ArgumentList $args -WorkingDirectory $sb -PassThru -WindowStyle Minimized
Start-Sleep ([Math]::Max(45, $UnloadSeconds + 35))   # map load plus every region's unload
$pw = (Get-Content "$w\sandbox\rcon.txt").Trim()
$rcon = "import importlib.util,sys; spec=importlib.util.spec_from_file_location('gq', r'C:\MSR\Portable-Package\FN\game_query.py'); gq=importlib.util.module_from_spec(spec); spec.loader.exec_module(gq); print(gq.rcon(27199, sys.argv[1], sys.argv[2]))"
$ErrorActionPreference = 'Continue' # rcon to a crashed server must not abort log collection
try {
    if (-not $s.HasExited) {
        python -c $rcon $pw 'status' 2>$null | Out-Null # the first rcon after start-up can be lost
        Start-Sleep 1
        foreach ($r in $Regions) { if (-not $s.HasExited) { python -c $rcon $pw "msr_region_load $r$(if ($Ahead) { ' ahead' })" 2>$null | Out-Null; Start-Sleep 4 } }
        if (-not $s.HasExited) { python -c $rcon $pw 'msr_regions' 2>$null | Where-Object { $_ -match '^region|^edicts' } | ForEach-Object { $_ -replace '\| title.*$', '' } }
    }
    if ($s.HasExited) { 'SERVER EXITED' }
} finally {
    powershell -NoProfile -ExecutionPolicy Bypass -File "$w\Stop-BigWorld-Test.ps1" | Out-Null
    Start-Sleep 1
    if (Test-Path "$sb\bwserver.log") { Copy-Item "$sb\bwserver.log" "$logs\$Name-server.log" -Force }
}
Select-String -Path "$logs\$Name-server.log" -Pattern '^MSR: (region .* (loaded|unloaded|load time|slowest|ran its))|walk-through|slow server frame|^MSR: recorded|Host_Error|late precache' | ForEach-Object { $_.Line }
