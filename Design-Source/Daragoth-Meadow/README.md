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
The new grass patch is twelve of our own CC0 tufts; masked alpha and scene-lit
flat shading prevent dark card backs. It does not use fullbright lighting.

Greenhollow has six enterable buildings, a well, garden beds, timber framing,
chimneys, and generated leaded windows. Four harmless residents follow actual
NPC walking routes through the square. Their names are Mara, Bren, Tessa, and
Oren. The resident roles do not yet provide merchant inventories or inn
services. Horse ownership remains temporary in this development build.

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

The frozen September 30 candidate is SHA-256
`67b57adc312a950635afcbdb9cd9fda1c8cc237cd811af926080cff478b2c43b`,
CRC32 `1159297584`. The seven static audit sections pass. Native captures
confirm that the interfering skyline is gone, camera positions match the
server placements, horses ride at 320/520 units per second, and all four
residents move. Final Debug 1280x720 snapshot counters range from 29 to 60 FPS;
these are individual frames, not a benchmark. The sanitized record is
`Development-Tests/Reports/daragoth-meadow-preview-20260930.json`.

`Development-Tests/test_daragoth_meadow.py` reproduces the static audit with
explicit `--bsp`, `--expected-sha`, `--previous-bsp`, `--original`,
`--source-report`, `--merge-report`, `--grass-model`, and `--report` paths.
Run in an x86 Visual Studio environment with `cl.exe` available. It rejects a
changed candidate before probing and checks its hash again after completion.

This is a local development preview, not a published update. Natural cliff
relief, detailed village interiors, quests, full neighboring-map travel, and
performance on other PCs still need work. It runs the existing Debug Win32
Xash renderer and does not claim PrimeXT PBR or modern grass shaders.
