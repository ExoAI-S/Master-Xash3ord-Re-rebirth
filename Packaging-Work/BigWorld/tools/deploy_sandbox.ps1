# Install the current builds into the private sandbox (never C:\MSR):
# ms.dll + client.dll from src\build-bw, the world map (default the 5-region Big World
# map) as maps\edana.bsp with its detail list, and the map's CRC in the sandbox FN
# manifest (FN reads it at start-up; the harness/launcher restart FN).
# Stops the sandbox game and FN first, because they hold these files open.
param([string]$Map = 'build\edana_bigworld5.bsp', [string]$Detail = 'build\edana_bigworld5_detail.txt',
      [string]$Patches = 'build\ent-patches-bigworld5', [string[]]$Regions = @('thornlands', 'edanasewers', 'thornlands_north', 'helena'),
      [switch]$NoDlls)
$ErrorActionPreference = 'Stop'
$w = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$game = "$w\sandbox\game\msr"
powershell -NoProfile -ExecutionPolicy Bypass -File "$w\Stop-BigWorld-Test.ps1"
Start-Sleep 1
if (-not $NoDlls) {
    Copy-Item "$w\src\build-bw\Debug\msr\bin\ms.dll" "$game\dlls\ms.dll" -Force
    Copy-Item "$w\src\build-bw\Debug\msr\bin\client.dll" "$game\cl_dlls\client.dll" -Force
}
Copy-Item "$w\$Map" "$game\maps\edana.bsp" -Force
Copy-Item "$w\$Detail" "$game\maps\edana_detail.txt" -Force
# Neighbour maps route into the world through entity patches; maps that are now regions
# of the world must not keep a patch of their own (their standalone copy stays unreachable).
foreach ($r in $Regions + @('edana')) {
    if (Test-Path "$game\maps\$r.ent") { Remove-Item "$game\maps\$r.ent" -Force; "removed maps\$r.ent" }
}
Get-ChildItem "$w\$Patches" -Filter *.ent | ForEach-Object {
    Copy-Item $_.FullName "$game\maps\$($_.Name)" -Force
    (Get-Item "$game\maps\$($_.Name)").LastWriteTime = Get-Date   # the engine uses a .ent only if it is newer than the .bsp
    "patch maps\$($_.Name)"
}
python -c @"
import json, os, pathlib, zlib
m = pathlib.Path(r'$w\sandbox\FN\content-manifest.json')
d = json.loads(m.read_text('utf-8-sig'))
d['maps']['edana'] = zlib.crc32(pathlib.Path(r'$game\maps\edana.bsp').read_bytes()) & 0xffffffff
t = m.with_suffix('.tmp'); t.write_text(json.dumps(d, indent=2) + '\n', 'utf-8'); os.replace(t, m)
print('FN manifest edana crc', d['maps']['edana'])
"@
Push-Location "$w\sandbox\FN"; python check_content.py; Pop-Location
Get-FileHash "$game\dlls\ms.dll", "$game\cl_dlls\client.dll", "$game\maps\edana.bsp" -Algorithm MD5 | ForEach-Object { "{0}  {1}" -f $_.Hash, $_.Path.Replace($w, '') }
