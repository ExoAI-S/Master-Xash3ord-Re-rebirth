# Native stablemaster and horse lifecycle audit

The Win32 Debug server exposes `ms_stable_audit <player slot> <phase> [other player slot]` with `sv_cheats 1`. It uses real horse entities, actual standing-hull traces, production stablemaster requests and player lifecycle methods. The command is excluded when `NDEBUG` is defined. Run it in a loopback development realm with synthetic FN characters; `death` and `spawn` act on the selected character in that realm.

The October 1 audit used an additional realm on UDP 27249 and its own cloned synthetic FN database on TCP 5842. It did not modify the normal game, real player profiles, public realms or GitHub releases. The native fixture kept the previous meadow BSP, which has the same stable floor, stablemaster and horse placements as the subsequently accepted batched meadow.

## Baseline and repairs

Two native baseline assertions failed before repairs: forced dismount left mount-imposed attack/jump/duck restrictions in the player's status, and `UTIL_Remove` left both mount links and the raised camera until a subsequent player update. The existing lifecycle helper restored the original status after its checks, so it had not caught the first issue.

The horse now records natural restrictions when the player's effects are rebuilt and restores those restrictions on release. A spell that expires while riding stays expired; a spell that starts while riding remains effective after dismount. Cleanup runs before `UTIL_Remove` marks a horse for deletion, and the existing virtual `OnDestroy` hook handles direct engine removal. Destruction does not relink the freed horse to its home. A horse marked for removal cannot be mounted again. No base-class virtual layout or network protocol changed.

## Reproduction sequence

Load two synthetic characters, enable mounts before loading the map and place both next to the stablemaster. For the private Daragoth preview, slot 1 stands at `-499.9527 5164 3158`, and slot 2 at `-443.9527 5116 3158`; `ms_mount_place` checks these destinations using the actual server hull API.

1. Run `restore`, `remove`, `destroy`, `effects` and `pads` for slot 1. The checks cover immediate camera/control/link restoration, direct engine destruction, changing real MScript effect variables, all blocked pads and skipping blocked/occupied pads. The effect fixture restores its original variables.
2. Run `requests` with other slot 2 and the existing `ms_stable_test 1 2`. Repeated mounted and unmounted requests reuse the same loan; another player is denied; moving an unmounted loan does not create a duplicate.
3. Move both players to original Daragoth, unload `daragoth_plains` with the real region command, reload it, then return. Compare customer loan entity IDs before and after; repeat the request checks.
4. Run `ride`, disable mounts and wait for a real server frame. Verify no rider link, no customer loan and the normal camera. Re-enable mounts and return beside the NPC.
5. Run `ride` then `spawn`; return, run `ride` then `death`, followed by `respawn`. Verify the selected loan disappears and the player's mount flag/link clears.
6. Assign both players horses, mount slot 2 and let that client disconnect and quit normally. Wait for both the client exit and server disconnect confirmation before checking that only slot 1's loan remains. A fixed delay is insufficient when the background client runs at a lower frame rate.
7. Mount slot 1 and execute a real `changelevel daragoth`. Verify cleanup and a fresh map containing only the shared, unmounted horse.

`state` reports the selected player's current camera, status and customer-loan count. `clear` removes that player's loans through the same spawn cleanup path. `ride` performs a validated test placement beside the existing loan and mounts it. These are audit helpers, not gameplay commands.

The sanitized report is `Reports/daragoth-mount-lifecycle-20261001.json`. It records baseline failures, the tested server/map hashes, native responses and the accepted results. Model animation, ordinary airborne mount/dismount rules, road/seam geometry and the prior normal-Use ownership cases remain covered by the existing mount policy and stablemaster preview tests. Loans are session state and are not saved into FN; this audit does not implement persistent mount ownership or horse-sized collision.

After acceptance, the same tested Debug DLL and its matching PDB were installed into both private previews with the batched meadow. Nine additional native smoke checks passed there: immediate cleanup through both removal paths, ordinary ownership/airborne rules, normal Use to request and dismount, camera and control restoration, normal quit cleanup and no snapshot overflow. The native server observation after Use was `mount=0 loans=1 status=0 physics=0 view=28.0`; quit then left only the shared horse. Staging preserved both player-profile files, both client DLLs and the accepted meadow BSP. The previous server DLL/PDB and a consistent synthetic FN snapshot were retained for rollback.
