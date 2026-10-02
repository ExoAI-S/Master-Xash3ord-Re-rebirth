# Animated creek and original entrance boundary

The first water and join candidates passed collision checks, but isolated native
views exposed two additional rendering problems. They are intermediate evidence,
not accepted preview maps.

`build_visible_creek.py` repairs a stock renderer mismatch. The renderer compares
a water brush's translated minimum height with its local face plane height. With
this creek's original Z2720 entity origin, it discarded every animated surface.
The builder appends model `*164`, baking the common vertical translation into its
vertices, planes and all four hulls, and removes that translation from the four
water entity origins. World positions, texture coordinates, embedded `!DPWATER`,
fluid contents and region ownership remain equal. Original geometry records stay
intact. The resulting visible-water input SHA-256 is
`22288e02f3b9b83a2f6bcb4bcebd05fefba3bb86460469ce11ec67525c6ea0f3`.

`build_boundary_closure.py` then restores the low entrance boundary previously
hidden by legacy exterior scenery. Ten original SKY faces below Z3584 become
ordinary lit `rock01a_ewok` faces using the embedded original rock. The same
material replaces the flat placeholder on the previous 90 join caps. One missing
solid rectangle at Y3088, X1936..2320, Z3072..3336 is inserted into its original
render node's contiguous face range. Three exact partitioned faces close the
eight-unit SKY/EMPTY strip at Y3216, X2432..2440, above the new bank and below
Z3584. High sky closure remains intact. Collision trees, entities, water geometry,
visibility data and the 84 meadow grass models remain unchanged.

The four added faces use proper outward winding, ordinary RGB style0 lightmaps,
and matching leaf marks. Render bounds expand only where needed. Subsequent face
references are remapped consistently across nodes, submodels and marksurfaces.
Modified render lumps are appended; the original file prefix remains unchanged
outside those lump directory descriptors.

Example from the repository root:

```powershell
python -B Design-Source/Daragoth-Meadow/build_visible_creek.py --base ../daragoth-development/meadow-join-repair/daragoth_meadow_repaired.bsp --out ../daragoth-development/meadow-visible-creek
python -B Design-Source/Daragoth-Meadow/build_boundary_closure.py --base ../daragoth-development/meadow-visible-creek/daragoth_meadow_visible_creek.bsp --out ../daragoth-development/meadow-boundary-closure
```

The builders refuse to overwrite frozen inputs or candidates. The boundary
construction candidate SHA-256 is
`676afa30a2e050a7dca9d56dfc82e1b40048e11c694d838d8e8b8abbd3224d05`.
It passed collision and native movement checks, but visual review found a
remaining flat original cap and a missing bed polygon visible through the water.
Its rejected native evidence remains preserved.

`build_join_material.py` replaces all 131 remaining original DPROCK seam caps
with the same embedded original rock and ordinary lighting. Only face material
and lighting records change; all geometry, references, entities, collision,
visibility and animated water remain identical. Its construction SHA-256 is
`a82d997a153543198f01c2d36199b7d78498f309c6a251fa70891abacbf69f29`.

`build_creek_bed.py` restores the exact missing render surface at node8808,
plane4474. It intersects that plane with its ancestor halfspaces and both child
trees, then subtracts existing coplanar faces. One upward face fills the remaining
49,047 square units. Adjacent DPGRASS texture coordinates and its original
style0 lighting grid are extended at the actual 64-unit lightmap step. Existing
faces, terrain slopes, collision and water contents remain intact. The face is
marked in the actual adjacent empty leaf4517 and the existing meadow visibility
anchors; later references are remapped consistently.

The wider creek survey's 313 missing ground-material results comprise 288
rendered solid rock banks, 12 rendered solid wooden supports/approaches, and
13 actual wet-bed omissions. All 13 wet points and 49 finer bridge-opening
points belong to this same missing surface. A nearby almost coincident plane
has complete rendered coverage and is preserved. An 8-unit local survey found
753 missing wet-bed samples before repair and none after, across 3,116 wet-floor
points. These are finite compiled surveys, not a claim of exhaustive walking.

The bed construction candidate SHA-256 is
`8388e76d2653f4acc09abc633b25c8ce94b816a9e99fb10743e8838edb37fdc3`.

The final bed candidate passed independent static checks, 405 native collision
traces, 23 isolated native placements and review of 28 fresh screenshots. Native
checks covered swimming, wading, three creek seams, the dry mounted bridge,
reload and the entrance road. Five entrance views were included. Root visual
review accepted the repaired bed, animated water and original rock boundaries.
The rejected 676 candidate and its original evidence remain preserved.

On 2026-10-02, the accepted 8388 candidate was installed in both private previews
through the reviewed map-only staging helper. All 242 protected files, including
controls, character profiles, DLLs, scripts and 84 meadow grass models per game,
remained unchanged. The first staging attempt failed before either map changed
because PowerShell coerced a null File.Replace backup argument to an empty path.
The versioned V2 helper uses [NullString]::Value; independent installation and
rollback primitive checks passed before the successful retry.

The private FN manifest changed only Daragoth's CRC. The restarted preview loaded
Daragoth with zero players and passed FN health checks. Both installed map hashes,
mouse-look controls, core binaries, profiles and FN character rows were verified.
Normal game files were preserved. Sanitized acceptance details are recorded in
`../../Development-Tests/Reports/daragoth-creek-join-repairs-20261002.json`.
Subsequent house-door work starts from this accepted map as a separate candidate.
