# Nearby wilderness encounters

This successor prepares thirty wilderness encounter zones on the accepted
furnished meadow. It uses existing orcs, trolls, goblins, skeletons, wolves,
spiders, wild boars and a black bear. Original Daragoth actors remain in the
preserved entity prefix. Town, stable, house entrances, bridge approaches and
the ruins landmark have conservative reserves around the new starting pads.
Those reserves place spawns; they do not prevent pursuit into them.

The two busier areas have twenty-four templates each: sixteen warriors and
eight archers on the eastern ridge, and twenty-four goblins in the far eastern
field. Each permits sixteen live managed actors, subject to the shared budget.
The other twenty-eight packs contain one to eight templates each. The complete
pool has 163 templates, rather than 163 simultaneous enemies.

The initial server policy permits sixteen new managed actors across all players
and all new controllers, including births in progress. A positive shared
0.2-second birth interval spreads admissions over time. Each controller also
has a local limit. Nearby living players activate fixed pads inside 1,600 units;
2,400-unit retention and a thirty-second idle grace avoid boundary flicker.
Pre-birth checks must exclude pads within 320 units of a player and pads occupied
by players, mounts or other solid actors. Every real player contributes to the
spatial set. These are initial settings awaiting actual engine measurements.

The first policy fills available slots in rotation. A real death starts the
existing randomized 90–180-second respawn delay. It does not implement a fixed
number of waves, a barrier requiring a whole pack to die, a special interwave
timer, or a two-group limit. The original layout proposal's wave fields remain
an unimplemented design reference.

Distant pristine ordinary actors can retire without death, XP, loot or kill
events. Actors with damage or pending reward credit remain through their normal
lifetime, even if healed. Finite-life actors and special or uncertain states
are also protected. Friendly movement references require separate diagnostics
from verified fighting. Protected actors can occupy the entire budget and delay
later encounters; the first version does not erase their progress to create
capacity. Wolves following an alpha are a specific near/far verification case.

`build_proximity_encounters.py` requires the pinned furnishing acceptance,
actual pad audit and agreed mapper API before preparing a candidate. It appends
thirty opted-in controllers and 163 fixed templates after the 1,138 preserved
records. Controllers reuse the original invisible nonsolid `*24` cube with its
compiled center translated into the plains. World geometry, collision, lighting,
visibility, water, brush doors and the existing furnishings retain their bytes.
Templates use unchanged packed scripts, unlimited lives, deterministic chance,
no party HP gate or region player-count gate, and `set_no_roam`. The last setting
suppresses idle wandering and does not leash pursuit.

Static pad checks must resolve the actual script bounds, including the mini
spider's 16-by-20 box and the troll's 100-by-125 box. They sample supported floor
contacts, the body volume, the production-selected trace hull, translated water
volumes, reserve boundaries and actor separation. Sampled custom boxes and fixed
engine hulls are distinct evidence. Static clearance cannot account for a player
or horse occupying a pad later; the changed core must recheck births.

The fixed-eight candidate and its old native preparation remain held reference
artifacts. This successor needs the new optional core, separate DLL/PDB/source
pins, two-client near/far and dense-budget tests, ordinary damage/death/respawn,
nondeath retirement, region replay and damage-credit starvation tests. Resource,
simulation, CPU and network observations must report actual measured limits.
Unchanged geometry evidence and accepted furnishing views do not substitute for
changed-core compatibility checks. No native acceptance, runtime installation,
particular frame rate or universal crash prevention is claimed by this source.

The prepared candidate is
`67946ff32b0f9ecf1410ca0791c59ded09dfbfd6c34cea6db87be679ff7775b6`
(whole-file CRC32 1139436697). Independent builder/output review passes with
receipt `165f102135a8ab465a68c0e4fc50dce472b9f558ece62f871c7464320f1f1b57`.
It separately replays serialized float32 pad coordinates. The reviewer authored
the original placement audit; this review is independent of the root builder,
not a second independently authored placement design. The compact checkpoint is
`Development-Tests/Reports/daragoth-proximity-candidate-20261002.json`.
Native acceptance and runtime installation remain false.
