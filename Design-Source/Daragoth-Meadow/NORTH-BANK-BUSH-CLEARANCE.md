# North entrance bank vegetation

The whole-map followup found visible leaf geometry from original nonsolid bush
304 inside the added north entrance bank. The indexed texture audit reproduced
411 opaque intersections among 2,256 sampled points above the root. One example
is at `(85.661, 3244.087, 3467.335)`, inside the solid behind DPROCK face 15986.

`build_north_bank_bush_clearance.py` moves this bush from
`93.5564 3183.91 3432` to `113 3136 3432`, a 51.7051-unit shift. Its yaw of
27 degrees, scale of 0.8, single-frame idle pose and other keys remain exact.
The production studio renderer applies the compiled bone pose before the
entity's yaw and uniform scale; the audit includes those transforms.

Both positions retain the horizontal rock ledge, face 1440 at Z3432, and the
original 13.7005-unit root embedding. The new stem stays 94.5635 units from
neighboring bush 303. Their inherited natural canopy overlap remains. A denser
32-division survey found 11,420 old above-floor mesh samples in solid space;
all 40,596 successor samples are empty. The independent nondegenerate triangle
and indexed-opacity replay also passed with float32 coordinates: 23,664
above-floor points, including 12,012 opaque points, have no nonempty contacts.

The first coarser placement at X112 missed 36 low above-floor contacts. The
denser diagnostic preserves that failure and selects X113. Root contact,
standing hull clearance and the floor height remain unchanged. These are finite
compiled checks, not an exhaustive traversal of the continuous map.

The frozen accepted base SHA-256 is
`0f8d0e4c429985eda72c8ce17f0480014a687d088f902e50ada1ea9b8c644754`.
The candidate SHA-256 is
`e942e42c6112a11858148ce279c8ffbe39e769059d60cb332c396b9c1020e927`.
The build receipt is
`957e19c59844e4e39c077767d1288a81bd8b5d7d3f5a2372e27a936cb9c866d5`;
independent placement review is
`33ca2718a5f4e902607f5a5f716ecfda24acee1b315607f347fdfade7a16d0ce`;
independent preservation review is
`4764c1d653873efb831dcf88014501d92b1f7262599ea529aa3e758fd841adf1`.

Independent byte comparison confirms the sole origin value change, including
raw entity formatting. All 1,052 other ordered entity records, fourteen
nonentity lump descriptors and bytes, Xash extras, model collision heads,
visibility, fourteen doors, five water entities and 84 grass sectors survive
unchanged. The builder accepts only pinned inputs, writes separate scratch
outputs and refuses to overwrite prior evidence.

Five fresh before/after camera pairs passed exact bounded pose checks with
zero network errors, using the same frozen client, engine and server. The road
control retains its appearance. The nearby tree canopy obscures much of the
four lower views. The elevated supplement shows the old high leaf cards against
the bank removed; some inherited neighboring lower foliage remains. Root viewed
all ten original PNGs at full resolution and accepted this finite improvement.
The elevated point camera is EMPTY, although the imaginary standing hull at
its eye is SOLID; that diagnostic exception is explicitly retained.
These are isolated noclip diagnostic cameras;
they do not certify ordinary walking, riding, physical keys or mouse behavior.
The test fixture's cleanup timestamp formatting refusal and exact UTC-tick
guard correction are retained in its evidence.

Root review SHA-256 is
`a3d6baebcb501d897c25af61a0299d20307c61c40bebb5065db6b89c670a6ca7`.
The four-pair comparison is
`7ef10cf978a26982e8f2309119bde3e2e02b81f511f17dd73371c98033f717ee`;
the elevated comparison is
`05039ecd5d7caa63273add63dbed4e511d0ae7a0b463761ccf8dbe726d954127`.
Original diagnostic receipts remain unchanged and are superseded only by the
separate root review. A prelaunch CRC type correction in the isolated FN clone
also retains its original artifacts. No failed native view was reclassified.

This candidate is not installed. The open human playtest retains the accepted
0f8 map and original controls. No player data, runtime settings or accepted
rollback assets were changed. Native evidence stays in the private sibling lab
under `meadow-next`; the installed checkpoint remains recorded separately in
`Development-Tests/Reports/daragoth-final-native-20261002.json`.
The separate reviewable candidate checkpoint is
`Development-Tests/Reports/daragoth-north-bank-bush-20261002.json`.
