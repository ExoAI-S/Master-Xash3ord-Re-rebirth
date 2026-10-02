# Greenhollow house furnishings

The six village houses have separate authored interiors using 22 existing game
models and 85 static decorations. The inn has a dining set and tea corner; the
workshop has a workbench, manuals and tool storage; the south cottage has a
sleeping corner and breakfast table; the north cottage has a study and alchemical
shelf; the bakery has individual loaves, preparation utensils and serving dishes;
the farmhouse has a bed, locker, small meal table and agricultural tools.

These are detailed original-game studio models, including selected book-filled
and alchemical shelf bodies, rather than additional block furniture. Small
objects sit on authored tables, plates or the existing bench. Candles and logs
are decorative; this pass adds no fire, pickup, loot, merchant or furniture
collision behavior. Existing house lighting and solid benches are retained.

`house_interiors.py` owns the six layouts, model hashes and actual selected-body
sequence0/frame0 bounds. The compiled bone hierarchy and compressed animation
channels are replayed before building; header bounds alone are insufficient
because the chair model also contains a large table body. All selected assets
have no bone controllers or model rotation flags. Orthogonal authored yaws and
uniform scales make the placement bounds reproducible. Floor contact is at
Z3128. A 64-unit central aisle, a conservative 100-unit hinge reserve and the
existing solid bench are kept clear of the new render geometry.

`build_house_interiors.py` appends only new nonsolid `env_model` records to the
frozen e942 north-bank successor. It preserves all 1,053 old ordered records,
their raw text, fourteen nonentity lump descriptors and bytes, all old file
contents outside the entity descriptor, world collision, visibility, lighting,
fourteen doors, five water entities and 84 grass sectors. It accepts a pinned
layout and map, rehashes the original models, writes only new files under the
private sibling `daragoth-development/house-interiors` lab and refuses overwrites.

The furnishing candidate SHA-256 is
`cc879ec6bc9a6929f84ff0b39b04d70860dd89920f3c00c81133e18b4c97a6ab`.
The build receipt is
`97c8573463ea5cfc3c0f224d9c4e430c940aa943183a2ca883df8236aeb66243`;
the authored layout is
`fc62bec568f01f01e9d7c2a6894691926c89dbbb74077f23bc88afe24ae32cdc`.

The first a0b candidate was rejected before any native launch because six inn
dishes floated above the broad tabletop and five food items had small gaps
above their plates. Its source, map and prepared fixture remain byte-exact in
the lab. Eleven Z corrections preserve every target, model, body, XY position
and angle. The successor validates actual triangle footprints: all 42 modeled
support contacts have 0.04–0.07 units of separation, with no negative mesh
overlap; the other 43 props touch actual floors or the existing bench. The
mandatory `shovelT.mdl` texture companion is also pinned. Independent selected
body/bone replay, all 7,517 above-floor drawn vertices, 30 standing-route samples
and exact map preservation pass. The independent receipt SHA-256 is
`5ee322056871d0c4ebcc5127da197e7a8dedb5a0a56818fe02013f7992a1af69`.

Root reviewed all twelve original 1280-by-720 native images, covering each
interior from the entry and back, and accepts their finite presentation. All
85 exact server furnishing states match at every view; the 22 primary models
have positive loaded indices, and network/resource errors are zero. All owned
synthetic processes are stopped. The independent native review is
`77ffeb9e22ad28c966acd8f33bdb69b87939ca8270def7093ccc182d19042649`;
the root component acceptance is
`a69daef6d036e846c6b0fa3671657ea74861c772732590eda156b1ee12a50f7f`.

The raw strict camera diagnostic remains false: the inn entry pitch was 7.5
degrees instead of the planned 15; the other eleven measured 13.5 and passed
the original tolerance. Root accepts the recorded entry view and complementary
back view for presentation, with that exception explicit and the raw failure
unchanged. Two earlier blocked checker launches, including a bounded string
reader repair, remain separate. The stopped native archive contains 66 pinned
files with SHA-256
`2e6bfaf56f8201fd8712fc40f8f73bd1472ceb57d523709ac28e0cb1b77f3bca`.

These noclip images do not certify ordinary walking, door operation or individual
network delivery of every prop. Furniture is decorative and nonsolid, including
the wooden bed frames. Existing interior lighting is retained. Static support
and clearance checks are finite. The human playtest remains on the accepted
0f8 map and original controls; no live installation has occurred.

The user's requested next pass adds existing scripted orcs, a troll, goblins and
skeletons in optional wilderness encounters after interior acceptance. Original
Daragoth encounters remain intact. Monster source semantics and off-route pads
are being reviewed separately; no enemy native acceptance is claimed here.
