@echo off
setlocal
set "MSR_NO_PAUSE="
if /i "%~1"=="--no-pause" set "MSR_NO_PAUSE=1"
pushd "%~dp0" || goto :failed
set "MSR_ZIP=MSR-PrimeXT-DM-Magic-Fix-Debug-Complete-2026-09-12.zip"
set "MSR_EXPECTED_HASH=8f62cafa56c06e1efaa907677b6bcb4b52ac53cc6c1b70130fdcd28c4d922b81"
echo Checking both download parts. This can take a minute.
powershell.exe -NoLogo -NoProfile -NonInteractive -Command "$ErrorActionPreference='Stop'; function Get-MSRDigest($p) { $stream=[IO.File]::OpenRead((Join-Path (Get-Location) $p)); try { $sha=[Security.Cryptography.SHA256]::Create(); try { return [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-','').ToLowerInvariant() } finally { $sha.Dispose() } } finally { $stream.Dispose() } }; try { $parts=@(@('.001',1700000000,'69371efe0a9661734dcdf0395fe2b5d07dd29237ae34b9fa4bd19df5ebbbf0be'),@('.002',1451413773,'e39a0698c63aef49b367109470af150b3d47a05cefbe2eba1a661955878d17ae')); foreach($part in $parts) { $path=$env:MSR_ZIP+$part[0]; if(-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw ('Missing download: '+$path+'. Put both parts and this CMD in the same folder.') }; if((Get-Item -LiteralPath $path).Length -ne $part[1]) { throw ('Incomplete or wrong-sized download: '+$path) }; if((Get-MSRDigest $path) -ne $part[2]) { throw ('Download verification failed: '+$path+'. Download this part again.') } }; if(Test-Path -LiteralPath $env:MSR_ZIP) { if((Get-Item -LiteralPath $env:MSR_ZIP).Length -eq 3151413773 -and (Get-MSRDigest $env:MSR_ZIP) -eq $env:MSR_EXPECTED_HASH) { exit 10 }; throw 'A different ZIP already exists at the output path. Move or rename it first; it will not be overwritten.' }; if(Test-Path -LiteralPath ($env:MSR_ZIP+'.assembling')) { throw 'A previous .assembling file exists. Move or rename it before retrying; it will not be overwritten.' }; exit 0 } catch { Write-Host ('ERROR: '+$_.Exception.Message) -ForegroundColor Red; exit 1 }"
if errorlevel 11 goto :failed_in_folder
if errorlevel 10 goto :already_ready
if errorlevel 1 goto :failed_in_folder
echo Joining the two parts. Please leave this window open.
copy /b "%MSR_ZIP%.001"+"%MSR_ZIP%.002" "%MSR_ZIP%.assembling" >nul
if errorlevel 1 goto :failed_in_folder
echo Verifying the completed game ZIP.
powershell.exe -NoLogo -NoProfile -NonInteractive -Command "$ErrorActionPreference='Stop'; function Get-MSRDigest($p) { $stream=[IO.File]::OpenRead((Join-Path (Get-Location) $p)); try { $sha=[Security.Cryptography.SHA256]::Create(); try { return [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-','').ToLowerInvariant() } finally { $sha.Dispose() } } finally { $stream.Dispose() } }; try { $temp=$env:MSR_ZIP+'.assembling'; if((Get-Item -LiteralPath $temp).Length -ne 3151413773 -or (Get-MSRDigest $temp) -ne $env:MSR_EXPECTED_HASH) { throw 'The assembled ZIP failed verification. Keep the download parts and retry in a folder with enough free space.' }; Move-Item -LiteralPath $temp -Destination $env:MSR_ZIP -ErrorAction Stop; exit 0 } catch { Write-Host ('ERROR: '+$_.Exception.Message) -ForegroundColor Red; exit 1 }"
if errorlevel 1 goto :failed_in_folder
goto :ready
:already_ready
echo The complete ZIP already exists and its SHA256 is correct.
:ready
echo.
echo READY: %MSR_ZIP%
echo Right-click that ZIP, choose Extract All, and open the extracted folder.
echo Open MSR-PrimeXT-DM and run MSR-Launcher.exe.
echo You can remove the two download parts after successful extraction.
popd
if not defined MSR_NO_PAUSE pause
exit /b 0
:failed_in_folder
popd
:failed
echo.
echo Setup stopped. Read the error above. Your download parts were kept.
if not defined MSR_NO_PAUSE pause
exit /b 1
