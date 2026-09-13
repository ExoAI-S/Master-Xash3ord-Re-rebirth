using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Web.Script.Serialization;
using System.Windows.Forms;

internal sealed class ProfileBackup
{
    internal string Path;
    internal string Key;
    internal string Source;
    internal DateTime Saved;
    internal string Label { get { return Saved.ToLocalTime().ToString("yyyy-MM-dd HH:mm") + "  |  " + Source + "  |  " + ProfileRecovery.Fingerprint(Key).Substring(0, 8); } }
}

// Keep uncertainty attached to the candidates so it cannot become an empty,
// apparently successful discovery and silently create a different identity.
internal sealed class ProfileDiscovery : List<ProfileBackup>
{
    internal readonly List<string> Warnings = new List<string>();
    internal ProfileDiscovery() { }
    internal ProfileDiscovery(ProfileDiscovery source) : base(source) { Warnings.AddRange(source.Warnings); }
    internal void Warn(string path) { string warning = "Could not read a valid profile or shortcut: " + path; if (!Warnings.Contains(warning)) Warnings.Add(warning); }
}

// The file boundary permits deterministic failure tests of the real restore body.
internal class ProfileFileAccess
{
    internal virtual void Commit(string staged, string target, bool exists)
    {
        if (exists) File.Replace(staged, target, null);
        else File.Move(staged, target);
    }
}

internal static class ProfileRecovery
{
    private static readonly JavaScriptSerializer Json = new JavaScriptSerializer();
    internal static string BackupDirectory
    {
        get
        {
            string user = Environment.GetEnvironmentVariable("USERPROFILE");
            if (String.IsNullOrEmpty(user) || !Path.IsPathRooted(user)) throw new IOException("Windows did not provide your user folder. Profile backups were not written.");
            return Path.Combine(user, "Saved Games", "MSR", "Profiles");
        }
    }

    internal static string Fingerprint(string key)
    {
        return Hash(Encoding.UTF8.GetBytes(key));
    }

    private static string Hash(byte[] value)
    {
        using (SHA256 hash = SHA256.Create()) return BitConverter.ToString(hash.ComputeHash(value)).Replace("-", "").ToLowerInvariant();
    }

    private static void RegularPath(string path)
    {
        for (string current = Path.GetFullPath(path); !String.IsNullOrEmpty(current); current = Path.GetDirectoryName(current))
            if ((File.Exists(current) || Directory.Exists(current)) && (File.GetAttributes(current) & FileAttributes.ReparsePoint) != 0)
                throw new IOException("Profile recovery cannot write through a linked folder or file. Use the original extracted folder.");
    }

    private static void OutsideInstallation(string root, string backups)
    {
        string install = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        string durable = Path.GetFullPath(backups).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        if (durable.StartsWith(install, StringComparison.OrdinalIgnoreCase)) throw new IOException("Profile backups must be outside the MSR installation.");
        RegularPath(backups);
    }

    internal static List<string> Targets(string root, string version)
    {
        if (version != MSRLauncher.Versions[0] && version != MSRLauncher.Versions[1]) throw new ArgumentException("Invalid game version.");
        if (!Directory.Exists(Path.Combine(root, version))) throw new DirectoryNotFoundException("Choose the launcher from the extracted MSR folder before restoring a profile.");
        List<string> result = new List<string>();
        foreach (string name in MSRLauncher.Versions)
        {
            string folder = Path.Combine(root, name);
            if (!Directory.Exists(folder)) continue;
            string target = Path.Combine(folder, "player-profile.json");
            RegularPath(target);
            result.Add(target);
        }
        return result;
    }

    internal static string PreviousRoot(string target)
    {
        if (String.IsNullOrEmpty(target) || !Path.IsPathRooted(target) || target.StartsWith(@"\\", StringComparison.Ordinal)) return null;
        string name = Path.GetFileName(target);
        string[] allowed = { "MSR-Launcher.exe", "Play-Enhanced.cmd", "Play-Stable.cmd", "Play-MSR.cmd", "Play-Realm-One.cmd", "Play-Realm-Two.cmd" };
        bool known = false;
        foreach (string file in allowed) if (String.Equals(name, file, StringComparison.OrdinalIgnoreCase)) known = true;
        if (!known || !File.Exists(target)) return null;
        string root = Path.GetDirectoryName(Path.GetFullPath(target));
        foreach (string version in MSRLauncher.Versions)
            if (Directory.Exists(Path.Combine(root, version, @"game\msr"))) return root;
        return null;
    }

    internal static ProfileDiscovery DiscoverFromTargets(string backups, IEnumerable<string> shortcutTargets)
    {
        ProfileDiscovery result = ListBackups(backups);
        HashSet<string> seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (ProfileBackup entry in result) seen.Add(Path.GetFullPath(entry.Path));
        foreach (string target in shortcutTargets)
        {
            try
            {
                string prior = PreviousRoot(target);
                if (prior == null) continue;
                ProfileDiscovery folder = ProfilesInSelectedFolder(prior);
                foreach (ProfileBackup entry in folder)
                    if (seen.Add(Path.GetFullPath(entry.Path))) result.Add(entry);
                result.Warnings.AddRange(folder.Warnings);
            }
            catch (InvalidDataException) { result.Warn(target); }
            catch (IOException) { result.Warn(target); }
            catch (UnauthorizedAccessException) { result.Warn(target); }
            catch (ArgumentException) { result.Warn(target); }
        }
        return result;
    }

    internal static ProfileDiscovery Discover(string backups, string desktop)
    {
        List<string> targets = new List<string>();
        ProfileDiscovery warnings = new ProfileDiscovery();
        try
        {
            if (!DirectoryAvailable(desktop, warnings)) return MergeWarnings(DiscoverFromTargets(backups, targets), warnings);
            object shell = Activator.CreateInstance(Type.GetTypeFromProgID("WScript.Shell", true));
            try
            {
                foreach (string name in new string[] { "MSR", "MSR - Join Realm One", "MSR - Join Realm Two", "MSR - Dungeon Master", "MSR - Enhanced", "MSR - Stable Base" })
                {
                    string path = Path.Combine(desktop, name + ".lnk");
                    try
                    {
                        if (!FileAvailable(path, warnings)) continue;
                        object link = shell.GetType().InvokeMember("CreateShortcut", BindingFlags.InvokeMethod, null, shell, new object[] { path });
                        try { targets.Add((string)link.GetType().InvokeMember("TargetPath", BindingFlags.GetProperty, null, link, new object[0])); }
                        finally { Marshal.FinalReleaseComObject(link); }
                    }
                    catch (IOException) { warnings.Warn(path); }
                    catch (UnauthorizedAccessException) { warnings.Warn(path); }
                    catch (COMException) { warnings.Warn(path); }
                    catch (TargetInvocationException) { warnings.Warn(path); }
                }
            }
            finally { Marshal.FinalReleaseComObject(shell); }
        }
        catch (COMException) { warnings.Warn(desktop); }
        catch (TargetInvocationException) { warnings.Warn(desktop); }
        return MergeWarnings(DiscoverFromTargets(backups, targets), warnings);
    }

    private static ProfileDiscovery MergeWarnings(ProfileDiscovery result, ProfileDiscovery other)
    {
        result.Warnings.AddRange(other.Warnings);
        return result;
    }

    private static bool Available(string path, bool directory, ProfileDiscovery result)
    {
        try
        {
            bool isDirectory = (File.GetAttributes(path) & FileAttributes.Directory) != 0;
            if (isDirectory != directory) { result.Warn(path); return false; }
            return true;
        }
        catch (FileNotFoundException) { return false; }
        catch (DirectoryNotFoundException) { return false; }
        catch (IOException) { result.Warn(path); return false; }
        catch (UnauthorizedAccessException) { result.Warn(path); return false; }
    }

    private static bool FileAvailable(string path, ProfileDiscovery result) { return Available(path, false, result); }
    private static bool DirectoryAvailable(string path, ProfileDiscovery result) { return Available(path, true, result); }

    // False means discovery is uncertain or identities conflict; the user must choose.
    internal static bool TryPrepareFresh(string root, string version, string backups, ProfileDiscovery candidates, Action<string> assertStopped)
    {
        List<string> targets = Targets(root, version);
        bool existing = false;
        foreach (string target in targets) if (File.Exists(target)) existing = true;
        if (existing)
        {
            using (FileStream guard = MSRLauncher.LockProfile(root))
                foreach (string target in targets) if (File.Exists(target)) BackupFile(target, backups, root, Path.GetFileName(Path.GetDirectoryName(target)));
            return candidates.Warnings.Count == 0; // An existing identity is never replaced.
        }
        if (candidates.Warnings.Count != 0) return false;
        HashSet<string> keys = new HashSet<string>();
        foreach (ProfileBackup entry in candidates) keys.Add(entry.Key);
        if (keys.Count > 1) return false;
        if (keys.Count == 1)
        {
            Restore(root, version, candidates[0].Path, backups, assertStopped, new ProfileFileAccess(), true, candidates[0].Key);
            return true;
        }
        using (FileStream launch = MSRLauncher.LockClientLaunch(root))
        {
            assertStopped(root);
            MSRLauncher.PrepareIdentity(root, version, backups, false);
        }
        return true;
    }

    internal static bool PrepareForUse(string root, string version, string desktop, bool beforeShortcutReplacement = false)
    {
        string backups = BackupDirectory;
        // Do not inspect old shortcuts when this install already has a profile.
        bool existing = false;
        foreach (string target in Targets(root, version)) if (File.Exists(target)) existing = true;
        ProfileDiscovery candidates = existing && !beforeShortcutReplacement ? new ProfileDiscovery() : Discover(backups, desktop);
        if (beforeShortcutReplacement)
            foreach (ProfileBackup entry in candidates)
            {
                try { BackupFile(entry.Path, backups, root, version); }
                catch (InvalidDataException) { candidates.Warn(entry.Path); }
                catch (IOException) { candidates.Warn(entry.Path); }
                catch (UnauthorizedAccessException) { candidates.Warn(entry.Path); }
            }
        if (TryPrepareFresh(root, version, backups, candidates, MSRLauncher.AssertNoRunningClient)) return true;
        using (ProfileRecoveryForm recovery = new ProfileRecoveryForm(root, version, !existing, backups, candidates))
        {
            DialogResult choice = recovery.ShowDialog();
            if (choice == DialogResult.OK) return true;
            if (choice != DialogResult.No) return false;
            using (FileStream launch = MSRLauncher.LockClientLaunch(root))
            {
                MSRLauncher.AssertNoRunningClient(root);
                MSRLauncher.PrepareIdentity(root, version, backups, true);
            }
            return true;
        }
    }

    internal static ProfileDiscovery ListBackups(string directory)
    {
        ProfileDiscovery result = new ProfileDiscovery();
        string[] paths;
        try
        {
            if (!DirectoryAvailable(directory, result)) return result;
            RegularPath(directory);
            paths = Directory.GetFiles(directory, "profile-*.json", SearchOption.TopDirectoryOnly);
        }
        catch (IOException) { result.Warn(directory); return result; }
        catch (UnauthorizedAccessException) { result.Warn(directory); return result; }
        foreach (string path in paths)
        {
            try
            {
                string key = MSRLauncher.ReadKey(path);
                string source = "Saved profile";
                string meta = path + ".meta";
                try
                {
                    if (FileAvailable(meta, result) && new FileInfo(meta).Length < 65536)
                    {
                        Dictionary<string, object> data = Json.DeserializeObject(File.ReadAllText(meta)) as Dictionary<string, object>;
                        object value;
                        if (data != null && data.TryGetValue("source_folder", out value) && value is string) source = (string)value;
                    }
                }
                catch (ArgumentException) { result.Warn(meta); }
                catch (IOException) { result.Warn(meta); }
                catch (UnauthorizedAccessException) { result.Warn(meta); }
                result.Add(new ProfileBackup { Path = path, Key = key, Source = source, Saved = File.GetLastWriteTimeUtc(path) });
            }
            catch (InvalidDataException) { result.Warn(path); }
            catch (IOException) { result.Warn(path); }
            catch (UnauthorizedAccessException) { result.Warn(path); }
        }
        result.Sort(delegate(ProfileBackup a, ProfileBackup b) { return b.Saved.CompareTo(a.Saved); });
        return result;
    }

    internal static ProfileDiscovery ProfilesInSelectedFolder(string folder)
    {
        // Only the folder explicitly selected, and its two documented runtime folders.
        ProfileDiscovery result = new ProfileDiscovery();
        foreach (string relative in new string[] { "player-profile.json", @"Portable-Package\player-profile.json", @"Stable-Base\player-profile.json" })
        {
            string path = Path.Combine(folder, relative);
            try
            {
                if (!FileAvailable(path, result)) continue;
                result.Add(new ProfileBackup { Path = path, Key = MSRLauncher.ReadKey(path), Source = Path.GetDirectoryName(path), Saved = File.GetLastWriteTimeUtc(path) });
            }
            catch (InvalidDataException) { result.Warn(path); }
            catch (IOException) { result.Warn(path); }
            catch (UnauthorizedAccessException) { result.Warn(path); }
        }
        return result;
    }

    private static byte[] ReadBytes(string path)
    {
        // Preserve even a damaged current profile, but never load arbitrary huge files.
        if (new FileInfo(path).Length > 4 * 1024 * 1024) throw new InvalidDataException("This profile file is unexpectedly large. It was not overwritten.");
        return File.ReadAllBytes(path);
    }

    private static string Stage(string directory, byte[] bytes)
    {
        string path = Path.Combine(directory, ".profile-" + Guid.NewGuid().ToString("N") + ".tmp");
        using (FileStream stream = new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.None))
        {
            stream.Write(bytes, 0, bytes.Length);
            stream.Flush(true);
        }
        return path;
    }

    internal static string BackupFile(string path, string backups, string root, string version)
    {
        return BackupBytes(ReadBytes(path), path, backups, root);
    }

    private static string BackupBytes(byte[] bytes, string path, string backups, string root)
    {
        OutsideInstallation(root, backups);
        bool valid = true;
        try { MSRLauncher.ReadKeyContent(bytes, path); } catch (InvalidDataException) { valid = false; }
        Directory.CreateDirectory(backups);
        string target = Path.Combine(backups, (valid ? "profile-" : "unreadable-") + Hash(bytes) + (valid ? ".json" : ".backup"));
        RegularPath(target);
        if (File.Exists(target))
        {
            if (Hash(File.ReadAllBytes(target)) != Hash(bytes)) throw new IOException("An existing profile backup differs from its recorded content. It was not overwritten.");
            return target;
        }
        string staged = Stage(backups, bytes);
        try
        {
            try { File.Move(staged, target); }
            catch (IOException)
            {
                // Another installation may back up the exact same profile concurrently.
                if (!File.Exists(target) || Hash(File.ReadAllBytes(target)) != Hash(bytes)) throw;
            }
            string metadata = Json.Serialize(new Dictionary<string, object> { { "source_folder", Path.GetFullPath(Path.GetDirectoryName(path)) }, { "saved_utc", DateTime.UtcNow.ToString("o") } });
            string metaStage = Stage(backups, Encoding.UTF8.GetBytes(metadata));
            try { if (!File.Exists(target + ".meta")) File.Move(metaStage, target + ".meta"); }
            finally { if (File.Exists(metaStage)) File.Delete(metaStage); }
            return target;
        }
        finally { if (File.Exists(staged)) File.Delete(staged); }
    }

    internal static bool Restore(string root, string version, string selected)
    {
        return Restore(root, version, selected, BackupDirectory, MSRLauncher.AssertNoRunningClient, new ProfileFileAccess());
    }

    internal static bool Restore(string root, string version, string selected, string backups, Action<string> assertStopped, ProfileFileAccess files, bool onlyIfFresh = false, string expectedKey = null)
    {
        OutsideInstallation(root, backups);
        using (FileStream launch = MSRLauncher.LockClientLaunch(root))
        using (FileStream profile = MSRLauncher.LockProfile(root))
        {
            assertStopped(root);
            byte[] replacement = ReadBytes(selected);
            string incoming = MSRLauncher.ReadKeyContent(replacement, selected);
            if (expectedKey != null && incoming != expectedKey) throw new IOException("The selected profile changed. Choose it again; no installed identity was replaced.");
            List<string> targets = Targets(root, version);
            if (onlyIfFresh) foreach (string target in targets) if (File.Exists(target)) return false;
            Dictionary<string, byte[]> originals = new Dictionary<string, byte[]>();
            Dictionary<string, string> staged = new Dictionary<string, string>();
            List<string> committed = new List<string>();
            try
            {
                foreach (string target in targets)
                {
                    byte[] current = File.Exists(target) ? ReadBytes(target) : null;
                    originals.Add(target, current);
                    bool same = false;
                    if (current != null)
                    {
                        try { same = MSRLauncher.ReadKeyContent(current, target) == incoming; } catch (InvalidDataException) { }
                        BackupBytes(current, target, backups, root);
                    }
                    if (!same) staged.Add(target, Stage(Path.GetDirectoryName(target), replacement));
                }
                // Ensure the chosen identity is durable even for an empty new installation.
                BackupBytes(replacement, selected, backups, root);
                assertStopped(root);
                foreach (KeyValuePair<string, byte[]> item in originals)
                {
                    byte[] now = File.Exists(item.Key) ? ReadBytes(item.Key) : null;
                    if ((now == null) != (item.Value == null) || (now != null && Hash(now) != Hash(item.Value)))
                        throw new IOException("An installed profile changed during recovery. No profiles were replaced. Choose the profile again after the other change finishes.");
                }
                foreach (KeyValuePair<string, string> item in staged)
                {
                    files.Commit(item.Value, item.Key, originals[item.Key] != null);
                    committed.Add(item.Key);
                }
                return committed.Count != 0;
            }
            catch (Exception failure)
            {
                bool rollbackFailed = false;
                for (int i = committed.Count - 1; i >= 0; i--)
                {
                    string target = committed[i];
                    try
                    {
                        byte[] original = originals[target];
                        if (original == null) File.Delete(target);
                        else
                        {
                            string restore = Stage(Path.GetDirectoryName(target), original);
                            try { files.Commit(restore, target, true); }
                            finally { if (File.Exists(restore)) File.Delete(restore); }
                        }
                    }
                    catch { rollbackFailed = true; }
                }
                if (rollbackFailed) throw new IOException("The restore could not finish or fully roll back. Keep both installed profiles and the backups in " + backups + ". Do not start MSR until you restore the matching profile to both builds.", failure);
                throw;
            }
            finally
            {
                foreach (string path in staged.Values) if (File.Exists(path)) File.Delete(path);
            }
        }
    }
}

internal sealed class ProfileRecoveryForm : Form
{
    private readonly string root;
    private readonly string version;
    private readonly ListBox profiles = new ListBox();
    private readonly Label detail = new Label();
    private readonly List<ProfileBackup> choices = new List<ProfileBackup>();
    private readonly Button restore = new Button { Text = "Restore selected profile", Enabled = false };
    private readonly Label warningTitle = new Label { Text = "Some locations could not be read. Choose a valid profile or your own old file.", Visible = false };
    private readonly TextBox warningText = new TextBox { Name = "DiscoveryWarnings", Multiline = true, ReadOnly = true, ScrollBars = ScrollBars.Both, WordWrap = false, Visible = false };
    private readonly List<string> warnings = new List<string>();
    private readonly List<Control> lowerControls = new List<Control>();
    private int warningOffset;

    internal ProfileRecoveryForm(string root, string version, bool fresh) : this(root, version, fresh, ProfileRecovery.BackupDirectory, Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory)) { }

    // The production discovery path is also usable with a synthetic desktop in tests.
    internal ProfileRecoveryForm(string root, string version, bool fresh, string backups, string desktop) : this(root, version, fresh, backups, ProfileRecovery.Discover(backups, desktop)) { }

    internal ProfileRecoveryForm(string root, string version, bool fresh, string backups) : this(root, version, fresh, backups, ProfileRecovery.ListBackups(backups)) { }

    internal ProfileRecoveryForm(string root, string version, bool fresh, string backups, ProfileDiscovery discovered)
    {
        this.root = root; this.version = version;
        Text = "Restore player profile";
        ClientSize = new Size(790, fresh ? 458 : 414);
        Font = new Font("Segoe UI", 10F);
        FormBorderStyle = FormBorderStyle.FixedDialog; MaximizeBox = false;
        StartPosition = FormStartPosition.CenterParent;
        Label intro = new Label { Text = "FN keeps your character saves. Your player profile identifies you.\nChoose your own old player-profile.json or a backup. This does not copy FN saves.", AutoSize = false };
        intro.SetBounds(20, 16, 750, 50); Controls.Add(intro);
        Button file = new Button { Text = "Choose old profile..." }; file.SetBounds(20, 78, 235, 34);
        file.Click += delegate
        {
            using (OpenFileDialog picker = new OpenFileDialog { Title = "Choose your own old player-profile.json", Filter = "Player profiles (*.json)|*.json", FileName = "player-profile.json", CheckFileExists = true, Multiselect = false })
                if (picker.ShowDialog(this) == DialogResult.OK)
                    Attempt(delegate { AddChoice(new ProfileBackup { Path = picker.FileName, Key = MSRLauncher.ReadKey(picker.FileName), Source = Path.GetDirectoryName(picker.FileName), Saved = File.GetLastWriteTimeUtc(picker.FileName) }, true); });
        };
        Controls.Add(file);
        Button folder = new Button { Text = "Choose old MSR folder..." }; folder.SetBounds(270, 78, 245, 34);
        folder.Click += delegate
        {
            using (FolderBrowserDialog picker = new FolderBrowserDialog { Description = "Choose your own old MSR folder or its Portable-Package / Stable-Base folder.", ShowNewFolderButton = false })
                if (picker.ShowDialog(this) == DialogResult.OK) Attempt(delegate
                {
                    ProfileDiscovery found = ProfileRecovery.ProfilesInSelectedFolder(picker.SelectedPath);
                    ShowWarnings(found.Warnings);
                    if (found.Count == 0 && found.Warnings.Count == 0) throw new FileNotFoundException("No player-profile.json was found in that folder or its two MSR runtime folders. Choose the profile file directly.");
                    foreach (ProfileBackup entry in found) AddChoice(entry, false);
                    profiles.ClearSelected();
                });
        };
        Controls.Add(folder);
        Label saved = new Label { Text = "Saved date  |  Original folder  |  Profile reference" }; saved.SetBounds(20, 129, 750, 23); Controls.Add(saved);
        profiles.SetBounds(20, 155, 750, 137); profiles.HorizontalScrollbar = true;
        profiles.SelectedIndexChanged += delegate
        {
            restore.Enabled = profiles.SelectedIndex >= 0;
            detail.Text = restore.Enabled ? "The current profile will be backed up first.\nBoth installed MSR builds will use the selected profile." : "Select a profile, or choose your own old profile file above.";
        };
        Controls.Add(profiles);
        detail.Text = "Select a profile, or choose your own old profile file above."; detail.SetBounds(20, 305, 750, 52); Controls.Add(detail);
        lowerControls.Add(detail);
        restore.SetBounds(20, 369, 255, 34);
        restore.Click += delegate { Attempt(delegate
        {
            if (profiles.SelectedIndex < 0) return;
            bool changed = ProfileRecovery.Restore(root, version, choices[profiles.SelectedIndex].Path, backups, MSRLauncher.AssertNoRunningClient, new ProfileFileAccess(), false, choices[profiles.SelectedIndex].Key);
            MessageBox.Show(this, changed ? "Your player profile was restored. Join the same realm to load your existing characters." : "This profile is already active. Its outside-install backup is ready.", "Player profile ready", MessageBoxButtons.OK, MessageBoxIcon.Information);
            DialogResult = DialogResult.OK; Close();
        }); };
        Controls.Add(restore);
        lowerControls.Add(restore);
        Button cancel = new Button { Text = "Cancel", DialogResult = DialogResult.Cancel }; cancel.SetBounds(645, 369, 125, 34); Controls.Add(cancel); CancelButton = cancel;
        lowerControls.Add(cancel);
        if (fresh)
        {
            Button startNew = new Button { Text = "Start a new profile" }; startNew.SetBounds(20, 413, 255, 34);
            startNew.Click += delegate
            {
                if (MessageBox.Show(this, "A new profile has a different identity. Existing characters remain with your old profile on FN. Start a new profile?", "Start a new profile", MessageBoxButtons.YesNo, MessageBoxIcon.Question) == DialogResult.Yes)
                { DialogResult = DialogResult.No; Close(); }
            };
            Controls.Add(startNew);
            lowerControls.Add(startNew);
        }
        warningTitle.SetBounds(20, 305, 750, 23); Controls.Add(warningTitle);
        warningText.SetBounds(20, 331, 750, 76); Controls.Add(warningText);
        foreach (ProfileBackup entry in discovered) AddChoice(entry, false);
        ShowWarnings(discovered.Warnings);
    }

    private void ShowWarnings(IEnumerable<string> found)
    {
        foreach (string warning in found) if (!warnings.Contains(warning)) warnings.Add(warning);
        if (warnings.Count == 0) return;
        int extra = 120 - warningOffset;
        foreach (Control control in lowerControls) control.Top += extra;
        ClientSize = new Size(ClientSize.Width, ClientSize.Height + extra);
        warningOffset = 120;
        warningTitle.Visible = true;
        warningText.Visible = true;
        warningText.Text = String.Join(Environment.NewLine, warnings.ToArray());
    }

    private void AddChoice(ProfileBackup entry, bool select)
    {
        for (int i = 0; i < choices.Count; i++) if (String.Equals(choices[i].Path, entry.Path, StringComparison.OrdinalIgnoreCase)) { if (select) profiles.SelectedIndex = i; return; }
        choices.Add(entry); profiles.Items.Add(entry.Label);
        if (select) profiles.SelectedIndex = choices.Count - 1;
    }

    private void Attempt(Action action)
    {
        try { action(); }
        catch (Exception error) { MessageBox.Show(this, error.Message, "Profile was not restored", MessageBoxButtons.OK, MessageBoxIcon.Error); }
    }
}
