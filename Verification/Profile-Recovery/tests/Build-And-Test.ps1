$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe'
$flags = @('/nologo','/debug:full','/optimize-','/platform:anycpu','/r:System.Windows.Forms.dll','/r:System.Drawing.dll','/r:System.Management.dll','/r:System.Web.Extensions.dll','/r:System.Runtime.Serialization.dll')
& $compiler @flags /target:winexe /out:package\MSR-Launcher.exe package\Launcher\Source\MSRLauncher.cs package\Launcher\Source\ProfileRecovery.cs
if ($LASTEXITCODE -ne 0) { throw 'Recovery launcher compile failed' }
& $compiler @flags /target:winexe /out:baseline\MSR-Launcher.exe baseline\Launcher\Source\MSRLauncher.cs
if ($LASTEXITCODE -ne 0) { throw 'Baseline launcher compile failed' }
& $compiler @flags /target:exe /main:RecoveryTests /out:tests\RecoveryTests.exe package\Launcher\Source\MSRLauncher.cs package\Launcher\Source\ProfileRecovery.cs tests\RecoveryTests.cs
if ($LASTEXITCODE -ne 0) { throw 'Recovery test compile failed' }
& $compiler @flags /target:exe /main:BaselineTests /out:tests\BaselineTests.exe baseline\Launcher\Source\MSRLauncher.cs tests\BaselineTests.cs
if ($LASTEXITCODE -ne 0) { throw 'Baseline test compile failed' }
& .\tests\RecoveryTests.exe
if ($LASTEXITCODE -ne 0) { throw 'Recovery tests failed' }
& .\tests\BaselineTests.exe
if ($LASTEXITCODE -ne 0) { throw 'Baseline tests failed' }
python tests\verify_debug.py
if ($LASTEXITCODE -ne 0) { throw 'EXE/PDB verification failed' }
Write-Output 'PASS: old/new Debug builds, focused inert tests, and exact PDB pairing'
