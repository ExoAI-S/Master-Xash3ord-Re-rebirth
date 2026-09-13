# MSR

Extract the entire ZIP into a writable folder. Open **MSR-Launcher.exe** or
**Play-MSR.cmd**. There is one game, including Dungeon Master support.

Press **P** in game for **Inventory**, **Character** and **World Map**. See
**MENU-GUIDE.md** for armor slots, bag actions and the glowing current-region map.

- **Join server** connects to Realm One, Realm Two, or a custom LAN/Internet address.
- **Play local** starts your own FN character service and two local realms, then joins.
- **Host controls** provides Start, Play, Status and Stop. Closing the game leaves the host running.
- **Dungeon Master** manages your own local realms. Refresh players, enter your player slot,
  grant DM, then press G in game and select Dungeon Master. Public realm hosts grant their own permissions.

Run **Create-Desktop-Shortcuts.cmd** for MSR, Join Realm One, Join Realm Two and
Dungeon Master shortcuts. Recreate them after moving the extracted folder.
The realm CMD helpers also join directly without starting servers.

Realm One: `schmidt-council.tun.ply.gg:48715`

Realm Two: `schmidt-once.tun.ply.gg:63800`

These realms share their host's FN character service; the host and tunnels
must be running. Your local FN has separate saves. The first join generates
a private Portable-Package/player-profile.json: back it up and never share it.
Fresh installs contain no player identity, saves, host passwords or tunnel account.

Close your client before starting a new one. Local hosting uses UDP 27025 and
27035; Internet hosting needs your own forwarding/tunnels. Starting local play
also prepares FN for in-game Create Game; keep the local host running for FN.

**Collect-Diagnostics.cmd** creates a local report after a failure. Review it
before sharing; nothing is uploaded automatically. Debug symbols are included.

Source is in **Source**, engine source in **Engine-Source**, launcher source
in **Launcher/Source**. See **SOURCE-BUILD.md** and **Recovery/README.md**.
