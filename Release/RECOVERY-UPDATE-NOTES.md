Download **MSR-Recovery-Debug-Complete-2026-09-13.zip** and extract the entire ZIP. Keep your old game folder until your character appears.

- **Character recovery:** fresh installations reuse one unambiguous identity found in your saved profile backups or previous MSR desktop shortcuts. If needed, open **Recover characters**, choose your own old MSR folder/profile, and restore it before joining your usual realm.
- **Identity backups:** normal launcher use preserves your profile outside the installation under **Saved Games\MSR\Profiles**. Existing identities are not silently overwritten, and manual recovery backs them up first.
- **Chat placement:** chat history and the typing line sit immediately above the active health/mana HUD, including retro mode and resolution changes.

The inventory, equipment slots, glowing Daragoth world map, unified weapon skills, realistic shortswords, Dungeon Master tools and both realm-join helpers remain included. The FN game-server loading flow is unchanged: the server requests character slots using the client's persistent identity and sends their selection information to the client.

FN characters are not bundled in this ZIP. Every player must use their own profile identity. Reinstalling with a new identity can show empty slots even though the original character is still on FN. See **RECOVER-CHARACTERS.md** inside the package.

This is a complete Windows Debug package with matching symbols and source. The optional native MScript prototype remains disabled. The [previous UI release](https://github.com/ExoAI-S/Master-Xash3ord-Re-rebirth/releases/tag/v2026.09.12-ui-debug) remains available for recovery.
