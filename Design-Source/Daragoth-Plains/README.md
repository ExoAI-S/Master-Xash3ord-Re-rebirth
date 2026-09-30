# Expanded Daragoth Plains prototype

This is a new editable map, `daragoth_plains`, with original generated geometry
and textures. It preserves the existing Daragoth BSP, live realm map rotations,
and public travel links. The first milestone is a broad place to test walking,
riding, dismounting, collision, and multiplayer replication.

The riding area is 24,000 by 20,000 game units, about 7.6 times the bounding
area of the old Daragoth map. It has low rolling fields, a south stable and
outpost, a broad northbound road, a shallow river crossed by a timber bridge,
stone ruins in the northeast, and a beacon west of the road. Terrain is built
from real collision brushes; the visual mesh is not an unsupported shell.

## Generate and compile

Python's standard library is sufficient for generation:

```powershell
python .\build_daragoth_plains.py
python .\compile_daragoth_plains.py --tools 'C:\path\to\PrimeXT\devkit'
python .\build_script_library.py --base 'C:\path\to\the\original\msr\scripts.pak'
```

PrimeXT tools required: `pxcsg.exe`, `pxbsp.exe`, `pxvis.exe`, `pxrad.exe`.
The compiler script embeds the procedural WAD textures, seals and clips the
world, uses fast visibility for the prototype, and bakes direct outdoor light.
The optional `--spacing` generator argument accepts 384 to 1536 units; the
default 768 keeps this broad map inexpensive while preserving smooth slopes.

Source and outputs are in `generated/msr/maps/`; the original texture WAD is
`generated/msr/daragoth_plains.wad`. The JSON reports preserve compile output,
geometry counts, source slope checks, and compiled hull/spawn checks. Compiler
temporary files are ignored. No files are installed into the live game by these
scripts.

The script-library builder adds the two original scripts under `Scripts/` to a
copy of the existing game library at `generated/msr/scripts.pak`. It verifies
every preexisting script remains byte-identical and records both library hashes.
Install this output alongside the map in the isolated runtime; ordinary MSR
reads this custom library rather than loose `.script` files. The original
`global.script` still supplies the normal character creation defaults. Its rusty
shortsword identifier is `swords_rsword`, without an `items/` prefix.
The generated `liblist.gam` is only a compiler workspace marker; retain the
runtime's full game `liblist.gam` when copying the BSP, config, and script library.

## Prototype placement

The horse entity is `ms_horse`, at `-1700 -7900 432`, yaw 0, with model
`models/mounts/plains_horse.mdl`. The timber floor spans x -2340 to -1060,
y -8220 to -7580 and its top is z 432. The canopy is z 768, leaving 336 units
of clear height. The stable is open on all four sides; the hitching rail is
behind the horse at y -8400. The first spawn is at `-1700 -7788 480`, yaw 270,
112 units north of the horse, facing it. This makes the horse reachable without
a long walk while keeping the spawn off its center. An independent spectator
spawn is at `-1000 -7100 544`, away from the stable and future gate triggers.

The map also has four safe arrival spawns for each of these retained travel
names: `daragoth01`, `deralia`, `from_nash`, and `mines`. These are reserved for
later original-gate integration; no travel brush or neighbor reroute has been
enabled yet. Add named `msarea_transition` brushes only after their destination
maps and reciprocal `desttrans` names are verified. Route Helena through the
installed BigWorld region using its existing arrival name rather than replacing
the published Edana BSP.

The generated `.cfg` uses the legacy MScript system (`as_enabled 0`), turns on
`ms_mounts`, and turns off dynamic combat events
for a controlled test. A dedicated isolated runtime must load the current MSR
Debug DLLs, matching horse model, and large-coordinate mode (`bigworld.enable`
or `-bigworld`). Execute the map config when launching the prototype. Public FN
use additionally requires registering the final BSP CRC; every recompile may
change that CRC. Start with isolated saves while testing.

## Current limits

This is a playable development layout with a first terrain and foliage art
pass. It is not a finished quest region or an MMORPG backend. Further foliage
variation, terrain material blending, interiors, road dressing, quest NPCs,
spawn balancing, and travel links are subsequent passes. Basic map title, clear weather metadata,
an explicit ordinary `game_master`, and three generic arrivals are present.
Fast visibility is intentionally broad
and needs profiling and a full visibility pass before a public update.

The opt-in mount prototype provides walking and galloping, exclusive rider
ownership, a seated human pose, and checked dismount placement. It currently
uses the standing player's collision hull; a full horse footprint is not yet
implemented. Horse ownership is transient and is not saved to FN. Character
saves in the development preview use an isolated FN instance and independent
test profiles. Mounts do not yet have purchase, inventory, progression, or
combat systems. The original live game and published maps remain the baseline.

## Original terrain and foliage pass

The field uses one seamless grass material with small blades and broad color
variation. The dirt road follows continuous, gently varying terrain columns;
material assignment no longer switches by unrelated cell/triangle centroids.
The original procedural WAD textures are now 256 by 256 pixels. Timber grain,
stone block joints, a thatch canopy surface, and small roof fascia improve the
initial outpost art without changing its floor or horse placement.

The map uses the original native models under `models/plains/`: 50 oaks,
35 birches, 19 pines, 125 bushes, 65 rock groups and 165 grass clumps. The total
is 459 scenery entities in 10 irregular copses and surrounding ground cover;
the map contains 490 entities. Primitive conical trees and pyramidal boulders
have been removed. Scenery positions use the actual triangulated terrain
surface. Model entities are non-solid, idle sequence 0 and scale 1. Foliage uses
framerate 1 for the original wind idle; the existing client interpolates its
sequence frames without server entity Think calls. Rock groups remain static.
Trees have
narrow invisible collision trunks, never a crown-sized obstacle.

Tree centers remain at least 1,050 units from the road center; ground-cover
centers remain 620 units clear. Spawn positions retain a 240-unit exclusion
plus each prop's radius, and stable/ruin precincts have additional exclusions.
The compiled report checks three standing-player riding lines across the road,
bridge ramps and bridge deck, plus 128-unit circles around all arrival points.
The source report records each placement and its radius for later profiling.
Every model's base uses barycentric interpolation of the emitted terrain;
compiled hull-0 vertical tests verify its surface within two units. Grass and
bush bases are embedded one unit; tree and rock bases are embedded three units.
Model radii include diagonal foliage extents from the final model manifest.

The tool wrapper defaults to one thread for all four compilers. A parallel CSG
trial produced varying clip planes and a failed collision probe at the northern
edge. The final single-thread build is checked twice for identical BSP SHA256;
`daragoth_plains-repeat-build-report.json` records that evidence. The wrapper
also temporarily hides the custom MSR script library from the compiler's Quake
PAK auto-mounter and restores it in a `finally` block.

`generated/msr/daragoth_plains-texture-preview.png` shows the original material
contact sheet. The prior playable BSP, source, WAD and report are preserved in
`generated/art-rollback-20260929/`. This folder is excluded from Git.
The first foliage pass uses 490 server entities and broad fast visibility;
measure client CPU/FPS and network traffic with multiple riders before raising
the foliage budget or publishing. The auto-grass code from PrimeXT is not linked
into the current MSR client, so this pass uses supported native model entities.
The six editable props and their original textures are in the sibling
`Daragoth-Foliage` directory. Their current shapes, density, and placement are
an initial visual treatment, with close-up rendering and grove lighting still
subject to playtesting.

All geometry and WAD textures in this directory were generated for this project.
They contain no downloaded images or geometry extracted from the original map.

## Native collision tracing

Use the development Xash engine together with the matching Debug client and
server DLLs. The old hull tracer can report a false ceiling on shallow adjacent
terrain planes, stopping a walking character or horse on clear ground. The
development tracer partitions the actual segment before applying its contact
epsilon at a genuine solid impact. A separate player movement correction accepts
a clear step trace whose fraction is 1, even when its unused normal is zero.

`Development-Tests/test_engine_hull_trace.py` compiles the production engine C
function in MSVC x86 Debug mode. Against the frozen plains BSP it checks 83,104
floor probes and 82,965 horizontal sweeps: nine former false ceilings become
zero. Real walls, ceilings, steps, drops, thin obstacles, water, both clipnode
formats, and start-solid contracts are covered separately. The movement replay
test checks the actual `PM_WalkMove` body. Neither test adds an artificial floor
clearance to the mounted player.

An exiting trace still reports start-solid and retains its native fraction and
endpoint; the player caller still clamps movement to zero. If the physical
segment exits solid space, all-solid now correctly clears. Non-player fly/toss
physics can therefore escape an initial solid volume that the old biased tracer
incorrectly treated as solid throughout. These are development engine changes;
the published baseline engine is not replaced by generating this map.
