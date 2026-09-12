# Test FN persistence between realms

Both servers use the same FN database and start in Edana. Use the desktop shortcut or Browse-Servers.cmd, then select Favorites. The launcher adds both entries before the game loads its menu. If an older game session still shows an empty list, exit the game and relaunch using this shortcut: a running menu can overwrite a file edited underneath it. Realm One is 127.0.0.1:27025; Realm Two is 127.0.0.1:27035.

1. Join Realm One and select the character you want to test. On this PC, Ragnar is slot 1 and the recovered Zalnar is slot 2.
2. Note an inventory item and your gold. Pick up or store an item to make a recognizable change.
3. Disconnect normally, then join Realm Two from Favorites. Select the same character slot and confirm the item and gold.
4. Make another change, disconnect normally, and return to Realm One to confirm it persisted in both directions.

Console alternative: `connect 127.0.0.1:27025` or `connect 127.0.0.1:27035`. Use the existing game client so it retains your private profile. Do not create a new character to switch realms.

These local Favorites enable testing on the hosting PC. Players in another household can use `schmidt-council.tun.ply.gg:48715` for Realm One and `schmidt-once.tun.ply.gg:63800` for Realm Two. Direct joining does not depend on the global Internet directory.
