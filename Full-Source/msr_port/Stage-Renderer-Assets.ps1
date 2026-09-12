param(
    [string]$PackageRoot = (Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) 'Portable-Package')
)

$ErrorActionPreference = 'Stop'

$sourceRoot = Split-Path -Parent $PSScriptRoot
$primeGame = Join-Path $sourceRoot 'game_dir'
$msrGame = Join-Path $PackageRoot 'game\msr'
$python = Join-Path $PackageRoot 'runtime\python.exe'
$generator = Join-Path $PSScriptRoot 'generate_msr_materials.py'

if (!(Test-Path -LiteralPath $msrGame)) { throw "MSR game directory not found: $msrGame" }
if (!(Test-Path -LiteralPath $python)) { throw "Package Python runtime not found: $python" }

function Copy-MissingTree([string]$RelativePath) {
    $source = Join-Path $primeGame $RelativePath
    $destination = Join-Path $msrGame $RelativePath
    $copied = 0
    Get-ChildItem -LiteralPath $source -Recurse -File | ForEach-Object {
        $relative = $_.FullName.Substring($source.Length + 1)
        $target = Join-Path $destination $relative
        if (!(Test-Path -LiteralPath $target)) {
            $targetDirectory = Split-Path -Parent $target
            New-Item -ItemType Directory -Force -Path $targetDirectory | Out-Null
            Copy-Item -LiteralPath $_.FullName -Destination $target
            $copied++
        }
    }
    Write-Host "$RelativePath`: copied $copied previously missing files"
}

Copy-MissingTree 'glsl'
Copy-MissingTree 'gfx'
Copy-MissingTree 'particles'
Copy-MissingTree 'scripts'

$models = Join-Path $msrGame 'models'
$materials = Join-Path $msrGame 'scripts\msr_models.mat'
& $python $generator $models $materials
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "PrimeXT renderer resources staged under $msrGame"
