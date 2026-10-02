param([Parameter(Mandatory=$true)][string]$OutputRoot,
      [Parameter(Mandatory=$true)][string]$EngineSourceRoot)
$ErrorActionPreference='Stop'
$repoRoot=Split-Path $PSScriptRoot -Parent
$serverRoot=Join-Path $repoRoot 'Full-Source\msr_source\src\game\server'
$runRoot=Join-Path $OutputRoot ('run-' + [guid]::NewGuid().ToString('N'))
$snapshot=Join-Path $runRoot 'inputs'
New-Item -ItemType Directory -Path $snapshot | Out-Null
$receipt=[ordered]@{
    schema='encounter-allocator-engine-model-v1'; started_utc=[DateTime]::UtcNow.ToString('o')
    status='preparing'; run_path=$runRoot; compiler=$null; arguments=@(); source_inputs=@()
    compile_exit=$null; test_exit=$null; groups=$null; assertions=$null; files=@(); error=$null
    scope='Engine-free allocator pressure/admission model with independent scan/high-water/growth oracle. No game, services, profiles, FN or native acceptance.'
    native_acceptance=$false; runtime_installation_performed=$false
}
$success=$false
try {
    $sources=@(
        (Join-Path $serverRoot 'msr_encounter_allocator.h'),
        (Join-Path $serverRoot 'msr_encounter_policy.h'),
        (Join-Path $PSScriptRoot 'test_encounter_allocator.cpp'),
        $PSCommandPath,
        (Join-Path $EngineSourceRoot 'engine\server\sv_game.c'),
        (Join-Path $EngineSourceRoot 'engine\server\server.h'))
    foreach($source in $sources){
        $target=Join-Path $snapshot (Split-Path $source -Leaf)
        $before=(Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
        Copy-Item -LiteralPath $source -Destination $target
        if((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant() -ne $before){throw 'Input snapshot mismatch'}
        $receipt.source_inputs += [ordered]@{original_path=$source; archived_path=$target; sha256=$before}
    }
    $vcvars='C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvarsall.bat'
    $environmentLines=& $env:ComSpec /d /s /c "`"$vcvars`" x86 >nul && set"
    if($LASTEXITCODE){throw 'Vendor compiler environment initialization failed'}
    foreach($line in $environmentLines){
        $separator=$line.IndexOf('=')
        if($separator -gt 0){
            $variableName=$line.Substring(0,$separator)
            if($variableName -notin @('HOME','CODEX_HOME')){
                [Environment]::SetEnvironmentVariable($variableName,$line.Substring($separator+1),'Process')
            }
        }
    }
    $compiler=(Get-Command cl.exe -ErrorAction Stop).Source
    $receipt.compiler=[ordered]@{path=$compiler; sha256=(Get-FileHash -LiteralPath $compiler).Hash.ToLowerInvariant(); architecture='x86'; version=(Get-Item -LiteralPath $compiler).VersionInfo.FileVersion}
    $exe=Join-Path $runRoot 'allocator-tests.exe'
    $arguments=@('/nologo','/std:c++20','/EHsc','/W4','/WX','/Od','/Ob0','/RTC1','/Zi','/MTd','/D_DEBUG','/utf-8',
        ('/Fe:'+$exe),('/Fo:'+(Join-Path $runRoot 'allocator-tests.obj')),('/Fd:'+(Join-Path $runRoot 'compiler.pdb')),
        (Join-Path $snapshot 'test_encounter_allocator.cpp'),'/link','/DEBUG',('/PDB:'+(Join-Path $runRoot 'allocator-tests.pdb')))
    $receipt.arguments=$arguments
    & $compiler @arguments *> (Join-Path $runRoot 'compile.txt')
    $receipt.compile_exit=$LASTEXITCODE
    if($LASTEXITCODE){throw 'Model compilation failed; see retained compile.txt'}
    & $exe *> (Join-Path $runRoot 'tests.txt')
    $receipt.test_exit=$LASTEXITCODE
    if($LASTEXITCODE){throw 'Allocator model tests failed; see retained tests.txt'}
    $result=Get-Content -LiteralPath (Join-Path $runRoot 'tests.txt') -Raw
    if($result -notmatch 'RESULT groups=(\d+) assertions=(\d+) PASS'){throw 'Missing test completion record'}
    $receipt.groups=[int]$Matches[1]; $receipt.assertions=[int]$Matches[2]
    foreach($pin in $receipt.source_inputs){
        if((Get-FileHash -LiteralPath $pin.original_path).Hash.ToLowerInvariant() -ne $pin.sha256 -or
           (Get-FileHash -LiteralPath $pin.archived_path).Hash.ToLowerInvariant() -ne $pin.sha256){throw 'Inputs changed during model test'}
    }
    $receipt.status='passed-engine-free-model-only'; $success=$true
} catch { $receipt.status='failed'; $receipt.error=$_.Exception.Message }
finally {
    $receipt.finished_utc=[DateTime]::UtcNow.ToString('o')
    foreach($file in Get-ChildItem -LiteralPath $runRoot -File){
        $receipt.files += [ordered]@{name=$file.Name; path=$file.FullName; bytes=$file.Length; sha256=(Get-FileHash -LiteralPath $file.FullName).Hash.ToLowerInvariant()}
    }
    $receiptPath=Join-Path $runRoot 'receipt.json'
    $receipt | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $receiptPath -Encoding utf8
    [pscustomobject]$receipt | Select-Object status,run_path,compile_exit,test_exit,groups,assertions,error | ConvertTo-Json
}
if(-not $success){exit 1}
