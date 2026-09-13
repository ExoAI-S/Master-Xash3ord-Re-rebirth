# Recovery and chat update validation

This update adds launcher identity recovery and lowers the client chat area.
The server, game scripts and FN character-slot loading flow retain the preceding
UI release's tested implementation. Earlier UI/FN evidence remains historical;
the checks below cover this update.

- Frozen launcher: candidate-03, 125 focused assertions passed; the previous
  launcher reproduces a changed identity in a fresh installation.
- Both compiled launchers pass their built-in self-tests. Debug builds use
  /debug:full and /optimize-. Each EXE's CodeView GUID/age matches its PDB.
- Populated offscreen forms were inspected. Tests exercise real synthetic
  filesystem replacements and shortcut COM operations, plus conflict handling,
  invalid data, locks, exact backups, source/target drift and rollback.
- Chat candidate-10: Debug client build, 544 source inputs matched the package,
  and 78 extracted-method layout checks passed for 640x480, 1920x1080 and
  3440x1440, normal/retro HUD, typing open/closed and moved HUD anchors.
- An isolated 1920x1080 game session showed chat history and the actual typing
  callback above the health/mana area. See Docs/images/chat-above-bars.png.
- Game server DLL/PDB and scripts match the preceding UI release. The optional
  native MScript pilot remains disabled.

The launcher tests do not claim physical file-picker interaction, live WMI
process enumeration, or recovery on another person's PC. They exercise the
running-client decision with synthetic records. FN still associates saves with
the client's persistent profile identity; character names are not credentials.

Frozen manifest SHA256 values:

- Launcher: db7b02a69b9547d935e68ae49c0953b9ad62d7e909b87509fccf0711b51eaf5d
- Chat: e1471c17d48cd44f14064fb31dac68f114e4c5bd99e704db915faafaac6e0be9

Runtime hashes are in DEBUG-BUILD.json; all packaged file hashes are in
PACKAGE-MANIFEST.json. Reproducible recovery checks are under
Verification/Profile-Recovery. A fresh copy of only that public suite compiled
both launchers and passed all 125 assertions and symbol checks without additional
files; all generated fixtures stayed outside the release staging folder. FN saves, real profile identities, host passwords
and tunnel credentials are excluded from the distributable game.

Recovery discovery also isolates damaged/unreadable files, keeps valid paired
profiles and backups available, and shows warnings before a fresh installation
chooses an identity. A damaged shortcut source cannot block the manual picker.
