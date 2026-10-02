# Daragoth horse prototype

This directory preserves the first generated horse as a rebuildable rollback.
The current runtime appearance comes from the licensed textured conversion in
[`Textured-Horse`](Textured-Horse/README.md). The statistics and source files
below describe the earlier generated model, rather than that replacement.

An original chestnut horse for the first mount experiment: shaped torso and
long head, articulated legs, mane and tail, sage saddle blanket, leather
saddle and bridle, reins, stirrups, and brass fittings. Geometry, texture and
animation were generated locally; no third-party horse assets were used.

The prototype used `Portable-Package/game/msr/models/mounts/plains_horse.mdl`.
Its texture and three animations are embedded in this one GoldSrc v10 file.

| Runtime sequence | Index | Frames | FPS | Duration |
|---|---:|---:|---:|---:|
| idle | 0 | 41 | 20 | 2.0 seconds |
| walk | 1 | 25 | 24 | 1.0 second |
| gallop | 2 | 21 | 30 | 0.67 seconds |

Coordinates are **+X forward**, **+Z up**, feet near **Z=0**. The saddle seat
anchor is **(-1.8, 0, 64.6)**; attachment 0 tracks the body bone. This is a
mount development prototype with rigid segment skinning. Mount ownership,
movement, the human rider's seated pose, and camera position are implemented
separately in the client/server code. The current collision body remains the
standing player hull; a full horse footprint and horse sound effects are still
development work. This asset does not imply persistent mount ownership on FN.

## Source and rebuild

`generate_horse.py` contains the complete asset generation and SMD export.
`MSR-Daragoth-Horse.blend` keeps the editable components, a 22-bone rig, three
animation actions, packed texture, lights and camera. The `export` directory
holds the QC, reference mesh, three animation SMDs, and 512×512 indexed BMP.
`horse-preview.png` and `horse-side-preview.png` show the actual generated mesh.

Run Blender 4.5 LTS with:

```powershell
& 'path\to\blender.exe' --background --python .\generate_horse.py
Set-Location .\export
& 'path\to\pxstudiomdl.exe' .\horse.qc
```

Copy the resulting `plains_horse.mdl` to the runtime asset path above. The QC
explicitly sets `$origin 0 0 0 -90` to cancel pxstudiomdl's built-in +90-degree
rotation; omitting this would make the horse face sideways in the game.
`$gamma 1.8` preserves the authored palette. Use the GoldSrc v10 compiler
without `$staticprop` or `$boneweights`.

Compiled export copies and Blender backup files are ignored. The runtime asset
path is the canonical location for the MDL; the editable source and rebuild
inputs remain in this directory.

The compiled prototype has **3,538 triangles**, **1,979 vertices**, **22 bones**,
and **6,138 submitted vertices**, safely inside this engine renderer's arrays.
`horse-validation.json` records the compiled file hash and renderer checks.
`check_compiled_horse.py` verifies the compiled orientation, saddle attachment,
sequence order and loops, and preservation of the original texture palette.

Generated geometry, texture, rig and animations are dedicated under CC0-1.0.
The generating script is MIT licensed; see `LICENSE.txt`.
