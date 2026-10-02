# Textured Daragoth horse

This replaces the original generated mount's appearance with Lyndon Daniels'
CC0 horse and ChadM's CC0 rig. The converted mesh uses native rigid weights,
attached mane/tail/eyes, original saddle equipment, and newly authored looping
idle, walk and gallop actions. See `LICENSE.txt` for asset provenance and scope.

`MSR-Textured-Horse.blend` is the editable, packed conversion source. It opens
without the original download. `prepare_rig.py` can recreate it from the exact
upstream file identified below; it verifies that input hash and never saves
over the upstream source. `export_horse.py` exports the saved conversion with
embedded diffuse textures and native single-bone assignments.

## Rebuild

Use Blender 4.5 LTS and a Python interpreter with Pillow installed:

```powershell
& 'path\to\blender.exe' --background --disable-autoexec --python-exit-code 1 --python .\export_horse.py -- --input .\MSR-Textured-Horse.blend --output .\export --texture-python 'path\to\python.exe'
Push-Location .\export
& 'path\to\pxstudiomdl.exe' .\horse.qc
Pop-Location
python ..\..\..\Development-Tests\test_textured_horse_model.py --mdl .\export\plains_horse.mdl --textures .\export
```

Use the GoldSrc v10 compiler without `$boneweights` or `$staticprop`. The
exporter splits permanent bodyparts to stay within the shipped renderer's
arrays; all 27 parts draw with body index zero. `$origin 0 0 0 -90` cancels the
compiler's built-in rotation. `$gamma 1.8` preserves the diffuse palette.
The compiler resizes the large textures to 556 by 554; non-power-of-two sizes
are supported in this path. Hair uses palette index 255 for transparency.

The runtime contract is +X forward, +Z up, feet near Z=0, and attachment zero
at (-1.8, 0, 64.6), relative to the rest pose. Sequence indices remain 0 idle
(41 frames at 20 FPS), 1 walk (25 at 24), and 2 gallop (21 at 30). The compiled
model has 19 bones, 18,690 triangles, eight embedded textures, and at most
5,392 submitted vertices per submodel, below the 16,384-entry renderer arrays.
The canonical MDL is `Portable-Package/game/msr/models/mounts/plains_horse.mdl`.

## Provenance and limits

Upstream downloaded `lyndon-rigged-horse.blend` SHA-256:
`9cca670b93a74d50e89263e50d55ab035a6c46aa7d2b21e354bdac6987037f4a`.
Converted blend SHA-256:
`c3e22613337d724dac7b875e26c049947d550bd85f22ca1cb0f75df28e5a14ff`.
Compiled MDL SHA-256:
`7b109d3f5228be595ada6f5f23c4cb941cb24bfcafb3f1db9dabb6311089c014`.

The seat now has a closed padded tree contoured to the blanket, closed leather
supports inside the cantle/pommel outlines, and brass fittings seated on the
cloth. These remove the visible suspended-seat gaps in the first conversion.

These gaits are an authored prototype, not motion capture. Rigid skinning and
indexed diffuse textures reduce the original soft skin and texture fidelity;
the original normal/AO maps are retained in Blender but not exported as native
PBR materials. A tiny moving blanket/flank contact at gallop frame 5 remains
in the geometry audit (0.043 game units); the supplied views show no open hole.
Movement still uses the standing player's hull and existing rider pose. This
asset adds no horse sounds, horse-sized collision, or persistent FN ownership.
The current mounted draw offset raises hips to67 units above the horse's feet,
clearing the padded seat. The stablemaster issues separate per-session loans.
The earlier generated horse source remains in the parent directory as a
rebuildable rollback. Native evidence is recorded separately from model checks.
