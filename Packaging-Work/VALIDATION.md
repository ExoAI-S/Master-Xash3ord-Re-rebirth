# Enhanced validation — 2026-09-12

## Stable and save recovery

- Restored 7,001 files from the original handoff and recorded their SHA-256
  hashes. Rechecked all 6,527 original game assets after the live switch tests:
  every file matched.
- Switched Enhanced → Stable → Enhanced with both realms responding.
  Stable does not register the new director commands.
- FN transfer tests pass for both-way transfer, WAL-backed databases,
  preservation of both prior databases, and rejection of schema mismatch
  without overwriting the destination.

## Encounter director

- Both Enhanced realms respond on ports 27025 and 27035 without passwords.
- Live orc and rat spawns, overlap refusal and cleanup passed. Evidence:
  `director-live-test.json`.
- Captain Brenn's checked position is `(1740,2520,-128)` in Edana.
- The ungranted QA client cannot enable events. In-game status and denied
  actions return readable feedback. Random encounters remain off by default.
- Full campaign-map testing and long-running encounter balance testing remain
  outstanding. This is an initial encounter director, not a full map editor.

## Client crash found and fixed

Three old test-client dumps reported `xash.dll!_chkstk` inside the crash
handler. The stack scan resolves about 28,649 return addresses to
`CHudSayText::EnsureTextFitsInOneLineAndWrapIfHaveTo` in one dump. The engine
DLL and its local symbol copy have matching SHA-256 hashes.

The chat implementation captured `ScreenWidth()-40` at DLL initialization,
before video dimensions were available. A Dungeon Master status/permission
message triggered recursive wrapping with that invalid width. This also
made the crash look like a menu or engine problem.

The Enhanced client now calculates chat bounds from current video dimensions,
defers wrapping before video initialization, guarantees progress when splitting
a word, preserves the remainder before scrolling, and bounds/terminates text
copies. Release builds retain function symbols and link maps beside the DLLs.

`test_saytext_wrap.py` compiles the actual production wrapping and scrolling
functions against a deterministic font. Checks pass for startup then resize,
the triggering status message, word wrapping, long words, a full chat buffer,
tiny widths, invalid row indexes and an unterminated color specifier.

The patched client stayed running through the formerly crashing sequence.
At 1280×720, visual checks passed for the Dungeon Master panel, status,
permission denial, host-granted enable and pause, cleanup feedback, Back,
and main-menu Cancel. RCON independently confirmed ON then OFF. The temporary
QA grant was revoked; both realms were left with random events off and no
active encounter. Actual creature spawning/cleanup had passed the earlier
server tests; this menu pass used an empty encounter. This turn did not repeat
fullscreen or native monitor-resolution testing. The PowerShell host panel
was launched but was not visually exercised by the automation tool.

## Artwork

The runtime logs confirm Xash external material replacements load for
`human/reference.mdl` body, `npc/guard1.mdl` armor and `monsters/Orc.mdl` face.
The legacy male1 body also has a replacement. Original model geometry and
animations are unchanged. Texture hashes and target paths are recorded in
`Portable-Package/game/msr/materials/msr-hd-manifest.json`.

PrimeXT shaders and proposed material data are staged, but its advanced
renderer callback is not yet integrated into the MSR client. Those staged
resources alone do not enable PBR, SSAO, shadow maps or PhysX.
