# Original entrance bush clearance

The small dark marks on the original entrance rock are leaves from an existing
bush protruding through the wall. Fresh views of the entrance-surface candidate
reproduced the marks. The compiled bush mesh crosses the wall at Y3088.

`build_entrance_bush_clearance.py` moves only that nonsolid bush, entity 460,
32 units south, from `2164.87 3015.32 3072` to `2164.87 2983.32 3072`. Its model,
pose, root height and other settings stay unchanged. The new position remains
on the original grass floor and leaves 24.713 units between the compiled mesh
and the wall. A finite survey of 40,596 above-floor triangle samples found no
world intersections; 6,521 equivalent samples intersected solid space at the
old position. The model's intentional root embedding remains intact.

The survey uses actual compiled triangles. The conservative rectangular bounds
include unused corners on an existing sloped grass bank, so the report does not
claim that the entire bounding box is empty. All 169 footprint samples have a
rendered floor.

The frozen base SHA-256 is
`77611d302aa1cf309550a517bed2c169388986341ff3bd02f06b5e1e8acdb4d7`.
The successor is
`0f8d0e4c429985eda72c8ce17f0480014a687d088f902e50ada1ea9b8c644754`.
The construction report SHA-256 is
`b5af56616a2fe37c9882fecb3bffcd53a11000d138f92de1c9c829819021ed85`.
Root's independent preservation review SHA-256 is
`4192517cc3e15a3767a647cf9bd25b235c3a2b9be16df3b7de697adf0efe7a2e`.

Independent byte comparison and ordered entity reload verified the sole origin
change. All 1,052 other entities and every other key of the changed entity are
identical. All fourteen nonentity lumps and their descriptors, extra Xash data,
world collision, visibility, doors, water, terrain and grass geometry are byte
identical. The builder preserves the original entity formatting and appends
the new entity lump; only its header descriptor changes in the old file prefix.

Fresh native after-views remain required before this candidate is accepted for
installation. The builder refuses to overwrite frozen maps or reports and does
not launch a game or modify a runtime directory. The accepted live map remains
unchanged while the human playtest runs.
