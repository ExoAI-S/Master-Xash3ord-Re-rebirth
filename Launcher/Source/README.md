# Native MSR launcher

`Build-Launcher.cmd` builds `MSR-Launcher.exe` and its matching PDB with the
Windows .NET Framework C# compiler: `/debug:full /optimize-`. The launcher uses
WinForms, WMI and Windows shortcut COM. Joining and creating shortcuts use no
PowerShell; local host operations use bundled Python and `Launcher/native_host.py`.

Normal launch has one game and one server selector. It offers Join server, Play
local, Host controls, Dungeon Master and Desktop shortcuts. The current runtime
remains at `Portable-Package/game`; this consolidation does not relocate live
services. An optional previous build at `Stable-Base` is accessed from Recovery.

Entry points:

- No arguments / `Play-MSR.cmd`: unified MSR launcher.
- `--realm one` / `--realm two`: join a shared realm.
- `--address hostname:port`: join a custom server.
- `--create-shortcuts`: MSR plus Realm One, Realm Two and Dungeon Master.
- `--host-action start|stop|status|play`: local host controls for the current game.
- `--dm`: local Dungeon Master controls.
- `--self-test`: isolated fixture checks and an offscreen launcher preview.
- `--validate-only` with ordinary launch arguments: parse and validate only;
  exit 0 for accepted options, 2 for invalid options. No UI, file writes, network,
  client launch or host action occurs in this mode.

For recovery and backward compatibility, `--version enhanced|stable` remains
accepted. Enhanced maps to the current runtime and Stable to the optional prior
runtime. These implementation names are absent from normal UI and shortcuts.
The host helper permits a package with only the current runtime. If a recovery
directory exists, it must be complete; it is not silently ignored if corrupt.

Recovery switching preserves identity validation, process ownership checks,
ordered locks, original-asset validation and FN save backups. A stale active
record referencing an absent build is refused, preserving saved data. No host
switch was performed to install or validate this launcher.

The shortcut creator backs up and removes only old edition links targeting this
installation. Unrelated or retargeted links are left untouched. Existing edition
CLI options remain compatible even though the root Play-Enhanced/Play-Stable
helpers have been replaced by Play-MSR and explicit Recovery helpers.

Self-tests validate identity creation/reuse/conflicts, address rejection before
writes, client-only arguments, the four portable shortcuts, the single selector,
single-runtime preparation, and Dungeon Master command restrictions. Host helper
tests use inert temporary fixtures and fake process APIs; no live service action
is needed. Actual gameplay validation is separate from these launcher checks.