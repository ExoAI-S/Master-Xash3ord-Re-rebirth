using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

internal static class PrimeXTMSRLauncher
{
    [System.Runtime.InteropServices.DllImport("user32.dll")]
    private static extern bool SetForegroundWindow(IntPtr window);
    [System.Runtime.InteropServices.DllImport("user32.dll")]
    private static extern bool ShowWindowAsync(IntPtr window, int command);
    private const string Runtime = @"C:\Users\chels\Documents\Codex\2026-09-11\thi-2\work\MSR-PrimeXT-Port-v1\runtime";

    [STAThread]
    private static int Main()
    {
        try
        {
            foreach (string relative in new[] { "xash3d.exe", "xash.dll", @"msr\cl_dlls\client.dll", @"msr\dlls\ms.dll", @"msr\scripts.pak" })
            {
                if (!File.Exists(Path.Combine(Runtime, relative)))
                    throw new FileNotFoundException("The staging build is incomplete: " + relative);
            }
            Directory.CreateDirectory(Path.Combine(Runtime, @"msr\save"));
            foreach (Process process in Process.GetProcessesByName("xash3d"))
            {
                try
                {
                    if (String.Equals(process.MainModule.FileName, Path.Combine(Runtime, "xash3d.exe"), StringComparison.OrdinalIgnoreCase))
                    {
                        ShowWindowAsync(process.MainWindowHandle, 9);
                        SetForegroundWindow(process.MainWindowHandle);
                        return 0;
                    }
                }
                catch (System.ComponentModel.Win32Exception) { }
                finally { process.Dispose(); }
            }
            string profile = Path.Combine(Runtime, "test-profile.txt");
            if (!File.Exists(profile))
                File.WriteAllText(profile, Guid.NewGuid().ToString("N"));
            string key = File.ReadAllText(profile).Trim();
            if (!System.Text.RegularExpressions.Regex.IsMatch(key, "^[0-9a-f]{32}$"))
                throw new InvalidDataException("The local test profile is invalid.");
            string config = "sv_lan 1\npublic 0\nms_central_enabled 0\nsetinfo _fnid \"" + key + "\"\nname \"PrimeXT Tester\"\n";
            File.WriteAllText(Path.Combine(Runtime, @"msr\primext_test.cfg"), config);
            Process.Start(new ProcessStartInfo
            {
                FileName = Path.Combine(Runtime, "xash3d.exe"),
                Arguments = "-game msr -windowed -width 1280 -height 720 -console -dev 2 -log -ip 127.0.0.1 -port 27045 +exec primext_test.cfg +maxplayers 4 +map edana",
                WorkingDirectory = Runtime,
                UseShellExecute = false
            });
            return 0;
        }
        catch (Exception error)
        {
            MessageBox.Show(error.Message, "MSR / PrimeXT staging test", MessageBoxButtons.OK, MessageBoxIcon.Information);
            return 1;
        }
    }
}
