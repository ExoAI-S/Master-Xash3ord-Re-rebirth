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

Root reviewed six fresh native after-views at original resolution, including
close, far and oblique wall views, the repaired side and entrance context. The
former black leaf intrusions are gone. All six camera positions and yaw angles
matched; five pitches matched strictly. The top context view used an actual
10.5-degree pitch instead of the requested 20 degrees. Its context was accepted
with that explicit exception, retaining the raw strict failure. The cap geometry
is byte identical to the previously accepted entrance candidate's top proof.

The root combined native review SHA-256 is
`ca70bfb12379af2aead6b18057e51e5380393de9f6225676c548aa9d0660fcc4`.
It links the frozen door base, final horse and logical input checks, independent
preservation reviews and 72 verified support files. The scope is finite; it
does not claim native traversal of every point in the map or physical keyboard
and mouse verification. The full original controls preset and final transaction
also passed their separate reviews.

The builder refuses to overwrite frozen maps or reports and does not launch a
game or modify a runtime directory. The accepted successor is now installed in
both private previews with the reviewed server and 57 original supported control
bindings. The stopped-session transactions, verified backups, Daragoth-only FN
checksum refresh and no-client restart checks passed. Existing settings,
profiles and FN account/character/revision records were preserved. The human's
requested playtest was opened afterward. The installed checkpoint and receipt
hashes are recorded in `Development-Tests/Reports/daragoth-final-native-20261002.json`.
