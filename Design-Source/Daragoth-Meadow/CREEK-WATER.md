# Creek water beneath the meadow bridge

The accepted whole-map meadow had a narrow creek brush that stopped short of
the bridge opening. Its `func_water` entity also lacked `skin -3`, which the
engine requires to apply water contents and swimming state. The brush's raw
water hull was already passable; the missing key does not establish a solid
collision barrier.

`build_creek_water.py` accepts only the frozen meadow BSP
`7db33aa84ff9f032d1267e3d37d2795e959e414c262dcb896c83a3169c1e5570`.
It translates four instances of the existing compiled `*162` brush into a
continuous channel. Their water surface is at world Z2936, 232 units below
the bridge underside. Both outer ends terminate beneath the banks. The four
entities use `skin -3`, `spawnflags 0`, transparency 120, and zero wave height.
The generator's original creek entity receives the same contents key so future
source builds retain water classification.

The output changes only the entity lump and its header descriptor. All fourteen
other lumps, the existing file prefix, and 1,043 other ordered entity records
remain identical. The result has 1,047 entities and preserves the 84 spatial
grass models. Rebuilding produces the same candidate SHA-256:
`9b3ae9aaeb56ff274f0caa3979661de8970c0cdf43de603c0b06355bc098c064`.

Example from the repository root:

```powershell
python -B Design-Source/Daragoth-Meadow/build_creek_water.py --base ../daragoth-development/meadow-whole-map/lighting-corrected/daragoth_meadow_batched.bsp --out ../daragoth-development/meadow-creek
python -B Development-Tests/test_meadow_creek.py --base ../daragoth-development/meadow-whole-map/lighting-corrected/daragoth_meadow_batched.bsp --bsp ../daragoth-development/meadow-creek/daragoth_meadow_creek.bsp --report-source ../daragoth-development/meadow-creek/creek-water-build-report.json --report ../daragoth-development/meadow-creek/independent-creek-static-qa.json
```

The independent checker validates preservation, float32 translated brush-hull
contents, touching seams, exact bank cross-sections, wet bridge-opening probes,
and dry bridge/approach probes. Its `--actual-c` mode also replays 135 bridge
floor traces through the engine's x86 C tracer. These checks pass. Forty-nine
bridge-opening points have a pre-existing missing rendered bed face despite
solid floor collision; the new water covers these points. Native waterlevel,
swimming, rendered seams, mounted bridge travel and region reload remain
separate acceptance checks. This document does not claim they passed until a
matching native receipt exists.
