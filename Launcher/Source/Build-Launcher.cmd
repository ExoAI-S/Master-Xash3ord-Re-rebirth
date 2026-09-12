@echo off
"%WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe" /nologo /target:winexe /debug:full /optimize- /platform:anycpu /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /reference:System.Management.dll /reference:System.Web.Extensions.dll /reference:System.Runtime.Serialization.dll /out:"%~dp0..\..\MSR-Launcher.exe" "%~dp0MSRLauncher.cs"
exit /b %ERRORLEVEL%
