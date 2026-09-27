# Run the scripted crossing test in the sandbox: test FN + dedicated realm + scripted client.
# Writes sandbox\logs\<Name>-client.log (client console with BW_ markers) and stops everything afterwards.
param([string]$Name = 'test', [int]$ClientSeconds = 420, [string]$Map = 'edana', [string[]]$ServerArgs = @())
$ErrorActionPreference = 'Stop'
$w = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$sb = "$w\sandbox\game"; $logs = "$w\sandbox\logs"
powershell -NoProfile -ExecutionPolicy Bypass -File "$w\Stop-BigWorld-Test.ps1" | Out-Null
$fn = Start-Process -FilePath python -ArgumentList "$w\sandbox\FN\fn_server.py", 'serve' -WorkingDirectory "$w\sandbox\FN" -PassThru -WindowStyle Hidden `
    -RedirectStandardOutput "$logs\fn-stdout.log" -RedirectStandardError "$logs\fn-stderr.log"
Start-Sleep 3
$serverArgList = @('-dedicated', '-console', '-log', 'bwserver') + $ServerArgs + @('-game', 'msr', '-port', '27199', '+ip', '127.0.0.1',
    '+maxplayers', '4', '+sv_lan', '1', '+public', '0', '+exec', 'server_sandbox.cfg', '+map', $Map)
$s = Start-Process -FilePath "$sb\xash3d.exe" -ArgumentList $serverArgList -WorkingDirectory $sb -PassThru -WindowStyle Minimized
Start-Sleep 22
if ($s.HasExited) { throw 'dedicated server exited during startup' }
$c = Start-Process -FilePath "$sb\xash3d.exe" -ArgumentList '-game', 'msr', '-log', '-window', '-width', '1280', '-height', '720', '-nosound', '-nomouse',
    '+exec', 'bigworld_test.cfg' -WorkingDirectory $sb -PassThru
$deadline = (Get-Date).AddSeconds($ClientSeconds)
while (-not $c.HasExited -and (Get-Date) -lt $deadline) { Start-Sleep 5 }
$serverAlive = -not $s.HasExited
$ErrorActionPreference = 'Continue' # rcon to a crashed server must not abort log collection
$pw = (Get-Content "$w\sandbox\rcon.txt").Trim()
$usage = python -c "import importlib.util; spec=importlib.util.spec_from_file_location('gq', r'C:\MSR\Portable-Package\FN\game_query.py'); gq=importlib.util.module_from_spec(spec); spec.loader.exec_module(gq); print(gq.rcon(27199, '$pw', 'edict_usage'))" 2>$null
# region table, player regions and monsters per region (ms.dll msr_regions command; harmless elsewhere)
python -c "import importlib.util; spec=importlib.util.spec_from_file_location('gq', r'C:\MSR\Portable-Package\FN\game_query.py'); gq=importlib.util.module_from_spec(spec); spec.loader.exec_module(gq); print(gq.rcon(27199, '$pw', 'msr_regions monsters'))" 2>$null |
    Set-Content -Encoding utf8 "$logs\$Name-regions.txt"
Copy-Item "$sb\engine.log" "$logs\$Name-client.log" -Force
powershell -NoProfile -ExecutionPolicy Bypass -File "$w\Stop-BigWorld-Test.ps1" | Out-Null
Start-Sleep 1
if (Test-Path "$sb\bwserver.log") { Copy-Item "$sb\bwserver.log" "$logs\$Name-server.log" -Force }
$t = Get-Content "$logs\$Name-client.log"
$i = ($t | Select-String 'BW_STEP_0_CREATE' | Select-Object -First 1).LineNumber
"server alive at end: $serverAlive; client exited: $($c.HasExited)"
"edict usage: " + (($usage | Out-String) -replace '\s+', ' ').Trim()
if ($i) { $t[($i - 1)..($t.Count - 1)] | Where-Object { $_ -match 'BW_|^origin|^health|entity \d|Kick|rror|crash|chat_check' -and $_ -notmatch 'FMOD' } }
else { 'no BW markers found'; $t | Select-Object -Last 30 }
if (Test-Path "$logs\$Name-server.log") { '--- server MSR lines:'; Select-String -Path "$logs\$Name-server.log" -Pattern '^MSR: ' | ForEach-Object { $_.Line } }
if (Test-Path "$logs\$Name-regions.txt") { '--- msr_regions:'; Get-Content "$logs\$Name-regions.txt" | Where-Object { $_ -notmatch '^\s+#' } }
