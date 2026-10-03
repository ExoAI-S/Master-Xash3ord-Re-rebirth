# Daragoth proximity encounters — local preview

Installed in the local **MSR - Daragoth Preview** on October 2, 2026
(verification files use October 3 UTC timestamps). This is not a public-realm
deployment or GitHub release.

## Behavior

- The expanded plains have 30 authored encounter zones with 163 reserve slots.
- Living players entering a zone activate nearby enemies. At most 16 managed
  enemies are active across the zones, with at least 0.2 seconds between births.
- Activation range is 1600 map units; retention range is 2400 units. Birth pads
  must be at least 320 units from players. Untouched, idle enemies can retire
  after players remain away for 30 seconds.
- Ordinary deaths use randomized 90–180 second respawn delays. Locations and
  enemy templates are authored; the system does not place arbitrary enemies at
  any player coordinate or reroll every pack's composition.
- Spawn pads avoid the village/stable reserve. This is not a chase boundary.
  Original Daragoth monsters are not included in the new system's cap.

Use the existing **MSR - Daragoth Preview** desktop shortcut and explore beyond
the village in the expanded plains. The normal MSR install and public realms
were not updated by this operation.

## Registration repair

The first native run rejected all 30 groups. Stock monster-template registration
interns even empty killtarget/perishtarget strings, giving them nonzero handles.
The opt-in encounter validator incorrectly treated those handles as real outputs.
`msr_encounters.inc` now checks the decoded string for nonempty content, including
the controller's fireallperish output. Nonempty outputs remain unsupported.

The corrected server was compiled as x86 Debug, with its matching PDB installed
in both local preview roots. Geometry lumps were preserved; the map changes are
entity placements, including the previously prepared furniture and encounters.

## Native evidence

Evidence is in `Verification/Daragoth-Encounters/2026-10-02/`. The native test
used an isolated client profile, the actual installed server and private FN,
ordinary character commands, and the existing cheat-gated placement command.

| Check | Observed result |
| --- | --- |
| Empty server | 30 controllers, 163 slots, zero refusals and zero births |
| Player far from encounter zones | Zero births |
| Player approaches wilderness zone | Five births in first snapshot, then cap reached at 16 |
| Player leaves; grace expires | All 16 untouched actors retired, zero live |
| Player returns | Fresh births; cumulative 32 births, 16 live, 16 retired |
| Invalid output regression | Nonempty target, killtarget, perishtarget, and fireallperish rejected four test groups; remaining 26 registered |
| FN compatibility | Installed Daragoth CRC and scripts CRC accepted by private FN |

All captured snapshots had zero spawn/descriptor failures and stayed within the
cap. This verifies basic activation, cap, pristine retirement, and reactivation.
After the second visit and client disconnect, 31 of 32 births had retired; one
untouched orc archer was conservatively retained with `Unsupported` reason 3.
The snapshot does not distinguish a shape mismatch from unsupported inventory.
That hold needs follow-up before broader acceptance; cleanup guards were not
weakened to force removal. The empty map was then reloaded for the user's test.
It does **not** establish multiplayer stress performance, combat/XP/loot behavior,
ordinary death respawn timing, or full traversal of all 30 zones. The historical
native acceptance flag remains false.

An earlier synthetic run ended before verification. One earlier client log
records a command-driven exit; the exact cause of the other observed closure is
unconfirmed. The successful run used console-driven commands without a long
queued `wait`, which had blocked later commands in the previous setup.

## Installed artifact identity

| Artifact | SHA-256 |
| --- | --- |
| daragoth.bsp | `67946ff32b0f9ecf1410ca0791c59ded09dfbfd6c34cea6db87be679ff7775b6` |
| ms.dll | `8a09d371260d33aca883c95239b300c5e23d84ef088e79189b35a71a88221cf7` |
| ms.pdb | `07233e43397703a7a001a757e30f47827cbfb3487806648d9decdf6dbe4b0cdc` |

Map CRC is `1139436697`; scripts CRC remains `4199339986`. Client DLL
`7331b73f5920572645912ff223e4de4009aaf2dc4fe2d307ff1ee125acb6b316`
was preserved. Profiles and existing character saves were not replaced.

## Rollback

The sibling `daragoth-development` lab retains verified original files and a
receipt that restores the pre-encounter map, server DLL/PDB, and FN content
manifest in both preview roots. Stop the preview client, server and its private
FN before running from the lab directory:

```powershell
python .\proximity-encounters\install_preview.py rollback --receipt .\backups\proximity-preview-20261003T041013Z\rollback-to-pre-encounters.json
```

The installer refuses mismatched or subsequently modified target files. It never
restores or replaces player profiles or FN character storage.
