# Original Daragoth foliage kit

Six original model props for the expanded plains: a mature broad oak with
buttress roots and spreading branches, a slender white-barked birch, a layered
conifer, a berry bush, a weathered rock clump, and low grass with seedheads.
All geometry, UVs, bark and leaf textures, palettes, and wind animation were
generated locally by `generate_foliage.py`. No external meshes or images were
downloaded or incorporated.

Runtime files belong in `Portable-Package/game/msr/models/plains/`. Each model
contains its own textures and animation; no separate runtime BMP is needed.

| File | Height | Maximum footprint radius | Triangles | Submitted vertices |
|---|---:|---:|---:|---:|
| plains_oak.mdl | 480 | 277 | 4,128 | 7,460 |
| plains_birch.mdl | 430 | 112 | 1,836 | 3,352 |
| plains_pine.mdl | 520 | 169 | 3,810 | 6,534 |
| plains_bush.mdl | 64 | 56 | 594 | 1,062 |
| plains_rocks.mdl | 54 | 57 | 320 | 876 |
| plains_grass.mdl | 30 | 25 | 48 | 96 |

Dimensions are in game units. The radius column rounds the manifest's maximum
horizontal vertex distance from the ground-center origin upward to a whole
unit; it includes diagonal leaf extents rather than only X/Y bounds. These are
placement estimates for the authored resting mesh, not solid collision hulls.

All models use a **ground-center origin**, **+Z up**, and **idle sequence 0**.
Place as nonsolid `env_model` props with ground at the interpolated terrain
surface. Keep collision trunks separate and leave the riding route open.
The native scenery entity now uses scaled, rotated sequence bounds for server
visibility linking. Studio model loading previously reset these bounds to a
point; roots embedded below the ground could then disappear from network
visibility. The bounds change retains nonsolid scenery and mapper collision
settings.
Tree/bush idle loops add slight canopy sway; rock and grass idle are static.
The generated bounds and hashes are recorded in `foliage-manifest.json` and
`foliage-validation.json`.

## Transparency and compatibility

Leaf, needle and grass textures are 512×512 **8-bit indexed BMPs**. The QC
sets the native **STUDIO_NF_MASKED (0x40)** flag. **Index 255** is the transparent
hole. Its RGB is a nearby leaf green to prevent bilinear blue fringes; the
transparent index remains unchanged. Bark/rock textures are opaque. Palettes
are preserved with `$gamma 1.8`.

Card geometry has explicit front and back triangles, so it does not depend on
the PrimeXT-only `twoside` material extension. The model format is GoldSrc
studio v10, with ordinary bones and sequences. The QC uses
`$origin 0 0 0 -90` to cancel the compiler's automatic Z rotation.

`check_foliage.py` verifies file/table/triangle-command bounds, renderer array
budgets, bone indices, ground and height bounds, idle loop, texture masked
flags, actual index255 hole counts, and preservation of the original palette.
The check reads the compiled MDLs rather than relying on Blender materials.

## Rebuilding and previews

```powershell
& 'path\to\blender.exe' --background --python-exit-code 1 --python .\generate_foliage.py
Push-Location .\export
Get-ChildItem -Filter '*.qc' | ForEach-Object { & 'path\to\pxstudiomdl.exe' $_.Name }
Pop-Location
python .\check_foliage.py
```

Copy the resulting six MDLs from `export` to the runtime folder. The editable
`MSR-Daragoth-Foliage.blend` retains all components, packed textures, rigs,
gentle wind actions, cameras and lights. Previews:

- `foliage-kit-preview.png`: all six props together.
- `oak-detail-preview.png`: leaf cards and bark at closer range.
- `foliage-alpha-proof.png`: original leaf/needle/grass RGBA textures over a
  checkerboard to show the transparent cutouts.

Assets are development prototypes. In-game view distance, entity counts,
lighting, alpha overdraw and riding clearances still require map playtesting.
This first kit is placed in the separate `daragoth_plains` development map;
it does not replace trees in the original Daragoth or published BigWorld maps.
The initial map uses 104 trees plus 355 bushes, rocks, and grass clumps.
Varying regional vegetation, final grove dressing, and performance tuning are
later art passes. Compiled export copies and Blender backup files are ignored;
the runtime directory is the canonical location for the six MDLs.
Generated assets are CC0-1.0; scripts are MIT. See `LICENSE.txt`.
