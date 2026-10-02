# Whole-map meadow groundcover

This private Daragoth pass covers the continuous original valley, entrance join,
and expanded fields. It builds on the stablemaster/road/orchard checkpoint
`60c64c69`, whose compiled map SHA-256 is
`e14b54e89f7a5870944c3759a3e8eda4e5e4b4ef962856b5ffbe52fe06da7b06`.

The grass is shorter and irregular: 42 crossed-card tufts per patch, at most
23.66 units tall. The existing CC0 indexed blade bitmap is copied unchanged.
There are 840 patches across the fields and 80 in the original valley, distributed
across eligible sectors before adding density. Placement follows compiled
rendered grass surfaces and the actual narrow road, with clear approaches to
buildings, walker routes, trees, stable, river, ruins, and actor spawn positions.
Every compiled root is fitted and slightly buried; placements that cross terrain
creases or solid obstructions are rejected.

## Spatial models and lighting

One networked entity per patch overflowed Xash3D's 16,384-byte player snapshot
buffer despite being below the entity limit. The final builder bakes the same
920 placements into 84 spatial models with permanent bodyparts. This reduces
total map entities to 1,044, including all 960 original nongrass records.
Each submodel stays below the compiler and renderer budgets: at most 3,696
triangles, 3,696 source vertices, and 7,392 submitted vertices.

The stock renderer samples light at entity origin plus eight units in Z.
An arbitrary cell-center origin with median terrain height put 43 of the 84
lighting samples inside solid terrain. The corrected anchor uses the planted
patch nearest each cell center, with Z at its ground height plus 64 units.
An equal inverse translation of model vertices preserves visible world geometry
and bounds. All 84 lighting samples are empty and have a lightmapped meadow
floor below them. Grass retains masked, scene-lit flatshade flags (65), with
fullbright disabled.

## Sources and verification

- `build_meadow_groundcover.py` creates the short irregular patch from the
  existing CC0 source cards and bitmap.
- `meadow_surface.py` indexes upward compiled world faces for placement and
  independent rendered-surface checks.
- `build_meadow_polish.py` distributes and fits the 920 placements against the
  frozen base, source report, and continuous-join report.
- `build_meadow_batches.py` compiles spatial models with grounded lighting
  anchors and replaces only the BSP entity lump.
- `Development-Tests/test_meadow_surface.py` checks face orientation, polygon
  containment, texture filters, and stacked surfaces.
- `Development-Tests/test_meadow_polish.py` verifies the intermediate placement
  map and independent root contact/clearance.
- `Development-Tests/test_meadow_batches.py` independently replays every compiled
  vertex, normal, UV, root, bodypart, texture, and lighting anchor. Its `--actual-c`
  mode uses the engine's x86 C trace code.

The private lab is the sibling `daragoth-development/meadow-whole-map` directory.
Final assets are under `lighting-corrected`; failed candidates and native evidence
are retained separately. Each builder and checker exposes required input paths
through `--help`; outputs must remain separate from the installed game.

Final candidate SHA-256:
`7db33aa84ff9f032d1267e3d37d2795e959e414c262dcb896c83a3169c1e5570`.
Independent static and actual-C QA pass: all 154,560 root-floor traces, 920
standing patch-center floor traces, and 84 lighting-anchor floor traces have zero
failures. All 14 nonentity BSP lumps and ordered nongrass entity records are
unchanged. This preserves terrain, collision, lighting data, visibility, textures,
road, village, orchard, stablemaster, and horse behavior from the base checkpoint.
Native view/movement acceptance and final preview staging are recorded separately
in `Development-Tests/Reports/daragoth-whole-map-meadow-preview-20261001.json`.

The subsequent mount checkpoint `81e60fe6` updates the Debug server DLL while
preserving this map. Its 30 lifecycle checks and nine additional native checks
on the combined meadow preview pass; see
`Development-Tests/Reports/daragoth-mount-lifecycle-20261001.json`. The grass
receipt retains the original core hashes used for its own 22-view native run and
records the later mount integration separately.

These are private development assets. The inherited Edana tree's upstream
license remains unverified; this pass does not authorize public distribution.
