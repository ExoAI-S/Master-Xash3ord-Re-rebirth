# Plains wilderness encounters

This fixed-eight candidate is retained as a static reference. Its native
preparation and installation are held after the request for a larger, dynamic
population. The successor is described in `PROXIMITY-ENCOUNTERS.md` and uses
`build_proximity_encounters.py` with a new optional core. The planned checks below
describe the historical fixed-eight scope and have not run for this candidate.

The first encounter pass adds eight existing scripted enemies in four groups:
two orc warriors and an archer in the eastern meadow, two goblins in the western
fields, one troll in the northern wilderness, and two skeletons near the eastern
ruins. The original Daragoth encounters remain intact. Houses and the village
remain the quieter part of the map; the new starting pads are off the riding
road and clear of the creek.

The authored pads are fixed. Spawn chance is 100 percent, the minimum player
count is one, and there is no party HP threshold. Each group has its own named
`msarea_monsterspawn` controller and at most three slots. The controllers reuse
the original invisible, nonsolid `*24` cube; its linked center, rather than its
low translated origin, belongs to the plains region. Native verification must
confirm that cached classification. No world, collision, lighting or visibility
lump is rebuilt.

Templates name the existing `monsters/orc_warrior`, `monsters/orc_archer`,
`monsters/goblin`, `monsters/troll` and `monsters/skeleton` scripts explicitly.
The packed script library and original model files are unchanged. Death begins
a randomized 90–180 second respawn delay, with unlimited lives and no reset
waves. `set_no_roam` suppresses idle wandering; it does not leash pursuit or
guarantee that enemies cannot follow a player toward town.

`build_plains_enemies.py` requires a pinned, passing native house-interior review
before it writes a candidate. It appends four controllers and eight templates
to the accepted furnishings component, preserves its 1,138 ordered records and
all fourteen nonentity lump bytes and descriptors, and writes only new files
under the sibling private lab. It cannot stage a map, modify scripts, start a
game, or overwrite a prior output.

The initial placement audit checks nine rendered support footprints per actor,
216 script-box points, standing hulls and translated water volumes. It keeps
the large troll's actual 100-by-125 script box distinct from the engine's fixed
large trace hull. These are finite static checks; native grounding, resource
delivery, AI, damage, death and respawn require separate observations.

The first furnished encounter candidate is
`baadf57a4b7cbbe89ae22ef27aae3e306807a5b477dedeba052f73ac09453c08`;
its build receipt is
`20eea064c3358504067726ce899e4cb4c159af09614df602de042caef8593ab6`.
Independent static verification passes with no failures, receipt
`6a808e0f0ba70f5704752205925d4644e662f736e90ca9c3332c7b16c5dae66b`.
It checks the exact preserved raw file prefix, all old records and nonentity
lumps, the twelve new records, eight dry pads and twenty-seven original model
files including the furnishing texture companion. Every linked controller
center classifies as the plains; its serialized low origin remains outside the
tight vertical region bound, as expected from the compiled pivot translation.

Native acceptance and installation are pending. Planned verification uses an
isolated synthetic player and unchanged production binaries, observes all eight
normal actors and the five script species, then checks ordinary damage and one
death/respawn cycle per group. Region unload/re-entry, initial town and riding
route separation, and resource/network capacity are also checked. Source-only
reward rules and historical unchanged core/water/input checks will be labeled
separately from fresh observations. No public release is made by this pass.
