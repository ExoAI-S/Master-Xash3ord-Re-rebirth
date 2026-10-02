# Rotating brush door Use regression

The isolated six-house Daragoth door test found that ordinary Use could open and
close a door once, then miss the closed leaf from inside. After rotation,
`SetObjectCollisionBox` leaves a conservative radius cube in `absmin`/`absmax`.
The historical `VecBModelOrigin = absmin + size / 2` no longer locates that leaf.
The archived inn inside-reopen sample points east at the closed door, while the
old target direction points behind the player.

`CBasePlayer::PlayerUse` now handles usable `SOLID_BSP func_door_rotating` objects
with the actual local `mins`/`maxs`, current origin, and full pitch/yaw/roll basis.
It inverse-transforms the query into the leaf box, clamps to its nearest point,
then transforms back. Reach remains 64 units measured from the player's origin;
the view-cone dot uses a normalized direction from the player's eye.
`EngineFunc::MakeVectors` supplies local outputs through its existing
`AngleVectors` wrapper and does not overwrite the player's global view basis.

Other entity selection, the early mounted-player Use hook, and the global
`VecBModelOrigin` used by effects and damage are unchanged. This does not add
line-of-sight occlusion to the pre-existing general Use selection policy.

`test_rotating_door_use.py` compiles the production geometry helper and exact
unchanged production angle/clamp routines. The C++ regression includes the
recorded old failure and corrected inside/outside directions; all six box faces
with noncentral origins; zero, +/-90, intermediate and mixed pitch/roll angles
against an independent Euler matrix; normalized directions; origin-based reach
limits and rejection of distant broadphase matches. All 2,002 checks pass.
The source-bound integration checks retain the old ordinary-entity branch and
confirm the local angle wrapper cannot alter view globals.

The isolated x86 Debug build includes this fix and the horse dry-bank water
release. Its final DLL is SHA-256
`306fb70f432d8f155e1b5faca06b25e7aa9e127f3ebd3670564f9439fa7db8a0`;
the matching PDB is
`592f26c4af132f5b8e5beb67394498e2aa18fca2d253bebad4e35349f359e6db`.
The separate door-only bundle remains preserved. All 330 final build inputs
have individually verified archived copies.

Native testing accepted repeated Use from both sides of all six houses on the
combined map, plus a fresh inn regression with the final server. The final bush
clearance map changes only one foliage entity's origin; door entities and all
14 non-entity BSP lumps remain byte-identical to the functional test map. Its
visual review and independent preservation review passed.

On October 2, 2026, the reviewed map/server/PDB and original controls were
installed in both private development runtimes with verified backups. FN's
Daragoth-only whole-file checksum was refreshed before restarting. No-client
postflight verified the active map, matching loaded module/PDB identities,
engine non-entity lump CRC, FN startup validation and current content checks.
Existing settings, profiles and FN account/character/revision contents matched
the stopped-session baseline. The ordinary installation and public release
were not updated. Map rollback must likewise refresh the FN Daragoth checksum
before restart.

Acceptance does not establish exhaustive traversal of every map point or
physical OS keyboard/full mouse-inventory interaction. The private playtest was
then opened at the player's explicit request.
