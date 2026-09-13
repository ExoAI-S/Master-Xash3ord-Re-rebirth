using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using System.Windows.Forms;

internal static class RecoveryTests
{
    static int checks;
    static string work;
    static string backups;
    static readonly string v = MSRLauncher.Versions[0];
    static void Check(bool value, string name) { if (!value) throw new Exception("FAIL: " + name); checks++; Console.WriteLine("PASS: " + name); }
    static void Throws<T>(Action action, string name) where T : Exception { bool caught = false; try { action(); } catch (T) { caught = true; } Check(caught, name); }
    static string Package(string name, bool paired)
    {
        string root = Path.Combine(work, name);
        foreach (string version in paired ? MSRLauncher.Versions : new string[] { v })
            foreach (string item in MSRLauncher.Required)
            {
                string file = Path.Combine(root, version, "game", item);
                Directory.CreateDirectory(Path.GetDirectoryName(file)); File.WriteAllText(file, "INERT fixture; never execute");
            }
        File.WriteAllText(Path.Combine(root, "MSR-Launcher.exe"), "INERT shortcut target; never execute");
        return root;
    }
    static string Profile(string root, string version, string key)
    {
        string path = Path.Combine(root, version, "player-profile.json");
        File.WriteAllText(path, "{\"profile_key\":\"" + key + "\",\"fixture_metadata\":\"retain exact bytes\"}", new UTF8Encoding(true));
        return path;
    }
    static string Bytes(string path) { return Convert.ToBase64String(File.ReadAllBytes(path)); }
    static bool Restore(string root, string selected) { return ProfileRecovery.Restore(root, v, selected, backups, delegate { }, new ProfileFileAccess()); }
    sealed class FailSecond : ProfileFileAccess
    {
        int calls;
        internal override void Commit(string staged, string target, bool exists) { if (++calls == 2) throw new IOException("inert second-commit failure"); base.Commit(staged, target, exists); }
    }
    static void Shortcut(string desktop, string name, string target)
    {
        Directory.CreateDirectory(desktop);
        object shell = Activator.CreateInstance(Type.GetTypeFromProgID("WScript.Shell", true));
        object link = shell.GetType().InvokeMember("CreateShortcut", BindingFlags.InvokeMethod, null, shell, new object[] { Path.Combine(desktop, name + ".lnk") });
        try { link.GetType().InvokeMember("TargetPath", BindingFlags.SetProperty, null, link, new object[] { target }); link.GetType().InvokeMember("Save", BindingFlags.InvokeMethod, null, link, new object[0]); }
        finally { Marshal.FinalReleaseComObject(link); Marshal.FinalReleaseComObject(shell); }
    }
    static bool HasButton(Form form, string text)
    {
        foreach (Control control in form.Controls) if (control is Button && control.Text == text) return true;
        return false;
    }
    static void Render(Form form, string name)
    {
        using (form)
        {
            form.StartPosition = FormStartPosition.Manual; form.Location = new Point(-32000, -32000); form.ShowInTaskbar = false;
            form.Show(); Application.DoEvents();
            foreach (Control control in form.Controls) { IntPtr handle = control.Handle; ListBox list = control as ListBox; if (list != null && list.Items.Count > 0) list.SelectedIndex = 0; }
            form.PerformLayout(); Application.DoEvents();
            using (Bitmap image = new Bitmap(form.Width, form.Height)) { form.DrawToBitmap(image, new Rectangle(0, 0, image.Width, image.Height)); image.Save(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, name)); }
            foreach (Control control in form.Controls) Check(control.Right <= form.ClientSize.Width && control.Bottom <= form.ClientSize.Height, name + " control bounds: " + control.GetType().Name);
        }
    }
    [STAThread] static int Main()
    {
        try
        {
            Application.EnableVisualStyles(); Application.SetCompatibleTextRenderingDefault(false);
            work = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "fixtures", Guid.NewGuid().ToString("N"));
            backups = Path.Combine(work, "Saved Games", "MSR", "Profiles"); Directory.CreateDirectory(work);
            string old = Package("Own old MSR", true), current = Package("New MSR", true);
            string keyOld = Guid.NewGuid().ToString("N"), keyNew = Guid.NewGuid().ToString("N"), keyOther = Guid.NewGuid().ToString("N");
            string source = Profile(old, v, keyOld), first = Profile(current, v, keyNew), second = Profile(current, MSRLauncher.Versions[1], keyOther);
            string originalFirst = Bytes(first), originalSecond = Bytes(second);
            Check(MSRLauncher.ReadKey(source) == keyOld, "BOM and metadata accepted by actual ReadKey");
            string invalid = Path.Combine(work, "invalid.json"); File.WriteAllText(invalid, "{\"profile_key\":\"bad\"}");
            Throws<InvalidDataException>(delegate { Restore(current, invalid); }, "invalid imported key rejected");
            File.WriteAllText(invalid, "{\"profile_key\":\"" + keyOld + "\",\"profile_key\":\"" + keyOld + "\"}");
            Throws<InvalidDataException>(delegate { Restore(current, invalid); }, "duplicate imported key rejected");
            File.WriteAllText(invalid, File.ReadAllText(source) + " {}");
            Throws<InvalidDataException>(delegate { Restore(current, invalid); }, "trailing JSON rejected");
            Check(Bytes(first) == originalFirst && Bytes(second) == originalSecond, "invalid imports preserve both installed files");
            Throws<InvalidOperationException>(delegate { ProfileRecovery.Restore(current, v, source, backups, delegate(string root) { MSRLauncher.AssertClientRecord(root, Path.Combine(root, v, @"game\xash3d.exe"), "-game msr"); }, new ProfileFileAccess()); }, "actual running-client guard blocks restore");
            Check(Bytes(first) == originalFirst && !Directory.Exists(backups), "running client preserves files and creates no backup/commit");
            MSRLauncher.AssertClientRecord(current, Path.Combine(current, v, @"game\xash3d.exe"), "-dedicated -game msr"); Check(true, "dedicated host is not mistaken for a running client");
            Throws<InvalidOperationException>(delegate { MSRLauncher.AssertClientRecord(current, null, null); }, "unknown process path fails closed");
            using (FileStream guard = MSRLauncher.LockClientLaunch(current)) Throws<IOException>(delegate { Restore(current, source); }, "client launch lock excludes recovery");
            using (FileStream guard = MSRLauncher.LockProfile(current)) Throws<IOException>(delegate { Restore(current, source); }, "profile lock excludes recovery");
            Throws<IOException>(delegate { ProfileRecovery.Restore(current, v, source, backups, delegate { }, new FailSecond()); }, "inert second atomic replace fails");
            Check(Bytes(first) == originalFirst && Bytes(second) == originalSecond, "first replace rolls back exactly on second failure");
            List<ProfileBackup> before = ProfileRecovery.ListBackups(backups);
            Check(before.Exists(delegate(ProfileBackup b) { return b.Key == keyNew && Bytes(b.Path) == originalFirst; }), "current profile backed up outside install before commit");
            Check(before.Exists(delegate(ProfileBackup b) { return b.Key == keyOther && Bytes(b.Path) == originalSecond; }), "different paired profile backed up before commit");
            Check(Restore(current, source), "explicit old file restore succeeds");
            Check(MSRLauncher.ReadKey(first) == keyOld && MSRLauncher.ReadKey(second) == keyOld, "both installed runtimes use selected identity");
            Check(Bytes(first) == Bytes(source), "restored profile exact source bytes");
            string sameBytes = Bytes(first); DateTime sameTime = File.GetLastWriteTimeUtc(first);
            Check(!Restore(current, source), "same-profile restore is idempotent");
            Check(Bytes(first) == sameBytes && File.GetLastWriteTimeUtc(first) == sameTime, "same-profile restore does not rewrite current file");
            string durableOld = ProfileRecovery.ListBackups(backups).Find(delegate(ProfileBackup b) { return b.Key == keyOld; }).Path;
            string fresh = Package("Fresh later installation", false);
            Check(Restore(fresh, durableOld), "restore from registry backup succeeds on new root");
            Check(MSRLauncher.ReadKey(Path.Combine(fresh, v, "player-profile.json")) == keyOld, "outside-install backup finds original identity after reinstall");
            Check(!Directory.Exists(Path.Combine(fresh, MSRLauncher.Versions[1])), "single runtime restore does not create Stable-Base");
            File.WriteAllText(first, "damaged current profile"); string damaged = Bytes(first);
            Check(Restore(current, source), "damaged current profile can be explicitly recovered");
            bool damagedSaved = false; foreach (string path in Directory.GetFiles(backups, "unreadable-*.backup")) if (Bytes(path) == damaged) damagedSaved = true;
            Check(damagedSaved, "damaged current bytes preserved outside install");
            string changedSource = Path.Combine(work, "changed-selection.json"); File.Copy(source, changedSource);
            Throws<IOException>(delegate { ProfileRecovery.Restore(current, v, changedSource, backups, delegate { }, new ProfileFileAccess(), false, keyOther); }, "changed selection rejected before commit");
            Check(MSRLauncher.ReadKey(first) == keyOld, "selection mismatch preserves current identity");
            string driftRoot = Package("Target drift test", true), driftA = Profile(driftRoot, v, keyNew), driftB = Profile(driftRoot, MSRLauncher.Versions[1], keyNew);
            int guardCalls = 0;
            Throws<IOException>(delegate { ProfileRecovery.Restore(driftRoot, v, source, backups, delegate { if (++guardCalls == 2) Profile(driftRoot, v, keyOther); }, new ProfileFileAccess()); }, "target drift after staging aborts before commit");
            Check(MSRLauncher.ReadKey(driftA) == keyOther && MSRLauncher.ReadKey(driftB) == keyNew, "target drift keeps external change and untouched paired file");
            string movingSource = Path.Combine(work, "source-drift.json"); File.Copy(source, movingSource); string capturedSource = Bytes(movingSource);
            string driftCache = Path.Combine(work, "Source snapshot registry"); int sourceGuards = 0;
            Check(ProfileRecovery.Restore(driftRoot, v, movingSource, driftCache, delegate { if (++sourceGuards == 2) File.WriteAllText(movingSource, "{\"profile_key\":\"" + keyOther + "\"}"); }, new ProfileFileAccess()), "source change after snapshot does not change selected replacement");
            Check(Bytes(driftA) == capturedSource && ProfileRecovery.ListBackups(driftCache).Exists(delegate(ProfileBackup b) { return Bytes(b.Path) == capturedSource; }), "captured replacement bytes have exact durable backup despite source change");
            string failedBackup = Path.Combine(work, "not-a-backup-directory"); File.WriteAllText(failedBackup, "inert");
            string beforeBackupFailure = Bytes(driftA);
            Throws<IOException>(delegate { ProfileRecovery.Restore(driftRoot, v, movingSource, failedBackup, delegate { }, new ProfileFileAccess()); }, "backup failure aborts restore");
            Check(Bytes(driftA) == beforeBackupFailure && Bytes(driftB) == beforeBackupFailure, "backup failure preserves both profiles exactly");
            string automatic = Package("Automatic new install", false), emptyCache = Path.Combine(work, "Empty durable cache");
            ProfileDiscovery clear = ProfileRecovery.DiscoverFromTargets(emptyCache, new string[] { Path.Combine(old, "MSR-Launcher.exe") });
            Check(clear.Count == 1 && clear[0].Key == keyOld, "unique previous shortcut target discovers original");
            Check(ProfileRecovery.TryPrepareFresh(automatic, v, emptyCache, clear, delegate { }), "fresh unique shortcut identity recovered automatically");
            Check(MSRLauncher.ReadKey(Path.Combine(automatic, v, "player-profile.json")) == keyOld, "automatic recovery restored old key");
            string conflictRoot = Package("Conflicting fresh install", false);
            ProfileDiscovery conflict = ProfileRecovery.DiscoverFromTargets(backups, new string[] { Path.Combine(old, "MSR-Launcher.exe") });
            Check(!ProfileRecovery.TryPrepareFresh(conflictRoot, v, backups, conflict, delegate { }), "conflicting cache plus shortcut requires selection");
            Check(!File.Exists(Path.Combine(conflictRoot, v, "player-profile.json")), "conflict creates no new profile");
            string existing = Package("Existing real new identity", false), existingFile = Profile(existing, v, keyNew); string existingBytes = Bytes(existingFile);
            Check(ProfileRecovery.TryPrepareFresh(existing, v, backups, clear, delegate { }), "existing profile remains usable");
            Check(Bytes(existingFile) == existingBytes, "existing new identity never silently overwritten");
            ProfileDiscovery duplicates = new ProfileDiscovery(clear); duplicates.Add(clear[0]);
            string agreed = Package("Repeated same identity", false);
            Check(ProfileRecovery.TryPrepareFresh(agreed, v, emptyCache, duplicates, delegate { }), "several sources agreeing on one identity are unambiguous");
            string noPrevious = Package("First install no candidates", false), firstCache = Path.Combine(work, "Empty first install registry");
            Check(ProfileRecovery.TryPrepareFresh(noPrevious, v, firstCache, new ProfileDiscovery(), delegate { }), "no candidates permits normal new profile creation");
            string newIdentity = MSRLauncher.ReadKey(Path.Combine(noPrevious, v, "player-profile.json"));
            Check(newIdentity != keyOld && ProfileRecovery.ListBackups(firstCache).Count == 1, "new identity has a durable backup immediately");
            Check(ProfileRecovery.PreviousRoot(Path.Combine(old, "Other.exe")) == null && ProfileRecovery.PreviousRoot(@"\\foreign\share\MSR-Launcher.exe") == null, "foreign target and network target filtered");
            string wrongLayout = Path.Combine(work, "Wrong layout"); Directory.CreateDirectory(wrongLayout); File.WriteAllText(Path.Combine(wrongLayout, "MSR-Launcher.exe"), "inert");
            Check(ProfileRecovery.PreviousRoot(Path.Combine(wrongLayout, "MSR-Launcher.exe")) == null, "invalid MSR target layout filtered");
            string desktop = Path.Combine(work, "Synthetic user desktop"); Shortcut(desktop, "MSR", Path.Combine(old, "MSR-Launcher.exe"));
            Shortcut(desktop, "Unrelated shortcut", Path.Combine(existing, "MSR-Launcher.exe"));
            ProfileDiscovery desktopFound = ProfileRecovery.Discover(Path.Combine(work, "No desktop cache"), desktop);
            Check(desktopFound.Count == 1 && desktopFound[0].Key == keyOld, "actual COM discovery reads only canonical synthetic user shortcut");
            string damagedOld = Package("Discovery damaged old installation", true);
            string damagedRuntime = Profile(damagedOld, v, keyOld); File.WriteAllText(damagedRuntime, "damaged profile fixture");
            string intactRuntime = Profile(damagedOld, MSRLauncher.Versions[1], keyOld);
            string warningCache = Path.Combine(work, "Discovery warning cache");
            ProfileRecovery.BackupFile(source, warningCache, current, v);
            string warningDesktop = Path.Combine(work, "Discovery warning desktop"); Shortcut(warningDesktop, "MSR", Path.Combine(damagedOld, "MSR-Launcher.exe"));
            ProfileDiscovery warningFound = ProfileRecovery.Discover(warningCache, warningDesktop);
            Check(warningFound.Exists(delegate(ProfileBackup b) { return b.Path.StartsWith(warningCache) && b.Key == keyOld; }), "production discovery retains valid cache beside damaged shortcut profile");
            Check(warningFound.Exists(delegate(ProfileBackup b) { return b.Path == intactRuntime; }) && warningFound.Warnings.Count == 1, "production discovery retains valid paired runtime and warns per damaged file");
            ProfileDiscovery selectedFolder = ProfileRecovery.ProfilesInSelectedFolder(damagedOld);
            Check(selectedFolder.Count == 1 && selectedFolder[0].Path == intactRuntime && selectedFolder.Warnings.Count == 1, "selected old folder retains valid paired profile despite invalid runtime");
            string uncertain = Package("Uncertain fresh installation", false);
            Check(!ProfileRecovery.TryPrepareFresh(uncertain, v, warningCache, warningFound, delegate { }), "discovery warning requires explicit choice even when all readable keys agree");
            Check(!File.Exists(Path.Combine(uncertain, v, "player-profile.json")), "uncertain discovery does not automatically restore or create identity");
            Throws<InvalidDataException>(delegate { MSRLauncher.ReadKey(damagedRuntime); }, "direct invalid-file selection still reports validation error");
            using (ProfileRecoveryForm warningForm = new ProfileRecoveryForm(damagedOld, v, false, warningCache, warningDesktop))
            {
                TextBox warning = warningForm.Controls["DiscoveryWarnings"] as TextBox;
                Check(warning != null && warning.Text.Contains(damagedRuntime), "production form constructor retains readable discovery warning");
                Check(HasButton(warningForm, "Choose old profile...") && HasButton(warningForm, "Choose old MSR folder..."), "production recovery form opens with both manual pickers after damaged discovery");
            }
            Render(new ProfileRecoveryForm(damagedOld, v, false, warningCache, warningDesktop), "discovery-warning.png");
            Check(File.ReadAllText(damagedRuntime) == "damaged profile fixture" && MSRLauncher.ReadKey(intactRuntime) == keyOld, "discovery and form construction never rewrite damaged or valid sources");
            using (FileStream locked = new FileStream(intactRuntime, FileMode.Open, FileAccess.Read, FileShare.None))
            {
                ProfileDiscovery unreadable = ProfileRecovery.Discover(warningCache, warningDesktop);
                Check(unreadable.Count == 1 && unreadable.Warnings.Count == 2, "unreadable shortcut profile does not discard readable cache");
            }
            string emptyWarningCache = Path.Combine(work, "No valid warning cache");
            File.WriteAllText(intactRuntime, "second damaged profile fixture");
            ProfileDiscovery noReadable = ProfileRecovery.Discover(emptyWarningCache, warningDesktop);
            Check(noReadable.Count == 0 && noReadable.Warnings.Count == 2, "zero valid candidates preserves all discovery failures");
            Check(!ProfileRecovery.TryPrepareFresh(uncertain, v, emptyWarningCache, noReadable, delegate { }) && !File.Exists(Path.Combine(uncertain, v, "player-profile.json")), "failed discovery with zero valid candidates never silently creates new profile");
            using (ProfileRecoveryForm emptyForm = new ProfileRecoveryForm(uncertain, v, true, emptyWarningCache, warningDesktop))
                Check(HasButton(emptyForm, "Start a new profile") && HasButton(emptyForm, "Choose old profile...") && HasButton(emptyForm, "Cancel"), "zero-valid discovery failure offers explicit new-profile and manual recovery choices");
            Render(new ProfileRecoveryForm(uncertain, v, true, emptyWarningCache, warningDesktop), "discovery-empty-warning.png");
            File.WriteAllText(Path.Combine(warningCache, "profile-damaged-fixture.json"), "damaged cached profile fixture");
            ProfileDiscovery damagedCache = ProfileRecovery.Discover(warningCache, Path.Combine(work, "No extra shortcuts"));
            Check(damagedCache.Count == 1 && damagedCache.Warnings.Count == 1, "production discovery retains valid cache beside malformed cached profile");
            Directory.CreateDirectory(emptyWarningCache); File.WriteAllText(Path.Combine(emptyWarningCache, "profile-damaged-fixture.json"), "damaged cached profile fixture");
            Throws<InvalidOperationException>(delegate { MSRLauncher.PrepareIdentity(uncertain, v, emptyWarningCache, false); }, "normal preparation cannot bypass unreadable-cache uncertainty");
            Check(!File.Exists(Path.Combine(uncertain, v, "player-profile.json")), "unreadable-cache guard leaves fresh profile absent");
            string beforeOverwrite = Package("Shortcut installer target", false);
            Check(ProfileRecovery.TryPrepareFresh(beforeOverwrite, v, emptyCache, desktopFound, delegate { }), "profile restored before synthetic shortcut replacement");
            typeof(MSRLauncher).GetMethod("CreateShortcuts", BindingFlags.Static | BindingFlags.NonPublic, null, new Type[] { typeof(string), typeof(string) }, null).Invoke(null, new object[] { beforeOverwrite, desktop });
            Check(MSRLauncher.ReadKey(Path.Combine(beforeOverwrite, v, "player-profile.json")) == keyOld, "shortcut replacement keeps recovered old identity");
            string script = File.ReadAllText(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, @"..\package\Create-Desktop-Shortcuts.ps1"));
            Check(script.IndexOf("--prepare-profile") < script.IndexOf("$shell.CreateShortcut"), "PowerShell wrapper prepares before overwriting shortcut");
            string cfgRoot = Package("Normal Prepare backup", false), cfgCache = Path.Combine(work, "Prepare registry");
            MSRLauncher.Prepare(cfgRoot, v, "127.0.0.1:27025", true, cfgCache, false);
            Check(ProfileRecovery.ListBackups(cfgCache).Count == 1, "normal Prepare backs up own profile");
            string cfgPath = Path.Combine(cfgRoot, v, @"game\msr\private_join.cfg"); string cfgBefore = File.ReadAllText(cfgPath);
            Throws<ArgumentException>(delegate { MSRLauncher.Prepare(cfgRoot, v, "bad;quit", true, cfgCache, false); }, "invalid address still rejected");
            Check(File.ReadAllText(cfgPath) == cfgBefore, "bad address leaves join configuration unchanged");
            Check(ProfileRecovery.BackupDirectory.EndsWith(@"Saved Games\MSR\Profiles") && !ProfileRecovery.BackupDirectory.Contains("AppData"), "production registry is outside AppData virtualization");
            Render(new LauncherForm(current, v), "new-launcher.png");
            Render(new ProfileRecoveryForm(current, v, false, backups), "restore-profile.png");
            Render(new ProfileRecoveryForm(conflictRoot, v, true, backups, conflict), "fresh-profile-choice.png");
            File.WriteAllText(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "recovery-results.json"), "{\"status\":\"PASS\",\"assertions\":" + checks + ",\"fixture_root\":\"" + work.Replace("\\", "\\\\") + "\",\"game_or_network_started\":false}");
            Console.WriteLine("PASS " + checks + " assertions; synthetic fixtures only."); return 0;
        }
        catch (Exception error) { Console.WriteLine(error); return 1; }
    }
}
