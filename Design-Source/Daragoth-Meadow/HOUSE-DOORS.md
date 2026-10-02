# Greenhollow house doors

The inn, workshop, two cottages, bakery and farmhouse now have authored wooden
doors. Use opens a door and Use closes it again. The existing eight Daragoth
doors remain unchanged. Each new door has its own native movement state.

`house_doors.py` defines the shared geometry and settings. `village.py` includes
the doors in future village generation. `build_house_doors.py` builds the same
doors directly onto the accepted private meadow map, without recompiling the
accepted terrain or creek repairs.

The builder compiles one original 6×72×90 wooden leaf and an ORIGIN pivot brush
in an isolated sealed room using PrimeXT CSG, BSP, VIS and RAD. It appends only
that brush model's render records, four collision hulls and ordinary style0 RGB
lighting, then instances the model at all six entrances. The embedded DPWOOD
texture is reused. Door sounds use the existing game fallback assets.

Each 80×92 entrance has four units of side clearance and one unit above and below
the closed leaf. The hinge placement permits both 90-degree opening directions
without sweeping into the original walls. Fully opened doors leave a 73-unit
aperture, with a 41-unit range of center positions for a normal standing player.
Native two-way doors choose their opening direction from the activating player.
Use-only and toggle flags are set; the doors have no crush damage, and their
nonnegative wait setting permits the native blocked-door reversal behavior.

The accepted base SHA-256 is
`8388e76d2653f4acc09abc633b25c8ce94b816a9e99fb10743e8838edb37fdc3`.
The six-door construction SHA-256 is
`9a8e78380ee79271a911749d089fb1576a1f6f3ef54bb3f0e360ad91f200f2d6`.
All 1,047 old ordered entity records, existing model records, original lump
prefixes and visibility data remain unchanged. The world and all its old hulls,
water entities, bed repair, original entrance closure and meadow grass remain
intact. The new brush model is *165; the total entity count is 1,053.

Independent static checks cover the isolated compiler mappings, texture, UVs,
lighting, old records, four analytic hulls and all six fitted placements. A
36,630-point sweep found no wall contacts across both opening directions at
five-degree intervals. The original engine collision implementation passed 144
traces: 36 closed-door blocks, 72 clear passages with doors at ±90 degrees and
36 unchanged world passages. These are finite compiled checks; native Use,
movement and fresh screenshot acceptance are required before installation.

The first native run with the previously accepted server exposed an existing
rotating-door interaction defect. The first opening worked, but later Use presses
could miss the door because the selection code combined rotation-expanded
absolute bounds with the unrotated model size. Some doors could not be reopened
from inside. That run is explicitly rejected and preserved under the private
`house-doors/diagnostic-server99-run01` folder; its screenshot labels are not
proof of successful door states.

A localized server Use-target correction now selects the nearest point on the
rotated door's actual local bounds. With that server, all six doors passed native
outside opening, inside closing and reopening, closed-door blocking, normal
entry and exit, blocked-motion reversal and no-injury checks. A full six-house
run and a bounded two-house supplement are explicitly linked; their original
diagnostic failures remain preserved. Reload restored the closed doors.

The accepted base door server SHA-256 is
`9e3dea1e96e365d45a4fcced005b5d06893a48b4459a72daaf9955cd07b9ba1b`.
The private combined native receipt SHA-256 is
`a9c10e804b63c6dceb2492bfcf3f961603dce0bd49bfb70973c35332afadbec3`.
Visual review covered all six houses, the wide inn view and reload. One farmhouse
inside view had an actual 9.6-degree downward pitch instead of the requested
zero; the closed leaf and frame remained clearly visible. This exception is
recorded without changing the original strict camera failure.

This accepts the frozen six-door map and door-use server as base evidence. The
successor map also closes two entrance post surfaces; its combined regression
with the forthcoming horse water recovery server remains required before live
installation. No door candidate has replaced the accepted live map yet.

Example from the repository root, using a fresh isolated output:

```powershell
python -B Design-Source/Daragoth-Meadow/build_house_doors.py --base ../daragoth-development/meadow-creek-bed/daragoth_meadow_bed_repaired.bsp
```

The builder refuses to overwrite an existing candidate or accepted map. Building
does not modify either running preview. Live play sessions must finish before
the separately verified candidate is staged and the private server reloaded.
