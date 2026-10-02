# Original entrance post closure

The reported entrance image exposed the narrow north cap of an existing solid
rock post. Its east side and top had collision planes but no rendered faces.
The repaired candidate adds those two exact surfaces with the adjacent embedded
`rock01a_ewok` texture. It includes the six Greenhollow house doors.

The east side is at X1936, Y3088–3216, Z3072–3336. The top is at Z3336,
X1920–1936, Y3088–3216. An independent eight-unit survey found 528 side samples
and 32 top samples with solid space behind, empty space outside and no original
covering surface. Every sample now has exactly one covering face. The winding,
texture alignment, ordinary sixteen-unit lightmap spacing and visibility marks
also passed independent checks.

`build_entrance_side_closure.py` accepts only the frozen six-door candidate
`9a8e78380ee79271a911749d089fb1576a1f6f3ef54bb3f0e360ad91f200f2d6`.
Its output is
`77611d302aa1cf309550a517bed2c169388986341ff3bd02f06b5e1e8acdb4d7`.
The construction report SHA-256 is
`6c75b8e03c9dddd521deb96c187f5c89a54798d5393cdeec7b1c86fcccba4229`.

The builder inserts two world faces and remaps existing face references. All
21,071 original faces retain their exact geometry, material and lightmap
descriptors. All 1,053 ordered entities, model collision heads, collision trees,
PVS bytes, embedded textures and old render primitive prefixes remain intact.
The shared house-door model remains *165; its first face shifts from 21065 to
21067 without changing its six faces or four hulls.

The independent checker is `Development-Tests/test_entrance_side_closure.py`.
Its private static receipt SHA-256 is
`147331cc63e9e0cf2d68ab29cae585170a5d291478f5040d7556c2726e029b2a`.
Fresh native side, top and road views confirm the two repaired surfaces. All
eight recorded camera positions and view angles matched their bounded requests.
The raw combined run remains diagnostic because its first horse fixture faced
an uphill spawn obstruction; this does not turn that run into a whole-suite
pass.

The small dark speckles were reproduced separately and traced to an original
bush protruding through the wall. `ENTRANCE-BUSH-CLEARANCE.md` describes its
origin-only successor. The combined server regression and fresh successor views
remain required before installation. The accepted live map remains unchanged
while the human playtest is running.

The builder and checker require fresh output paths and refuse to overwrite
existing evidence. Neither launches a game nor changes a runtime directory.
