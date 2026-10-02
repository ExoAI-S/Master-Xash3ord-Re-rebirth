# Visible closure at the Daragoth-to-plains join

The continuous join at world Y3216 had 377 north-facing cap faces and no
south-facing caps. This left some cut solids visible through from the original
Daragoth side. The old cap builder also skipped the entire X1104..2432 portal
band, leaving a few cut solids uncovered beside the narrower road. Concrete
missing sections include X768/Z3440, facing south, and X1920/Z3120, facing north.

`build_join_caps.py` operates on the frozen creek candidate from
`build_creek_water.py`. It partitions both existing world render trees exactly
at the join. It selects only sections where one side is SOLID and the opposite
side is EMPTY or SKY, then subtracts all existing coplanar rendered coverage.
The result adds 90 faces: 74 facing south and 16 facing north. Small section
tiles bound texture extents; faces reuse the existing DPROCK mapping and ordinary
RGB style0 lighting. Existing sky closure remains in place.

The builder inserts these faces at the end of the contiguous world range and
remaps later submodel face references. The original two join visibility anchors
and each adjacent open leaf receive matching marksurfaces. Leaf and ancestor
render bounds expand to contain the new surfaces. No planes, node children,
leaf contents, collision clipnodes, model hull headnodes, visibility bytes,
texture records, texture mappings or entities change. Creek water and the
84 grass models are preserved. Changed render lumps are appended while the
existing file bytes remain intact outside their nine directory descriptors.

Example from the repository root:

```powershell
python -B Design-Source/Daragoth-Meadow/build_join_caps.py --base ../daragoth-development/meadow-creek/daragoth_meadow_creek.bsp --out ../daragoth-development/meadow-join-repair
```

The deterministic combined water/join candidate SHA-256 is
`827f22e886c679f44cdfe8584d339feae841e49b9f43e4ec2da3fb2949b26cf8`.
The join build report is `meadow-join-repair/join-caps-build-report.json` in the
private lab. `Development-Tests/test_meadow_join_caps.py` independently checks
preservation, face winding, lightmaps and directional interface coverage. The
final candidate passes 32,256 portal samples on a 16-unit grid, 39,585 broader
interface samples on a 64-unit grid, four known-gap regressions, and 270
actual-C standing road sweeps across the join. These finite samples do not
establish complete foot-by-foot walking coverage. Native before/after views,
culling and movement remain separate acceptance checks.
Only matching acceptance receipts authorize preview staging; building this
candidate does not itself change either private preview.
