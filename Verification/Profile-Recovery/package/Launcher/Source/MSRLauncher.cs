using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Management;
using System.Reflection;
using System.Runtime.Serialization;
using System.Runtime.Serialization.Json;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Web.Script.Serialization;
using System.Windows.Forms;

internal static class MSRLauncher
{
    [DataContract]
    private sealed class Identity
    {
        [DataMember(Name = "profile_key", IsRequired = true)]
        public string Key { get; set; }
    }
    internal const string RealmOne = "schmidt-council.tun.ply.gg:48715";
    internal const string RealmTwo = "schmidt-once.tun.ply.gg:63800";
    internal static readonly string[] Versions = { "Portable-Package", "Stable-Base" };
    internal static readonly string[] Required = { "xash3d.exe", "xash.dll", @"msr\cl_dlls\client.dll", @"msr\dlls\ms.dll", @"msr\scripts.pak" };
    private static readonly JavaScriptSerializer Json = new JavaScriptSerializer();

    [STAThread]
    private static int Main(string[] args)
    {
        string root = AppDomain.CurrentDomain.BaseDirectory;
        try
        {
            if (args.Length == 1 && args[0] == "--self-test")
            {
                Application.EnableVisualStyles();
                Application.SetCompatibleTextRenderingDefault(false);
                SelfTest(root);
                return 0;
            }
            if (args.Length == 1 && args[0] == "--create-shortcuts")
            {
                Application.EnableVisualStyles();
                Application.SetCompatibleTextRenderingDefault(false);
                if (!ProfileRecovery.PrepareForUse(root, Versions[0], Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), true)) return 1;
                CreateShortcuts(root);
                MessageBox.Show("Created MSR, Join Realm One, Join Realm Two, and Dungeon Master desktop shortcuts.", "MSR shortcuts");
                return 0;
            }
            if ((args.Length == 1 || args.Length == 3) && args[0] == "--prepare-profile")
            {
                if (args.Length == 3 && args[1] != "--desktop") throw new ArgumentException("Use --prepare-profile --desktop followed by your shortcut folder.");
                Application.EnableVisualStyles();
                Application.SetCompatibleTextRenderingDefault(false);
                string desktop = args.Length == 3 ? Path.GetFullPath(args[2]) : Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
                return ProfileRecovery.PrepareForUse(root, Versions[0], desktop, true) ? 0 : 1;
            }
            string version = "Portable-Package";
            string realm = null;
            string hostAction = null;
            bool dungeonMaster = false;
            bool validateOnly = false;
            for (int i = 0; i < args.Length; i++)
            {
                if (args[i] == "--version" && i + 1 < args.Length)
                {
                    string value = args[++i].ToLowerInvariant();
                    if (value != "enhanced" && value != "stable") throw new ArgumentException("Choose --version enhanced or stable.");
                    version = value == "stable" ? "Stable-Base" : "Portable-Package";
                }
                else if (args[i] == "--realm" && i + 1 < args.Length)
                {
                    string value = args[++i].ToLowerInvariant();
                    if (value != "one" && value != "two") throw new ArgumentException("Choose --realm one or two.");
                    realm = value == "one" ? RealmOne : RealmTwo;
                }
                else if (args[i] == "--address" && i + 1 < args.Length) { realm = ValidateAddress(args[++i]); }
                else if (args[i] == "--dm") { dungeonMaster = true; }
                else if (args[i] == "--validate-only") { validateOnly = true; }
                else if (args[i] == "--host-action" && i + 1 < args.Length)
                {
                    hostAction = args[++i].ToLowerInvariant();
                    if (hostAction != "start" && hostAction != "stop" && hostAction != "status" && hostAction != "play")
                        throw new ArgumentException("Choose host action start, stop, status, or play.");
                }
                else throw new ArgumentException("Unknown launcher argument. Open MSR-Launcher.exe without arguments to choose a server.");
            }
            if ((realm != null ? 1 : 0) + (hostAction != null ? 1 : 0) + (dungeonMaster ? 1 : 0) > 1)
                throw new ArgumentException("Choose one launcher action at a time.");
            // CLI validation must never write profiles, open a window or touch a host.
            if (validateOnly) return 0;
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            if (realm != null) { Launch(root, version, realm, true); return 0; }
            if (dungeonMaster) Application.Run(new DMForm(root));
            else if (hostAction != null) Application.Run(new HostForm(root, version, hostAction));
            else
            {
                if (!ProfileRecovery.PrepareForUse(root, version, Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory))) return 0;
                Application.Run(new LauncherForm(root, version));
            }
            return 0;
        }
        catch (Exception error)
        {
            if (Array.IndexOf(args, "--validate-only") >= 0) return 2;
            ShowError(root, error);
            return 1;
        }
    }

    internal static void ShowError(string root, Exception error)
    {
        string log = Path.Combine(root, "launcher-error.log");
        // Never log configurations or profile contents. Only our fixed validation messages
        // and OS exceptions about operations are recorded.
        try { File.AppendAllText(log, DateTime.UtcNow.ToString("o") + " " + error.GetType().Name + ": " + error.Message + Environment.NewLine); }
        catch { log = "The folder is not writable, so an error log could not be saved."; }
        MessageBox.Show(error.Message + "\n\n" + log, "MSR could not launch", MessageBoxButtons.OK, MessageBoxIcon.Error);
    }

    internal static string ValidateAddress(string address)
    {
        address = address.Trim();
        Match match = Regex.Match(address, @"^([A-Za-z0-9.-]+):([0-9]{1,5})$");
        int port;
        if (!match.Success || !Int32.TryParse(match.Groups[2].Value, out port) || port < 1024 || port > 65535)
            throw new ArgumentException("Enter a server hostname or IPv4 address followed by a port, for example 192.168.1.10:27025.");
        return address;
    }

    internal static string ReadKey(string path)
    {
        if (new FileInfo(path).Length > 65536) throw new InvalidDataException("The player profile is too large. It was not overwritten.");
        return ReadKeyContent(File.ReadAllBytes(path), path);
    }

    internal static string ReadKeyContent(byte[] bytes, string path)
    {
        try
        {
            if (bytes.Length > 65536) throw new SerializationException();
            string content;
            using (StreamReader reader = new StreamReader(new MemoryStream(bytes), Encoding.UTF8, true)) content = reader.ReadToEnd();
            if (!(Json.DeserializeObject(content) is Dictionary<string, object>)) throw new SerializationException();
            Identity data;
            using (MemoryStream input = new MemoryStream(Encoding.UTF8.GetBytes(content)))
                data = (Identity)new DataContractJsonSerializer(typeof(Identity)).ReadObject(input);
            if (data == null || data.Key == null || !Regex.IsMatch(data.Key, "^[0-9a-f]{32}$"))
                throw new SerializationException();
            return data.Key;
        }
        catch (Exception error)
        {
            if (error is IOException || error is UnauthorizedAccessException) throw;
            throw new InvalidDataException("The player identity in " + Path.GetFileName(Path.GetDirectoryName(path)) + " is invalid. Restore its player-profile.json backup; it has not been overwritten.");
        }
    }

    internal static string Prepare(string root, string version, string address, bool windowed)
    {
        return Prepare(root, version, address, windowed, ProfileRecovery.BackupDirectory, false);
    }

    internal static string Prepare(string root, string version, string address, bool windowed, string backups, bool startNew)
    {
        if (version != Versions[0] && version != Versions[1]) throw new ArgumentException("Invalid game version.");
        address = ValidateAddress(address);
        string folder = Path.Combine(root, version);
        string game = Path.Combine(folder, "game");
        foreach (string part in Required)
            if (!File.Exists(Path.Combine(game, part))) throw new FileNotFoundException("The extracted game is incomplete: " + version + "\\game\\" + part + ". Extract the entire original game ZIP before adding this launcher.");
        string key = PrepareIdentity(root, version, backups, startNew);
        string configuration = "setinfo _fnid \"" + key + "\"\r\npassword \"\"\r\nexec masterpiece.cfg\r\nms_invtype \"1\"\r\nms_alpha_inventory \"1\"\r\nconnect " + address + "\r\n";
        File.WriteAllText(Path.Combine(game, @"msr\private_join.cfg"), configuration, Encoding.ASCII);
        return "-game msr -port 27026 -console -log client.log " + (windowed ? "-windowed -width 1280 -height 720 " : "") + "+exec private_join.cfg";
    }

    internal static string PrepareIdentity(string root, string version, string backups, bool startNew)
    {
        ProfileRecovery.Targets(root, version);
        string folder = Path.Combine(root, version);
        using (FileStream profileGuard = LockProfile(root))
        {
        string profilePath = Path.Combine(folder, "player-profile.json");
        string otherPath = Path.Combine(root, version == Versions[0] ? Versions[1] : Versions[0], "player-profile.json");
        string key = File.Exists(profilePath) ? ReadKey(profilePath) : null;
        string other = File.Exists(otherPath) ? ReadKey(otherPath) : null;
        if (key != null && other != null && key != other)
            throw new InvalidDataException("The current and recovery builds have different player identities. Keep both player-profile.json files and restore the intended identity before joining. Neither file was changed.");
        if (key == null)
        {
            key = other;
            if (key == null)
            {
                ProfileDiscovery saved = ProfileRecovery.ListBackups(backups);
                if (!startNew && (saved.Count != 0 || saved.Warnings.Count != 0))
                    throw new InvalidOperationException("A saved player profile is available or could not be read. Use Recover characters to choose a valid profile, or explicitly choose Start a new profile.");
                byte[] bytes = new byte[16];
                using (RandomNumberGenerator random = RandomNumberGenerator.Create()) random.GetBytes(bytes);
                key = BitConverter.ToString(bytes).Replace("-", "").ToLowerInvariant();
            }
            // CreateNew prevents concurrent launchers from replacing an identity.
            using (FileStream stream = new FileStream(profilePath, FileMode.CreateNew, FileAccess.Write, FileShare.None))
            using (StreamWriter writer = new StreamWriter(stream, new UTF8Encoding(false)))
                writer.Write(Json.Serialize(new Dictionary<string, object> { { "profile_key", key } }));
        }
        // Keep the identity outside the installation before preparing every join.
        ProfileRecovery.BackupFile(profilePath, backups, root, version);
        return key;
        }
    }

    internal static FileStream LockProfile(string root)
    {
        for (int attempt = 0; attempt < 20; attempt++)
        {
            try { return new FileStream(Path.Combine(root, ".player-profile.lock"), FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None); }
            catch (IOException error)
            {
                int code = System.Runtime.InteropServices.Marshal.GetHRForException(error) & 0xFFFF;
                if (code != 32 && code != 33) throw;
                System.Threading.Thread.Sleep(100);
            }
        }
        throw new IOException("Another MSR launcher is updating your player identity. Wait briefly and try again; no profile was overwritten.");
    }

    internal static FileStream LockClientLaunch(string root)
    {
        try { return new FileStream(Path.Combine(root, "client-launch.lock"), FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None); }
        catch (IOException) { throw new IOException("Another MSR launcher is starting a game or restoring a profile. Wait briefly and try again."); }
    }

    internal static void AssertNoRunningClient(string root)
    {
            using (ManagementObjectSearcher searcher = new ManagementObjectSearcher("SELECT ExecutablePath, CommandLine FROM Win32_Process WHERE Name='xash3d.exe'"))
            using (ManagementObjectCollection processes = searcher.Get())
            {
                foreach (ManagementObject process in processes)
                using (process)
                {
                    string path = process["ExecutablePath"] as string;
                    string command = process["CommandLine"] as string;
                    AssertClientRecord(root, path, command);
                }
            }
    }

    internal static void AssertClientRecord(string root, string path, string command)
    {
        if (String.IsNullOrEmpty(path)) throw new InvalidOperationException("Windows could not verify an open game process. Close MSR before restoring a profile or joining another server.");
        foreach (string runtime in Versions)
            if (String.Equals(path, Path.Combine(root, runtime, @"game\xash3d.exe"), StringComparison.OrdinalIgnoreCase) &&
                !Regex.IsMatch(command ?? "", @"(^|\s)-dedicated(\s|$)", RegexOptions.IgnoreCase))
                throw new InvalidOperationException("Close the current MSR game window before restoring a profile or joining another server. Your current game was left running.");
    }

    internal static bool Launch(string root, string version, string address, bool windowed)
    {
        if (!ProfileRecovery.PrepareForUse(root, version, Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory))) return false;
        using (FileStream guard = LockClientLaunch(root))
        {
            AssertNoRunningClient(root);
            string arguments = Prepare(root, version, address, windowed);
            string game = Path.Combine(root, version, "game");
            using (Process process = Process.Start(new ProcessStartInfo { FileName = Path.Combine(game, "xash3d.exe"), WorkingDirectory = game, Arguments = arguments, UseShellExecute = false }))
            {
                if (process == null) throw new InvalidOperationException("Windows did not start the game process.");
                if (process.WaitForExit(750) && process.ExitCode != 0)
                    throw new InvalidOperationException("The game exited during startup (code 0x" + unchecked((uint)process.ExitCode).ToString("X8") + "). Check " + version + "\\game\\client.log.");
            }
        }
        return true;
    }

    private static void Property(object item, string name, object value)
    {
        item.GetType().InvokeMember(name, BindingFlags.SetProperty, null, item, new object[] { value });
    }

    internal static void CreateShortcuts(string root)
    {
        string desktop = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
        CreateShortcuts(root, desktop);
    }

    private static void CreateShortcuts(string root, string desktop)
    {
        Directory.CreateDirectory(desktop);
        string exe = Path.Combine(root, "MSR-Launcher.exe");
        object shell = Activator.CreateInstance(Type.GetTypeFromProgID("WScript.Shell", true));
        try
        {
            string[] names = { "MSR", "MSR - Join Realm One", "MSR - Join Realm Two", "MSR - Dungeon Master" };
            string[] arguments = { "", "--realm one", "--realm two", "--dm" };
            string[] descriptions = { "Open MSR: join a realm, play locally, or use Dungeon Master controls.", "Join MSR Realm One.", "Join MSR Realm Two with the same character profile.", "Manage Dungeon Master permissions on realms hosted on this PC." };
            for (int i = 0; i < names.Length; i++)
            {
                object shortcut = shell.GetType().InvokeMember("CreateShortcut", BindingFlags.InvokeMethod, null, shell, new object[] { Path.Combine(desktop, names[i] + ".lnk") });
                try
                {
                    Property(shortcut, "TargetPath", exe);
                    Property(shortcut, "Arguments", arguments[i]);
                    Property(shortcut, "WorkingDirectory", root);
                    Property(shortcut, "Description", descriptions[i]);
                    shortcut.GetType().InvokeMember("Save", BindingFlags.InvokeMethod, null, shortcut, new object[0]);
                }
                finally { System.Runtime.InteropServices.Marshal.FinalReleaseComObject(shortcut); }
            }
            // Consolidate only old shortcuts that still belong to this installation.
            foreach (string oldName in new string[] { "MSR - Enhanced", "MSR - Stable Base" })
            {
                string oldPath = Path.Combine(desktop, oldName + ".lnk");
                if (!File.Exists(oldPath)) continue;
                object oldShortcut = shell.GetType().InvokeMember("CreateShortcut", BindingFlags.InvokeMethod, null, shell, new object[] { oldPath });
                bool owned;
                try
                {
                    string target = (string)oldShortcut.GetType().InvokeMember("TargetPath", BindingFlags.GetProperty, null, oldShortcut, new object[0]);
                    string legacyCmd = Path.Combine(root, oldName == "MSR - Enhanced" ? "Play-Enhanced.cmd" : "Play-Stable.cmd");
                    owned = String.Equals(target, exe, StringComparison.OrdinalIgnoreCase) || String.Equals(target, legacyCmd, StringComparison.OrdinalIgnoreCase);
                }
                finally { System.Runtime.InteropServices.Marshal.FinalReleaseComObject(oldShortcut); }
                if (owned)
                {
                    string backup = Path.Combine(root, "Recovery", "Desktop-Shortcut-Backups", Guid.NewGuid().ToString("N"));
                    Directory.CreateDirectory(backup);
                    File.Copy(oldPath, Path.Combine(backup, oldName + ".lnk"));
                    File.Delete(oldPath);
                }
            }
        }
        finally { System.Runtime.InteropServices.Marshal.FinalReleaseComObject(shell); }
    }

    private static void Assert(bool condition, string message) { if (!condition) throw new Exception("Self-test failed: " + message); }
    private static void SelfTest(string root)
    {
        string fixture = Path.Combine(Path.GetTempPath(), "MSR Launcher Synthetic Tests", "native launcher " + Guid.NewGuid().ToString("N"), "MSR Fixture");
        foreach (string version in Versions)
            foreach (string part in Required)
            {
                string file = Path.Combine(fixture, version, "game", part);
                Directory.CreateDirectory(Path.GetDirectoryName(file));
                File.WriteAllText(file, "test fixture; no executable content");
            }
        string testBackups = Path.Combine(Path.GetDirectoryName(fixture), "Durable Profiles");
        string args = Prepare(fixture, Versions[0], RealmOne, true, testBackups, true);
        string firstPath = Path.Combine(fixture, Versions[0], "player-profile.json");
        string first = ReadKey(firstPath);
        string original = File.ReadAllText(firstPath);
        string metadataPath = Path.Combine(fixture, "metadata-profile.json");
        File.WriteAllText(metadataPath, "{\"metadata\":{\"description\":\"profile_key\"},\"profile_key\":\"" + first + "\"}", new UTF8Encoding(true));
        Assert(ReadKey(metadataPath) == first, "metadata and UTF8 BOM accepted");
        string duplicatePath = Path.Combine(fixture, "duplicate-profile.json");
        File.WriteAllText(duplicatePath, "{\"profile_key\":\"" + first + "\",\"profile_key\":\"" + first + "\"}");
        bool duplicate = false;
        try { ReadKey(duplicatePath); } catch (InvalidDataException) { duplicate = true; }
        Assert(duplicate, "duplicate identity keys rejected");
        Assert(args.Contains("-windowed -width 1280 -height 720") && !args.Contains("-dedicated"), "windowed client arguments");
        Prepare(fixture, Versions[1], RealmTwo, false, testBackups, true);
        Assert(first == ReadKey(Path.Combine(fixture, Versions[1], "player-profile.json")), "identity reused across versions");
        Prepare(fixture, Versions[0], "127.0.0.1:27025", true, testBackups, true);
        Assert(File.ReadAllText(firstPath) == original, "existing identity preserved");
        string cfgPath = Path.Combine(fixture, Versions[0], @"game\msr\private_join.cfg");
        string cfg = File.ReadAllText(cfgPath);
        bool invalid = false;
        try { Prepare(fixture, Versions[0], "host:27025;quit", true); } catch (ArgumentException) { invalid = true; }
        Assert(invalid && cfg == File.ReadAllText(cfgPath), "invalid address rejected before writing");
        string secondPath = Path.Combine(fixture, Versions[1], "player-profile.json");
        File.WriteAllText(secondPath, "{\"profile_key\":\"" + (first == new string('a', 32) ? new string('b', 32) : new string('a', 32)) + "\"}");
        bool mismatch = false;
        try { Prepare(fixture, Versions[0], RealmOne, true, testBackups, true); } catch (InvalidDataException) { mismatch = true; }
        Assert(mismatch && File.ReadAllText(firstPath) == original, "conflicting identities refused");
        string shortcuts = Path.Combine(fixture, "Test Shortcuts");
        CreateShortcuts(fixture, shortcuts);
        object shell = Activator.CreateInstance(Type.GetTypeFromProgID("WScript.Shell", true));
        try
        {
            Dictionary<string, string> expected = new Dictionary<string, string> {
                { "MSR - Join Realm One", "--realm one" }, { "MSR - Join Realm Two", "--realm two" },
                { "MSR", "" }, { "MSR - Dungeon Master", "--dm" }
            };
            foreach (KeyValuePair<string, string> item in expected)
            {
            object shortcut = shell.GetType().InvokeMember("CreateShortcut", BindingFlags.InvokeMethod, null, shell, new object[] { Path.Combine(shortcuts, item.Key + ".lnk") });
            try
            {
                string target = (string)shortcut.GetType().InvokeMember("TargetPath", BindingFlags.GetProperty, null, shortcut, new object[0]);
                string arguments = (string)shortcut.GetType().InvokeMember("Arguments", BindingFlags.GetProperty, null, shortcut, new object[0]);
                Assert(String.Equals(target, Path.Combine(fixture, "MSR-Launcher.exe"), StringComparison.OrdinalIgnoreCase) && arguments == item.Value, "portable native shortcut target and arguments: " + item.Key);
            }
            finally { System.Runtime.InteropServices.Marshal.FinalReleaseComObject(shortcut); }
            }
        }
        finally { System.Runtime.InteropServices.Marshal.FinalReleaseComObject(shell); }
        Assert(Directory.GetFiles(shortcuts, "*.lnk").Length == 4, "four unified launch shortcuts");
        string legacyPath = Path.Combine(shortcuts, "MSR - Enhanced.lnk");
        string foreignPath = Path.Combine(shortcuts, "MSR - Stable Base.lnk");
        object migrationShell = Activator.CreateInstance(Type.GetTypeFromProgID("WScript.Shell", true));
        try
        {
            foreach (string linkPath in new string[] { legacyPath, foreignPath })
            {
                object link = migrationShell.GetType().InvokeMember("CreateShortcut", BindingFlags.InvokeMethod, null, migrationShell, new object[] { linkPath });
                try
                {
                    Property(link, "TargetPath", linkPath == legacyPath ? Path.Combine(fixture, "MSR-Launcher.exe") : Path.Combine(fixture, "Other Installation", "MSR-Launcher.exe"));
                    link.GetType().InvokeMember("Save", BindingFlags.InvokeMethod, null, link, new object[0]);
                }
                finally { System.Runtime.InteropServices.Marshal.FinalReleaseComObject(link); }
            }
        }
        finally { System.Runtime.InteropServices.Marshal.FinalReleaseComObject(migrationShell); }
        string originalLegacy = Convert.ToBase64String(File.ReadAllBytes(legacyPath));
        string originalForeign = Convert.ToBase64String(File.ReadAllBytes(foreignPath));
        CreateShortcuts(fixture, shortcuts);
        Assert(!File.Exists(legacyPath), "owned old edition shortcut consolidated");
        Assert(originalForeign == Convert.ToBase64String(File.ReadAllBytes(foreignPath)), "unrelated old-name shortcut preserved");
        string[] migratedBackups = Directory.GetFiles(Path.Combine(fixture, "Recovery", "Desktop-Shortcut-Backups"), "*.lnk", SearchOption.AllDirectories);
        Assert(migratedBackups.Length == 1 && originalLegacy == Convert.ToBase64String(File.ReadAllBytes(migratedBackups[0])), "exact legacy shortcut backup preserved before removal");
        using (LauncherForm form = new LauncherForm(fixture, Versions[0]))
        {
            int selectors = 0;
            foreach (Control control in form.Controls) if (control is ComboBox) selectors++;
            Assert(selectors == 1, "normal launcher selects a server without an edition selector");
            Assert(form.Text == "MSR", "unified launcher title");
            form.ShowInTaskbar = false;
            form.StartPosition = FormStartPosition.Manual;
            form.Location = new Point(-10000, -10000);
            form.Show();
            Application.DoEvents();
            using (Bitmap preview = new Bitmap(form.Width, form.Height))
            {
                form.DrawToBitmap(preview, new Rectangle(0, 0, form.Width, form.Height));
                preview.Save(Path.Combine(root, "native-launcher-preview.png"), System.Drawing.Imaging.ImageFormat.Png);
            }
            form.Close();
        }
        // A fresh single-game ZIP must not depend on a recovery runtime being present.
        string single = Path.Combine(fixture, "Single Game");
        foreach (string part in Required)
        {
            string file = Path.Combine(single, Versions[0], "game", part);
            Directory.CreateDirectory(Path.GetDirectoryName(file));
            File.WriteAllText(file, "test fixture; no executable content");
        }
        Prepare(single, Versions[0], RealmOne, true, testBackups, true);
        Assert(!Directory.Exists(Path.Combine(single, Versions[1])), "single runtime launch preparation needs no recovery build");
        string dmArgs = NativeHost.Arguments(fixture, Versions[0], "rcon", "realm-two", "ms_dm_grant 31");
        Assert(dmArgs.Contains("--version enhanced --action rcon --server-id realm-two --command \"ms_dm_grant 31\""), "native DM helper contract");
        bool unsafeCommand = false;
        try { NativeHost.Arguments(fixture, Versions[0], "rcon", "realm-one", "status;quit"); } catch (ArgumentException) { unsafeCommand = true; }
        Assert(unsafeCommand, "RCON command chaining rejected");
        bool invalidSlot = false;
        try { NativeHost.Arguments(fixture, Versions[0], "rcon", "realm-one", "ms_dm_grant 32"); } catch (ArgumentException) { invalidSlot = true; }
        Assert(invalidSlot, "invalid DM slot rejected");
        string report = "PASS: relocated path with spaces; new cryptographic identity; existing identity preserved; recovery identity reuse; conflict rejection; metadata/BOM accepted and duplicate identity keys refused; malformed address rejected before changes; windowed client-only launch arguments; all four unified shortcuts created and targets/arguments read back in an isolated fixture; normal launcher has only the server selector; single-runtime preparation; native DM helper command contract; invalid slots and RCON chaining refused.\r\nNo game, service, or real desktop shortcut was started or changed by this self-test.\r\n";
        File.WriteAllText(Path.Combine(root, "native-launcher-self-test.txt"), report);
    }
}

internal sealed class LauncherForm : Form
{
    private readonly string root;
    private readonly ComboBox servers = new ComboBox();
    private readonly TextBox address = new TextBox();
    private readonly CheckBox windowed = new CheckBox();

    internal LauncherForm(string root, string version)
    {
        this.root = root;
        Text = version == "Stable-Base" ? "MSR - Recovery build" : "MSR";
        ClientSize = new Size(640, 412);
        Font = new Font("Segoe UI", 10F);
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false;
        StartPosition = FormStartPosition.CenterScreen;
        AddLabel("Choose a realm, play locally, or open Dungeon Master controls.", 22, 18, 596, 25);
        AddLabel("Server", 22, 65, 140, 25);
        servers.SetBounds(168, 62, 450, 28);
        servers.DropDownStyle = ComboBoxStyle.DropDownList;
        servers.Items.AddRange(new object[] { "Realm One", "Realm Two", "Another server / LAN" });
        servers.SelectedIndexChanged += delegate { address.Text = servers.SelectedIndex == 0 ? MSRLauncher.RealmOne : servers.SelectedIndex == 1 ? MSRLauncher.RealmTwo : "127.0.0.1:27025"; address.ReadOnly = servers.SelectedIndex != 2; };
        Controls.Add(servers);
        AddLabel("Address", 22, 108, 140, 25);
        address.SetBounds(168, 105, 450, 28);
        Controls.Add(address);
        servers.SelectedIndex = 0;
        windowed.Text = "Start in a 1280 x 720 window";
        windowed.SetBounds(168, 146, 450, 28);
        windowed.Checked = true;
        Controls.Add(windowed);
        AddLabel("Join server uses the address above. Play local starts this PC's realms.\nFN keeps your character saves. Your player profile identifies you.", 22, 187, 596, 48);
        Button shortcuts = new Button { Text = "Desktop shortcuts" };
        shortcuts.SetBounds(428, 292, 190, 32);
        shortcuts.Click += delegate { try { if (ProfileRecovery.PrepareForUse(root, version, Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), true)) { MSRLauncher.CreateShortcuts(root); MessageBox.Show("MSR and three direct-access shortcuts were created on your desktop.", "MSR shortcuts"); } } catch (Exception error) { MSRLauncher.ShowError(root, error); } };
        Controls.Add(shortcuts);
        Button join = new Button { Text = "Join server" };
        join.SetBounds(22, 242, 290, 36);
        join.Click += delegate
        {
            try { if (MSRLauncher.Launch(root, version, address.Text, windowed.Checked)) Close(); }
            catch (Exception error) { MSRLauncher.ShowError(root, error); }
        };
        Controls.Add(join);
        Button play = new Button { Text = "Play local" };
        play.SetBounds(328, 242, 290, 36);
        play.Click += delegate { using (HostForm form = new HostForm(root, version, "play")) form.ShowDialog(this); };
        Controls.Add(play);
        Button host = new Button { Text = "Host controls" };
        host.SetBounds(22, 292, 190, 32);
        host.Click += delegate { using (HostForm form = new HostForm(root, version)) form.ShowDialog(this); };
        Controls.Add(host);
        Button dm = new Button { Text = "Dungeon Master", Enabled = version == "Portable-Package" };
        dm.SetBounds(225, 292, 190, 32);
        dm.Click += delegate { using (DMForm form = new DMForm(root)) form.ShowDialog(this); };
        Controls.Add(dm);
        Button recover = new Button { Text = "Recover characters" };
        recover.SetBounds(22, 343, 190, 36);
        recover.Click += delegate { using (ProfileRecoveryForm form = new ProfileRecoveryForm(root, version, false)) form.ShowDialog(this); };
        Controls.Add(recover);
        AddLabel("Reinstalled MSR? Restore your own old player-profile.json.\nProfiles are backed up in Saved Games\\MSR\\Profiles.", 225, 341, 393, 48);
        AcceptButton = join;
    }

    private void AddLabel(string text, int x, int y, int width, int height)
    {
        Label label = new Label { Text = text };
        label.SetBounds(x, y, width, height);
        Controls.Add(label);
    }
}

internal sealed class HostForm : Form
{
    private readonly string root;
    private readonly string version;
    private readonly TextBox output = new TextBox();
    private readonly List<Button> buttons = new List<Button>();
    private bool busy;

    internal HostForm(string root, string version, string initialAction = null)
    {
        this.root = root;
        this.version = version;
        Text = version == "Stable-Base" ? "MSR local host - Recovery build" : "MSR local host";
        ClientSize = new Size(690, 470);
        Font = new Font("Segoe UI", 10F);
        StartPosition = FormStartPosition.CenterParent;
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false;
        Label hint = new Label { Text = version == "Stable-Base" ? "Recovery restores the previous build with save backups. Close the game first.\nSwitching builds disconnects players on the current local realms." : "Play local starts this PC's realms and opens the game. Close the game first.\nIf returning from recovery, local saves are backed up before switching builds." };
        hint.SetBounds(20, 18, 650, 48);
        Controls.Add(hint);
        string[] actions = { "start", "play", "status", "stop" };
        string[] labels = { "Start host", "Play local", "Host status", "Stop host" };
        for (int i = 0; i < actions.Length; i++)
        {
            string action = actions[i];
            Button button = new Button { Text = labels[i] };
            button.SetBounds(20 + i * 165, 80, 150, 36);
            button.Click += delegate { Invoke(action); };
            buttons.Add(button);
            Controls.Add(button);
        }
        output.Multiline = true;
        output.ReadOnly = true;
        output.Font = new Font("Consolas", 9F);
        output.ScrollBars = ScrollBars.Vertical;
        output.SetBounds(20, 135, 645, 270);
        output.Text = "Use Start host, then Play local. Joining the shared Internet realms uses the main launcher's Join server button.";
        Controls.Add(output);
        Button dm = new Button { Text = "Dungeon Master controls", Enabled = version == "Portable-Package" };
        dm.SetBounds(20, 420, 225, 34);
        dm.Click += delegate { using (DMForm form = new DMForm(root)) form.ShowDialog(this); };
        Controls.Add(dm);
        buttons.Add(dm);
        FormClosing += delegate(object sender, FormClosingEventArgs e) { if (busy) e.Cancel = true; };
        if (initialAction != null) Shown += delegate { Invoke(initialAction); };
    }

    private void Invoke(string action)
    {
        if (busy) return;
        busy = true;
        foreach (Button button in buttons) button.Enabled = false;
        output.Text = "Running " + action + "...";
        NativeHost.Run(root, version, action, null, null, delegate(string result)
        {
            busy = false;
            foreach (Button button in buttons) button.Enabled = true;
            buttons[buttons.Count - 1].Enabled = version == "Portable-Package";
            output.Text = result;
        });
    }
}

internal static class NativeHost
{
    internal static string Arguments(string root, string version, string action, string server, string command)
    {
        if (version != "Portable-Package" && version != "Stable-Base") throw new ArgumentException("Invalid host version.");
        if (action != "start" && action != "stop" && action != "status" && action != "play" && action != "rcon") throw new ArgumentException("Invalid host action.");
        string args = "\"" + Path.Combine(root, @"Launcher\native_host.py") + "\" --package-root \"" + root.TrimEnd(Path.DirectorySeparatorChar) + "\" --version " +
            (version == "Stable-Base" ? "stable" : "enhanced") + " --action " + action;
        if (action == "rcon")
        {
            if (server != "realm-one" && server != "realm-two") throw new ArgumentException("Invalid local realm.");
            if (!Regex.IsMatch(command ?? "", @"^(status|ms_dm_revoke|ms_dm_grant ([0-9]|[12][0-9]|3[01])|ms_event (status|on|off|clear|orcs|rats))$"))
                throw new ArgumentException("Invalid Dungeon Master action.");
            args += " --server-id " + server + " --command \"" + command + "\"";
        }
        return args;
    }

    internal static void Run(string root, string version, string action, string server, string command, Action<string> complete)
    {
        string python = Path.Combine(root, version, @"runtime\python.exe");
        if (!File.Exists(python) || !File.Exists(Path.Combine(root, @"Launcher\native_host.py")))
        {
            complete("The native host helper is missing. Extract the complete launcher update into your MSR-PrimeXT-DM folder.");
            return;
        }
        string args;
        try { args = Arguments(root, version, action, server, command); }
        catch (Exception error) { complete(error.Message); return; }
        System.ComponentModel.BackgroundWorker worker = new System.ComponentModel.BackgroundWorker();
        worker.DoWork += delegate(object sender, System.ComponentModel.DoWorkEventArgs e)
        {
            using (Process process = Process.Start(new ProcessStartInfo { FileName = python, Arguments = args, WorkingDirectory = root, UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true, RedirectStandardError = true }))
            {
                if (process == null) throw new InvalidOperationException("Windows did not start the host helper.");
                System.Threading.Tasks.Task<string> errors = System.Threading.Tasks.Task.Factory.StartNew(delegate { return process.StandardError.ReadToEnd(); });
                string text = process.StandardOutput.ReadToEnd();
                process.WaitForExit();
                e.Result = text + errors.Result + (process.ExitCode == 0 ? "" : "\r\nHost operation failed (exit " + process.ExitCode + ").");
            }
        };
        worker.RunWorkerCompleted += delegate(object sender, System.ComponentModel.RunWorkerCompletedEventArgs e)
        {
            complete(e.Error == null ? (string)e.Result : e.Error.Message);
            worker.Dispose();
        };
        worker.RunWorkerAsync();
    }
}

internal sealed class DMForm : Form
{
    private readonly string root;
    private readonly ComboBox realm = new ComboBox();
    private readonly NumericUpDown slot = new NumericUpDown();
    private readonly TextBox output = new TextBox();
    private readonly List<Button> buttons = new List<Button>();
    private bool busy;

    internal DMForm(string root)
    {
        this.root = root;
        Text = "MSR Dungeon Master - local realms";
        ClientSize = new Size(760, 590);
        Font = new Font("Segoe UI", 10F);
        StartPosition = FormStartPosition.CenterParent;
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false;
        Label intro = new Label { Text = "Controls the realms hosted on this PC. Join the game, refresh players,\nthen grant the number beside your name in the # column. In game: G > Dungeon Master." };
        intro.SetBounds(18, 14, 724, 49);
        Controls.Add(intro);
        realm.DropDownStyle = ComboBoxStyle.DropDownList;
        realm.Items.AddRange(new object[] { "Realm One", "Realm Two" });
        realm.SelectedIndex = 0;
        realm.SetBounds(18, 76, 180, 29);
        Controls.Add(realm);
        AddButton("Refresh players", "status", 212, 74, 160);
        Label label = new Label { Text = "Player slot" };
        label.SetBounds(390, 78, 88, 26);
        Controls.Add(label);
        slot.Minimum = 0;
        slot.Maximum = 31;
        slot.SetBounds(484, 75, 64, 30);
        Controls.Add(slot);
        Button grant = AddButton("Grant DM", null, 566, 74, 175);
        grant.Click += delegate { Invoke("ms_dm_grant " + ((int)slot.Value).ToString(System.Globalization.CultureInfo.InvariantCulture)); };
        AddButton("Revoke all grants", "ms_dm_revoke", 18, 119, 180);
        AddButton("Event status", "ms_event status", 212, 119, 160);
        AddButton("Enable random", "ms_event on", 386, 119, 170);
        AddButton("Pause random", "ms_event off", 570, 119, 171);
        AddButton("Clear encounter", "ms_event clear", 18, 164, 180);
        AddButton("Summon Orcs", "ms_event orcs", 212, 164, 160);
        AddButton("Summon rats", "ms_event rats", 386, 164, 170);
        output.SetBounds(18, 218, 723, 319);
        output.Multiline = true;
        output.ReadOnly = true;
        output.Font = new Font("Consolas", 9F);
        output.ScrollBars = ScrollBars.Vertical;
        output.Text = "Start your local host first.\r\nGrants expire on disconnect or map change.\r\nFor shared Internet realms, ask their host to grant control.";
        Controls.Add(output);
        Label note = new Label { Text = "Random events start off. In Edana, stand near the entrance courtyard before summoning." };
        note.SetBounds(18, 551, 724, 28);
        Controls.Add(note);
        FormClosing += delegate(object sender, FormClosingEventArgs e) { if (busy) e.Cancel = true; };
    }

    private Button AddButton(string text, string command, int x, int y, int width)
    {
        Button button = new Button { Text = text };
        button.SetBounds(x, y, width, 34);
        if (command != null) button.Click += delegate { Invoke(command); };
        buttons.Add(button);
        Controls.Add(button);
        return button;
    }

    private void Invoke(string command)
    {
        if (busy) return;
        busy = true;
        foreach (Button button in buttons) button.Enabled = false;
        realm.Enabled = slot.Enabled = false;
        output.Text = "Running " + command + "...";
        NativeHost.Run(root, "Portable-Package", "rcon", realm.SelectedIndex == 0 ? "realm-one" : "realm-two", command, delegate(string result)
        {
            busy = false;
            foreach (Button button in buttons) button.Enabled = true;
            realm.Enabled = slot.Enabled = true;
            output.Text = result;
        });
    }
}
