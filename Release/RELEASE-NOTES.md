# MSR PrimeXT with Dungeon Master mode — Debug complete package

This release contains the complete game package from September 12, 2026, including the Enhanced version with Dungeon Master mode and the Stable version for rollback.

## Download and play on Windows 11

Download these **three files** from the release into the **same folder**:

1. `MSR-PrimeXT-DM-Magic-Fix-Debug-Complete-2026-09-12.zip.001`
2. `MSR-PrimeXT-DM-Magic-Fix-Debug-Complete-2026-09-12.zip.002`
3. `Restore-Game-Zip.cmd`

Double-click `Restore-Game-Zip.cmd`. It checks the size and SHA256 of both parts, joins them into the original ZIP, and verifies the completed ZIP. It keeps the downloaded parts and refuses to overwrite a different existing ZIP. It uses Windows' built-in PowerShell commands; no PowerShell script policy change is needed.

Right-click the completed `.zip`, choose **Extract All**, then open `MSR-PrimeXT-DM` and run **`MSR-Launcher.exe`**. Read `START-HERE.md` in the extracted package for launch, host, character, and Dungeon Master instructions. Use the included shortcut creator for desktop shortcuts. Do not run the game from inside the ZIP.

Allow **at least 12 GB free space** for the two downloads, the assembled ZIP, and extracted files together. After successful extraction, the ZIP parts and assembled ZIP can be removed to reclaim space.

The archive is split only because [GitHub limits each release asset to under 2 GiB](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases). Reassembly restores the exact original ZIP; no files were removed. GitHub's automatically generated **Source code** downloads are for developers and do not contain the complete playable package.

## Included

- Enhanced game with Dungeon Master mode and a full Stable rollback version.
- Native launcher, local hosting with private FN character persistence, public realm join launchers, custom-address join, and desktop shortcut creation.
- Game assets and bundled runtime tools from the complete package.
- SDK and engine source, Debug game DLLs with matching symbols and maps, and validation documentation.
- No personal characters, FN databases, host credentials, or Playit credentials.

Realm shortcuts connect to the existing host's published addresses. Those realms are available while the host PC, game servers, FN service, and tunnels are running. Local hosting is available through the launcher.

## Magic-effect corrections and validation

This build sets up sprite models before submitting render entities, corrects optional dynamic-light argument bounds, and fixes script return-value lifetimes that could corrupt vectors used for magic effects and sound positions. It includes the optional `ms_debug_effects` diagnostic cvar, disabled by default.

An isolated Debug client/server test displayed hand-glow sprites and completed three lightning casts with effect and beam activity, mana use, correct traced positions, and a responsive client. Native regression checks cover the original rendering, argument-boundary, and script-lifetime defects. The complete archive passed checks on all **39,040 entries**.

Sound dispatch and positions were verified through diagnostics; physical speaker output was not independently heard. The brief lightning bolt was not independently captured in a screenshot. These checks do not establish that the friend's earlier separate `0xC0000005` crash is resolved. See `DEBUG-VALIDATION.md` and `MAGIC-EFFECTS-FIX.md` inside the package for the detailed test evidence.

## Archive identity

- Original archive size: **3,151,413,773 bytes**.
- Original archive SHA256: `8f62cafa56c06e1efaa907677b6bcb4b52ac53cc6c1b70130fdcd28c4d922b81`.
- Part 001: **1,700,000,000 bytes**.
- Part 002: **1,451,413,773 bytes**.
- `SHA256SUMS.txt` contains checksums for the downloads and original archive.

Upstream license and attribution notices are retained in the package. Different code, tools, and game assets have their own terms; this release does not apply a new blanket license to them.
