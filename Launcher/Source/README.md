# Native MSR launcher

`Build-Launcher.cmd` builds the package's `MSR-Launcher.exe` and its PDB using
the .NET Framework C# compiler supplied with Windows. This is a Debug build.
The launcher uses .NET Framework, WinForms, WMI and the Windows shortcut COM API.
Joining a server and creating shortcuts do not invoke PowerShell.

Supported entry points:

- No arguments: choose Enhanced/Stable and a public or custom server.
- `--realm one` / `--realm two`: join the corresponding shared realm.
- `--address hostname:port --version enhanced|stable`: direct join.
- `--create-shortcuts`: create five native desktop shortcuts.
- `--host-action start|stop|status|play --version enhanced|stable`: host window.
- `--dm`: local Enhanced Dungeon Master controls.
- `--self-test`: isolated fixture validation; never launch the game or a host.

The native host window invokes the bundled Python interpreter and
`Launcher/native_host.py`. DM commands use that helper's `rcon` action and strict
command allowlist. The helper owns process validation, persistence and version
switching rules. Start and Play safely switch versions, preserving FN character
databases with backups. The helper verifies Stable critical files, refuses open
clients or ambiguous process ownership, and keeps both database copies before
transferring saves. It has passed an isolated live Enhanced/Stable round trip.
Stable joining uses original Stable game files, including their known limitations.

Normal joining defaults to a 1280x720 window and keeps the existing graphics
profile. Player identities are generated cryptographically, reused across game
versions and never overwritten. Conflicting identities cause an explicit error.
Existing game windows are left running and a second client launch is refused.

Verified without starting the game: relocated paths containing spaces; new and
existing identities; cross-version identity reuse/conflict rejection; malformed
addresses rejected before writes; windowed client-only arguments; five shortcut
files created and read back in an isolated fixture; helper RCON argument contract,
invalid slots and command chaining refusal. GUI/gameplay checks remain separate.

The distribution audit reproduced PowerShell's RemoteSigned rejection of an
unsigned Internet-marked harmless script using the bundled runtime. No execution
policies or Windows security settings were changed. Native binaries remain
subject to the user's ordinary Windows application controls.
