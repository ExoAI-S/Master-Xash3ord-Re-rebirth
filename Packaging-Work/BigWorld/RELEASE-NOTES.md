## MSR Five-Region Big World

Edana, Thornlands, Edana sewers, Northern Thornlands, and Helena now form one connected world with short fades at region crossings. The update also adds world-state storage to the FN service, exact logout position restoration, and timed boss respawns. This is a Debug build.

**New installation:** Download `MSR-Recovery-Debug-BigWorld5-2026-09-27.zip` (the complete game). Extract the entire ZIP to a writable folder. In the extracted `MSR` folder, run `Install-BigWorld.cmd` once, then launch the game with `MSR-Launcher.exe` or `Play-MSR.cmd`. If you host realms, start them after installation. Every player joining a Big World host needs the same update.

**Existing September 24 installation:** Download `MSR-BigWorld-20260927-1032.zip`. Close the game and stop hosted realms. Extract the package folder inside your existing `MSR` folder and run its `Install-BigWorld.cmd`. The installer checks the base game files before making changes. If you have an older Big World test package installed, uninstall that package first.

The installer preserves local character profiles and FN saves and creates a rollback backup next to the game folder. `Uninstall-BigWorld.cmd` restores the prior files. Keep your old game folder or a separate save backup until you verify your characters.

The full archive contains no personal character profile or FN database. The September 24 release remains available as a downgrade base. The updated source and map build tools are in this repository under `Full-Source`, `Portable-Package/FN`, and `Packaging-Work/BigWorld`.

Validation: Debug DLL build succeeded; the map report found zero hull, extent, or PVS mismatches; FN tests passed (21 passed, one skipped); and a scratch install/uninstall restored baseline files byte-for-byte. The full ZIP passed archive integrity and package base-hash checks. In-game traversal of every region was not repeated for this release.
