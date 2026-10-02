# Daragoth meadow and Greenhollow development preview

This art pass adds broad rolling grassy hills, mixed groves, slope-aligned
grass patches, and the small timber village of Greenhollow to the continuous
Daragoth prototype. The original valley, guards, starting pool, and northern
road remain in the same map. Travel into the fields uses no fade or loading
screen. The preceding plains builders and compiled private backups remain
available for rollback.

The original `Deralia_3dskybox.mdl` decoration spans tens of thousands of
units beyond its tiny authored entity bounds. Its windmill and walls intersect
the newly traversable fields. This variant excludes that single surveyed
decoration; the prior builder's default and the original game stay unchanged.

The meadow palette follows the original grass's measured color and the
original sun settings. Its bitmap pixels come from an independent procedural
noise texture. Fine global UVs reduce the large repeating diagonal pattern.
The denser grass pass uses 760 patches, each with 36 small crossed sprays of our
own CC0 grass. Each patch has 288 triangles, half the preceding patch's count.
Minimum patch separation is 142.8 units. Masked alpha and scene-lit flat shading
prevent dark card backs; fullbright is disabled.

Natural boundary terrain raises grassy lower foothills into steeper rocky upper
faces along the west/east/north perimeter and beside the original entrance.
Multiple bounded waves break up ridge crests into unequal peaks and saddles.
An independently generated, tileable stone bitmap reduces the former broad
checker pattern on the slopes.
The entrance road stays flat across the surveyed opening, with no fade or map
load. The river bridge, village routes, stable door and far Deralia road remain
usable. Analytic protected pads retain their base height, though interpolation
between coarse terrain vertices can change nearby ground. The old seam caps,
SKY shell and PVS coverage remain for closure beneath the feathered banks.

Greenhollow has six enterable buildings, a well, garden beds, timber framing,
chimneys, and generated leaded windows. Four harmless residents follow actual
NPC walking routes through the square. Their names are Mara, Bren, Tessa, and
Oren. The resident roles do not yet provide merchant inventories or inn
services. Horse ownership remains temporary in this development build.

The October1 scale correction reduces building footprints to about60% of the
initial layout while keeping plots and resident routes fixed. Wall height is
112units instead of256; roof rise is88instead of180. Doorways are80by92,
around the villagers'70-unit visual height and72-unit standing hull. Windows,
benches, chimneys and farmhouse entrance steps follow the smaller proportions.

## Build privately

Run these from the repository root, using Python 3 and the native PrimeXT map
tools/model compiler. Keep original game inputs read-only and use a scratch
output. This directory includes the original foliage source needed to rebuild
the patch without a previous generated export.

```powershell
python Design-Source/Daragoth-Meadow/build_grass_patch.py --source Design-Source/Daragoth-Meadow/SourceAssets --out ../daragoth-development/meadow/grass --compiler C:/Users/cptki/Documents/Codex/MSR-Male-Adventurer/InGamePreview/compiler/build/pxstudiomdl.exe
python Design-Source/Daragoth-Meadow/build_meadow.py --original C:/MSR/Portable-Package/game/msr/maps/daragoth.bsp --ent C:/MSR/Portable-Package/game/msr/maps/daragoth.ent --out ../daragoth-development/meadow --tools C:/Users/cptki/Documents/Codex/MSR-BigWorld/src/build-tools/Release/msr/devkit
python Design-Source/Daragoth-Meadow/build_scripts.py --base ../daragoth-development/expanded/scripts.pak --out ../daragoth-development/meadow/scripts.pak
```

The script library builder appends five original village scripts and verifies
that every existing record's bytes survive unchanged. It does not translate
or replace the existing MScript library. The model builder sets the native
GoldSrc v10 flatshade bit explicitly because this compiler's QC parser lacks
that keyword. It asserts masked alpha and rejects fullbright.

For a private runtime, stage the merged BSP as `msr/maps/daragoth.bsp`, the
expanded script library as `msr/scripts.pak`, and the new prop as
`msr/models/plains/meadow_grass_patch.mdl`. The earlier original foliage models
are also required. Back up and hide any private `daragoth.ent` sidecar, rebuild
the private FN manifest, and restart the private FN/game server together. Use
`ms_region_unload_time 0` for this adjoining-region prototype.

## Validation and limits

The actual x86 Debug C collision harness checks all four seam hulls, original
geometry preservation, riding landmarks, field contacts, grass mesh roots,
resident paths, and each doorway in both directions. Separate native game
captures check appearance, camera position, real walking, mounting, and riding.
Sanitized results belong in `Development-Tests/Reports`; raw game logs, original
textures, screenshots, compiled combined BSPs, FN data, and identities stay in
the private lab.

The earlier meadow checkpoint is SHA-256
`67b57adc312a950635afcbdb9cd9fda1c8cc237cd811af926080cff478b2c43b`.
Its original validation record remains in
`Development-Tests/Reports/daragoth-meadow-preview-20260930.json`.

The denser grass/natural boundary candidate is SHA-256
`3c55d11e5121d40ee43f4369d2fbb4dd35fde34cfe3835faf0ddd946095334c3`,
CRC32 `3264622046`. Playable interior mesh slopes remain below 24 degrees;
intentionally steep boundary faces reach 75.424 degrees. Terrain peaks at
3220 local units beneath the 4096-unit SKY ceiling. All eight static audit
sections pass. The focused boundary audit requires consecutive sampled real
steep hull0/hull1 contacts and rejected 18-unit steps across at least 256 units,
plus production movement and compiled contact-connectivity checks. The
[sanitized checkpoint](../../Development-Tests/Reports/daragoth-natural-boundary-preview-20260930.json)
records these audits, four native walking approaches and retreats, a real
mounted gallop/retreat at the eastern boundary, and visible village resident
movement. The final old-valley and north-road recaptures did not verify their
requested locations and are explicitly excluded as placement evidence.
Snapshot frame rates are individual frames, not a benchmark.

`Development-Tests/test_daragoth_meadow.py` reproduces the static audit with
explicit `--bsp`, `--expected-sha`, `--previous-bsp`, `--original`,
`--source-report`, `--merge-report`, `--grass-model`, and `--report` paths.
Run in an x86 Visual Studio environment with `cl.exe` available. It rejects a
changed candidate before probing and checks its hash again after completion.

The independent segment-contents oracle partitions exact BSP half-spaces and
uses the harness's float32 endpoints. The former 33-point sample check missed
real 0.005649-unit terrain solids, mislabeling them as empty-space collisions.
Six synthetic regressions cover thin solids, reverse travel, empty paths,
stationary points, endpoint ownership and water. Existing true-empty collision
regressions remain detected. The engine and original geometry are unchanged.

This is a local development preview, not a published update. Broad planar rock
faces, the rectangular footprint, repeated grass placement and basic building
forms still need art work. Detailed village
interiors, quests, full neighboring-map travel, and
performance on other PCs still need work. It runs the existing Debug Win32
Xash renderer and does not claim PrimeXT PBR or modern grass shaders.

The October1 private preview also uses the converted CC0 textured horse with
an attached mane, original saddle and three native gait loops. See
`Design-Source/Mounts/Textured-Horse/README.md` for provenance and rebuild steps.
The current stablemaster/orchard BSP SHA-256 is
`e14b54e89f7a5870944c3759a3e8eda4e5e4b4ef962856b5ffbe52fe06da7b06`.
Its eight static QA sections pass, including all six doorways and16closed
resident route segments. The earlier September30 terrain/hash reports remain
historical checkpoints; current native evidence is recorded separately.

The original Daragoth road now continues into the fields at its original
256-unit width. All four mip levels and the palette of `DeraliaRoad_2_0` are
read from the supplied original BSP. The texture's world V axis remains
`[0,-1,0,200]`, preserving its phase across the join. Terrain triangles are
split along the narrow road edges without changing their surfaces or the
protected entrance collision. Side paths and village soil remain distinct.

Twelve apple trees form three small groves outside the village and nearby
fields. `build_edana_apple_tree.py` exports the installed Edana trunk and its
associated crown as one masked native model, excluding a second orphan crown.
Five original apple decorations accompany each tree; they are decorative and
do not implement harvesting. Extracted geometry, textures and models remain
private because their upstream asset licensing has not been established.
Only the exporter is included in source control. The reused road has the same
restriction; the original meadow grass, village geometry and CC0 horse retain
their separate provenance.

A native `ms_stablemaster` stands beside the stable. Approach and press the
bound **Use** key to request a loan horse, then use the horse to mount.
Each connected player can have one loan; repeat requests reuse it and other
players cannot mount it. Eight clear paddock pads bound the local capacity.
Loans disappear on character respawn, death, disconnect or map shutdown.
They are session loans, not persisted FN inventory items. The original public
prototype horse remains available separately. Mounted hips are raised three
units to clear the new padded seat; the standing collision hull is unchanged.

The private desktop entry is **MSR - Daragoth Preview**. Normal installation
and public realm deployment are separate from this development candidate.
The partner chat's whole-map meadow polish uses a separate candidate and must
be validated before replacing this checkpoint.
