# Recover your FN characters after reinstalling

FN stores the characters on the host. Your own `player-profile.json` tells the
game server which character slots belong to you. A new identity opens a
different set of slots even when the original characters are still on FN.

## Install and reconnect

Extract the complete ZIP into a writable folder. Keep the previous installation
until your character appears. Run **Create-Desktop-Shortcuts.cmd**, then open
**MSR** and join the same realm you used before.

A fresh installation checks your saved profile backups and previous MSR desktop
shortcuts. When they identify one consistent profile, it reuses that identity.
Conflicting profiles or unreadable discovered files open the recovery dialog
with an explicit choice. Read the warning, then select your valid old profile. An existing profile is never silently
replaced.

If your character is missing, use **Recover characters** in the launcher:

1. Close the game normally.
2. Choose **Choose old MSR folder...** and select your previous installation,
   or **Choose old profile...** and select your own `player-profile.json`.
3. Select the intended profile and click **Restore selected profile**.
4. Join the same realm again and choose your character slot.

The usual old file is `Portable-Package/player-profile.json` inside the previous
game folder. Restore your own profile; someone else's file opens their slots.
The launcher preserves the current identity before replacing it. Restoring an
identity does not delete or overwrite either identity's characters on FN.

## Backups that survive an extracted-folder replacement

Normal launcher use backs up your player identity beneath:

`%USERPROFILE%\Saved Games\MSR\Profiles`

Keep that folder private. It contains the identities needed to access characters
and is not part of the shareable game ZIP. FN hosts also retain character
revisions and make hourly database snapshots while running. A friend's profile
file lives on their own computer; the host's database backup does not include it.

**Play local** uses your local host's FN database. To see a character from a
shared Internet realm, join that realm. Moving a local host's database is a
separate operation from restoring a player identity.

If the old profile and its backups are all gone, contact your FN host with your
character name. An update cannot infer a lost private identity from a name.
