Download **MSR-Unified-Debug-Complete-2026-09-12.zip** below and extract it completely into a writable folder. Open **MSR-Launcher.exe** or **Play-MSR.cmd**. Run **Create-Desktop-Shortcuts.cmd** to create the MSR, realm-join and Dungeon Master shortcuts.

- Press **P** for the new Inventory, Character and World Map tabs, with fantasy menu decoration.
- Drag armor from hands or bags onto compatible equipment slots. Updated servers enforce the equipment requirements.
- View the Daragoth atlas with a glowing current-region marker, zoom, centering and map transitions.
- Weapon skills now have one base level and experience bar. Magic schools and Parry remain separate.
- Realistic regular and rusty shortswords are included. The original player model remains installed.
- Local Create Game sessions can load and save through private FN; the previously disabled local FN request worker now starts correctly.
- Dungeon Master mode and both Internet realm join helpers are retained in one game package.

This ZIP includes the game files, bundled runtime, matching source, editable shortsword artwork, development tests and Debug symbols. It contains no player's private identity, character saves, host passwords or tunnel credentials. GitHub's automatic Source code downloads are developer snapshots; use the named complete ZIP to play.

Both public realms must be online to join them. Your own local FN host has separate saves. Keep your private player-profile.json backed up so your identity remains the same when moving to a fresh extraction.

See **MENU-GUIDE.md**, **START-HERE.md** and **Release/UI-UPDATE-VALIDATION.md** inside the ZIP. Engine checks exercised menu callbacks and synthetic character persistence; physical mouse/keyboard capture and extended gameplay were not exhaustively tested. The optional native MScript prototype remains disabled.

Keep the [previous DM Debug release](https://github.com/ExoAI-S/Master-Xash3ord-Re-rebirth/releases/tag/v2026.09.12-dm-debug) and raw pre-update save backups for recovery. Reverting DLLs alone does not reconstruct the former unequal weapon subskills after a migrated save has been written.
