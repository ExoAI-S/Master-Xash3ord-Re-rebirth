# First frozen geometry candidate

Candidate SHA-256: `54a4ca0d5b5b1e61b8d6c7ae8d69bb46247949fd07d00d850b52b330efb41329`.
CRC32: `162721740`. Size: 15,796,388 bytes. The generated BSP remains in isolated development scratch, outside the installed game and the frozen plains assets.

The continuous join uses world Y=3216. Original Daragoth stays at offset zero. New plains offset is `(1650.0473022166188,13216,2688)`. The new local road at Y=-10000 meets the original X=1528 road with floor Z=3072. The original northern Deralia brush transition is removed; the far northern trigger retains its original destination metadata, including the absence of `desttrans`. The candidate contains exactly one explicit global game master. The original ordinary creation spawn remains at `(-864,-3856,3200)`.

The build removes 218 original world faces and clips 77 straddling faces; it removes seven new world faces and clips 11. It repacks 61 cropped lightmaps. All 191 textures are embedded. The original 16-unit and new 64-unit sample grids are preserved. Structural checks find no node ordering or lightmap bounds errors.

Independent production C collision QA passes all four hulls: 24,000 original point contents checks and 104,516 contacts remain unchanged away from the join; 3,860 seam floor probes and 23,160 sweeps in both directions have no blockage or floor discontinuity. Actual `PM_WalkMove` replay passes 840 frames at speeds 320 and 520 over timestep range 1/120 to 0.1 seconds. The reproducible native audit is `Development-Tests/test_daragoth_expanded_collision.py`. These checks establish collision behavior; in-game rendering and gameplay remain separate checks.

Known visual work remains. Main northern grass and road X=1104..2432 meet Z=3072 exactly, but cropped hills away from the road lack vertical render caps. The worst visible cut top is Z=3442.67 at X=624..728, 370.67 units above the new field. Further west/east, original outside-world solid can be invisible when viewed from the expanded field. The old low sky ceiling also needs visual inspection. This first candidate should not be described as a finished landscape until caps and scenery make those edges sound.

The first conservative cross-PVS opens 533 original rows while new rows see 544 original leaves; 11 original leaf indices are asymmetric. A follow-up should union the two old visibility sets and use that same mask in both directions. The frozen first BSP stays unchanged until the next candidate is explicitly staged. `ms_region_unload_time 0` is required for this milestone; adjacency-aware preloading is deferred.

Native two-client testing crossed the join both ways without a level change or fade. Fresh character testing exposed an additional issue: although the original begin entity remained, new generic plains spawns competed with the original selection pool and both fresh characters started at the stable. The capped candidate removes every plains spawn and preserves only the exact original spawn pool. This first BSP remains historical geometry evidence, not the selected playable preview.
