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

The builders refuse to overwrite frozen inputs or candidates. The final
construction candidate SHA-256 is
`676afa30a2e050a7dca9d56dfc82e1b40048e11c694d838d8e8b8abbd3224d05`.
Independent checks and fresh native visual acceptance are required before
map-only staging. Building these files does not modify either running preview.
