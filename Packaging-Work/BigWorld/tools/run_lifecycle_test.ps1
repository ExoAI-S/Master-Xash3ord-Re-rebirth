# Region unload/reload test: sandbox FN + dedicated realm (-bigworld, short unload time) +
# the scripted client from write_lifecycle_test_cfg.py, while polling msr_regions every few
# seconds into sandbox\logs\<Name>-timeline.txt. Stops everything afterwards.
param([string]$Name = 'lifecycle', [int]$UnloadSeconds = 15, [int]$ClientSeconds = 600, [int]$PollSeconds = 3)
$ErrorActionPreference = 'Stop'
$w = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$sb = "$w\sandbox\game"; $logs = "$w\sandbox\logs"
powershell -NoProfile -ExecutionPolicy Bypass -File "$w\Stop-BigWorld-Test.ps1" | Out-Null
$fn = Start-Process -FilePath python -ArgumentList "$w\sandbox\FN\fn_server.py", 'serve' -WorkingDirectory "$w\sandbox\FN" -PassThru -WindowStyle Hidden `
    -RedirectStandardOutput "$logs\fn-stdout.log" -RedirectStandardError "$logs\fn-stderr.log"
Start-Sleep 3
$serverArgList = @('-dedicated', '-console', '-log', 'bwserver', '-bigworld', '-game', 'msr', '-port', '27199', '+ip', '127.0.0.1',
    '+maxplayers', '4', '+sv_lan', '1', '+public', '0', '+exec', 'server_sandbox.cfg', '+ms_region_unload_time', "$UnloadSeconds", '+map', 'edana')
$s = Start-Process -FilePath "$sb\xash3d.exe" -ArgumentList $serverArgList -WorkingDirectory $sb -PassThru -WindowStyle Minimized
Start-Sleep 22
if ($s.HasExited) { throw 'dedicated server exited during startup' }
$pw = (Get-Content "$w\sandbox\rcon.txt").Trim()
$rcon = "import importlib.util,sys; spec=importlib.util.spec_from_file_location('gq', r'C:\MSR\Portable-Package\FN\game_query.py'); gq=importlib.util.module_from_spec(spec); spec.loader.exec_module(gq); print(gq.rcon(27199, sys.argv[1], sys.argv[2]))"
$timeline = "$logs\$Name-timeline.txt"
"test start $(Get-Date -Format HH:mm:ss)" | Set-Content -Encoding utf8 $timeline
$c = Start-Process -FilePath "$sb\xash3d.exe" -ArgumentList '-game', 'msr', '-log', '-window', '-width', '1280', '-height', '720', '-nosound', '-nomouse',
    '+exec', 'bigworld_test.cfg' -WorkingDirectory $sb -PassThru
$start = Get-Date
$ErrorActionPreference = 'Continue' # rcon to a crashed server must not abort log collection
try {
    while (-not $c.HasExited -and ((Get-Date) - $start).TotalSeconds -lt $ClientSeconds) {
        Start-Sleep $PollSeconds
        if ($s.HasExited) { "SERVER EXITED at $(Get-Date -Format HH:mm:ss)" | Add-Content -Encoding utf8 $timeline; break }
        $snap = try { python -c $rcon $pw 'msr_regions' 2>$null } catch { "rcon failed: $_" }
        "--- t+$([int]((Get-Date) - $start).TotalSeconds)s" | Add-Content -Encoding utf8 $timeline
        $snap | Where-Object { $_ -match '^region \d|^edicts|^player|^monsters|rcon failed' } | ForEach-Object { ($_ -replace '\| title.*$', '') } | Add-Content -Encoding utf8 $timeline
    }
    $serverAlive = -not $s.HasExited
    if ($serverAlive) {
        try { python -c $rcon $pw 'msr_regions monsters' 2>$null | Set-Content -Encoding utf8 "$logs\$Name-regions.txt" } catch { "rcon failed: $_" }
    }
} finally {
    if (Test-Path "$sb\engine.log") { Copy-Item "$sb\engine.log" "$logs\$Name-client.log" -Force }
    powershell -NoProfile -ExecutionPolicy Bypass -File "$w\Stop-BigWorld-Test.ps1" | Out-Null
    Start-Sleep 1
    if (Test-Path "$sb\bwserver.log") { Copy-Item "$sb\bwserver.log" "$logs\$Name-server.log" -Force }
}
"server alive at end: $serverAlive; client exited: $($c.HasExited)"
'--- client markers:'
Get-Content "$logs\$Name-client.log" | Where-Object { $_ -match 'BW_|^origin|lifecycle_chat|Host_Error|rror' -and $_ -notmatch 'FMOD|sound/' }
'--- server MSR / error lines:'
Select-String -Path "$logs\$Name-server.log" -Pattern '^MSR: |Host_Error|late precache|no free edicts|FATAL' | ForEach-Object { $_.Line }
