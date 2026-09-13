$ErrorActionPreference = 'Stop'
# Compile the preserved candidate-08 suites, then the candidate-09 FN regression.
& (Join-Path $PSScriptRoot 'unified/Run-Tests.ps1')
& (Join-Path $PSScriptRoot 'equipment/Run-Tests.ps1')
& (Join-Path $PSScriptRoot 'fn-listen/Run-Tests.ps1')
