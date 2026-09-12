# Master Sword — Steam Independent

This personal build uses the Xash3D FWGS engine and freshly compiled Master Sword: Rebirth game DLLs. It starts without Steam. It includes your supplied game content and a separate FN service hosted on your PC.

## Play on this PC

Extract the entire ZIP into a writable folder, then run **Create-Shortcuts.cmd** to create desktop shortcuts for that location. To join the original host, use **Master Sword - Join a Server** and see **PLAY-WITH-FRIENDS.txt** for LAN addresses and Internet setup.

To run your own realms, double-click **Master Sword - Steam Independent**, or **Browse-Servers.cmd** here. The launcher starts FN and both dedicated realms, adds both realms to Favorites before starting the client, and opens the Internet server browser. Select **Favorites**, then choose a realm. **Play-Local.cmd** still joins Realm One directly. A player profile is created on first launch. Close an existing game window before launching again. Inventory opens in the compact, alphabetical layout by default.

The first run can show a Windows Firewall prompt. You handle this prompt yourself. Cancel is sufficient for play on this same PC; network hosting requires the appropriate access on your own network.

- **Start-Host.cmd** runs both public realms without opening the game.
- **Status-Host.cmd** checks FN, both ports, both maps, and password state.
- **Stop-Host.cmd** stops both realms gracefully, backs up characters, and stops FN.
- **Enable-WAN-Firewall.cmd** adds one Windows Firewall rule for both UDP ports when run as Administrator.
- **Backup-FN.cmd** creates a database backup while FN is running.
- **Show-Profile.cmd** shows your private FN account number for importing characters.
- **Test-FN.cmd** runs isolated backend tests.

Realm One uses UDP **27025** and Realm Two uses UDP **27035**. Both start in Edana, bind to all network interfaces, set `public 1`, and require no game password. FN listens only on **127.0.0.1:5710** and is shared by both realms. Strong, generated RCON passwords remain in `host-settings.json`. You can edit each realm's `hostname`, `map`, or `maxplayers` there while the host is stopped.

On the hosting PC, open Multiplayer / Internet Games and choose **Favorites** to find both realms. Close and reopen the browser to reload its favorites file. See **TEST-PERSISTENCE.md** to test the same character on both servers. The global Internet directory is separate and its registration is still pending.

## Play with friends

Give each player a fresh extracted copy of the package. They run **Join-Server.cmd** and choose Realm One or Realm Two; there is no password prompt. The original host's public addresses are **schmidt-council.tun.ply.gg:48715** and **schmidt-once.tun.ply.gg:63800**. The launcher creates a different player profile for each fresh installation.

The original host uses two free Playit UDP tunnels because the ISP uses carrier-grade NAT. The private Playit agent maps the public addresses above to local UDP **27025** and **27035**. A different person hosting their own realms must configure their own router or tunnel account. Do not expose FN port 5710.

Use this private-profile system with trusted players and hosts. It does not use Steam authentication. A profile key identifies the same player across your compatible private hosts; it is sent to the game host. It is not a public account/login service. Keep `player-profile.json` private and backed up, and do not let two people use the same profile. The game server rejects simultaneous connections with the same profile.

## Characters and backups

Private FN starts with its own database. Official FN characters are not downloaded. Your supplied local `.char` files remain under `game/msr/save/` in your personal installation; save files and the FN database are excluded from the distributable ZIP.

Back up **player-profile.json**, **FN/data/**, and **FN/backups/**. If you lose the profile, a new profile will have a different FN account number. If you move this personal installation to another PC, keep the existing profile and database together. For a different player, use a fresh ZIP extraction instead.

To import a supplied local character, stop the host, run **Show-Profile.cmd**, and use the displayed account number:

```text
FN-Admin.cmd import "game\msr\save\YOUR_FILE.char" --steamid YOUR_PRIVATE_FN_ACCOUNT_NUMBER --slot 0
```

The import only writes into an empty slot and makes a backup first. Slots are 0, 1, and 2. `FN-Admin.cmd --help` describes export, history, restore, and account flags. The `steamid` option keeps the FN protocol's original field name; this build uses private account numbers.

## Build status

The client and server compiled successfully, and dependency inspection confirms neither DLL imports Steam. The client reached its main menu with no Steam API DLL in the installation. The dedicated server loaded Edana and successfully validated FN, scripts, and map checksums. Thirteen isolated FN tests and the native player-ID tests passed.

The rebuilt client has connected and reconnected to the independent server, loaded the saved private-FN character, and repeatedly saved it. The player hands and held shortsword render, and the user visually confirmed bags and sword sheaths on the HUD character after the Xash attachment compatibility fix. Armor uses that same working attachment path. Both password-free realms answer locally and through their Playit public UDP addresses. XP ownership now retains Xash's full Internet-player ID instead of truncating it and discarding awards at monster death. A separate-PC play session and all-map gameplay coverage remain pending. This is an experimental Xash3D port.

See **VALIDATION.md**, **PROTOCOL.md**, and **source/BUILD.md** for evidence, protocol details, exact source versions, and how to rebuild. The original Steam installation and original ZIP were not modified.

## PrimeXT graphics continuation

All local and Internet launchers now load `game/msr/masterpiece.cfg`. On the
current Xash renderer this enables the supported high-quality texture,
anti-aliasing, lighting, sprite, high-model, and reflection settings. The
package also contains PrimeXT's GLSL/material runtime, generated material
metadata for the shipped models, and the first upgraded shortsword texture
set. The advanced PrimeXT renderer callback is still being merged, so HDR,
PBR, shadow maps, SSAO, bloom, and the new external model maps are staged but
not yet active in normal gameplay.
