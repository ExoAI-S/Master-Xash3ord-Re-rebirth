# MSR PrimeXT with Dungeon Master mode

Extract the **entire ZIP** into a writable folder on a Windows PC, such as
`Documents\Games`. Open the extracted folder before running a launcher.
The package includes both runnable game versions, the required runtimes and
assets, and the project source. You do not need to compile it to play.

For a game on your own PC, double-click **Play-Enhanced.cmd**. For the shared
Internet realms, use **Play-Realm-One.cmd** or **Play-Realm-Two.cmd**. You can
also open **MSR-Launcher.exe** directly to choose. These entry points use a
native Windows launcher and the bundled Python runtime; playing does not
require executing unsigned PowerShell scripts.

This edition includes Debug builds of the Enhanced game client and server,
with matching PDB symbols for investigating crashes. The engine is the existing
runtime with its matching symbols. Stable retains its original game binaries.

## Join the shared Internet realms

Double-click **Play-Realm-One.cmd** or **Play-Realm-Two.cmd**. These open the
Enhanced client and connect directly; they do not start servers on your PC.
Select a character slot and create a character on your first visit.

| Launcher | Public address |
|---|---|
| Play-Realm-One.cmd | schmidt-council.tun.ply.gg:48715 |
| Play-Realm-Two.cmd | schmidt-once.tun.ply.gg:63800 |

Both realms are password-free and share the host's FN character service, so
the same character can move between them. Close the game before opening the
other realm launcher. The host PC and its Internet tunnels must be running.

Your first launch creates a private `Portable-Package/player-profile.json`.
Keep a backup of that file: it identifies your characters on the host's FN.
Do not send your generated profile to another player. The distributed ZIP
starts with no player's identity or character saves.

For a LAN address or a different server, use `Portable-Package/Join-Server.cmd`.
Joining the shared realms does not require you to configure router forwarding
or create a tunnel account.

## Desktop shortcuts

Run **Create-Desktop-Shortcuts.cmd** once after extraction. It creates:

- **MSR - Join Realm One** and **MSR - Join Realm Two** for the shared Internet realms.
- **MSR - Enhanced** and **MSR - Stable Base** for hosting and playing on your own PC.
- **MSR - Dungeon Master** for administering your own Enhanced realms.

The shortcuts point to the location where you extracted the game. Run the
creator again if you move that folder.

## Dungeon Master on the shared realms

Ask the realm host to grant your player slot Dungeon Master control. Then
press **G** in game and choose **Dungeon Master**. The package's host control
window manages servers on your own PC; it cannot grant permission on somebody
else's public realms.

The menu can show status, summon Orc raiders or giant rats, enable or pause
random encounters, and clear the current director encounter. In Edana, move
near the town entrance courtyard before summoning. Only one director encounter
can run at a time. Random encounters start off; when enabled their default
interval is about 10–15 minutes. Grants end on disconnect or map change.

## Host your own local game and use DM

1. Double-click **Play-Enhanced.cmd**. It starts a new local FN service and two
   local realms, then opens the client on the first realm.
2. Create or select a character.
3. Open **Dungeon-Master.cmd**, select your local realm, and click **Refresh players**.
4. Find your name and the number in the `#` column. Enter that player slot and
   click **Grant Dungeon Master**.
5. Return to the game, press **G**, and choose **Dungeon Master**.

The local launcher waits for FN and both realms to finish loading before it
opens the client. It also prepares the FN settings used by the in-game
**Create Game** option. Start **Play-Enhanced.cmd** first if you want that
option to use your local FN saves. Opening `game/xash3d.exe` directly creates
or loads your player identity, but does not start the FN service.

Keep the local host running while you use Create Game with FN. A fresh direct
Create Game session without the local host setup uses the game's separate
local character storage. Existing local character files are not automatically
imported into FN. The LAN setting no longer disables private FN in Enhanced.

Your local FN has its own character storage. Characters from the shared public
realms stay on their host and are not downloaded into your local FN database.
Other players on your LAN can connect to your PC's LAN address using UDP ports
27025 and 27035. Hosting over the Internet requires your own forwarding or UDP
tunnels. This ZIP includes no access to the original host's tunnel account.

Use `Portable-Package/Status-Host.cmd` to check the Enhanced host and
`Portable-Package/Stop-Host.cmd` to save and stop it. The Stable equivalents are
inside `Stable-Base`. Closing the game window leaves the local host running.

## Stable rollback

Close the game, then run **Play-Stable.cmd** to switch your local host to the
preserved Stable game. **Play-Enhanced.cmd** switches back. Switching stops the
current local realms, backs up their saves, copies the FN character state, and
starts the selected version. Players on your local realms are disconnected
during this process. Do not run both versions' hosts at the same time.

| Version | Folder | Contents |
|---|---|---|
| Enhanced | Portable-Package | HD textures on existing player, guard and Orc models; Captain Brenn at the Edana entrance; DM mode and optional encounters; chat crash fix. |
| Stable | Stable-Base | Preserved base game and original guard encounter, without Enhanced HD replacements, DM director or chat changes. |

The base game assets are checked against their original hashes before a Stable
launch. Packaging launchers and private configuration are separate from those
preserved assets. New meshes, animations and the full advanced PrimeXT renderer
are still future work.

`Version-Backups` is created as you switch versions and holds your save backups.
`Packaging-Work/verify_stable_base.py` and its manifest support base verification.
`Full-Source` contains the project source; the two runtime folders contain the
playable game assets.

## If startup fails or the game crashes

After the failure, run **Collect-Diagnostics.cmd**. It writes a ZIP inside
`Diagnostics` with recent game logs, binary versions/hashes, and Windows crash
events. Review that report and send it with the steps that caused the failure.
The collector does not upload anything or copy player profiles, saves, or
memory dump contents. It lists available crash dumps so one can be requested
separately if the event report is insufficient.

The reported `0xC0000005` access violation has not yet been reproduced in this
edition. The local Create Game reconnect loop was reproduced and traced to a
missing FN player identity; that startup path has been corrected in source.
See `DEBUG-VALIDATION.md` for the checks completed and their limits.
