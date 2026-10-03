# Daragoth scenery distance playtest — October 3, 2026

The local Daragoth preview now keeps full scenery nearby and gradually removes
distant decorative models. Terrain, buildings, players, enemies, horses, items,
collision and server encounter behavior are unaffected. No extra foliage was
added: existing near-player density is preserved.

Open **MSR - Daragoth Preview**. Distance fading is enabled by default. For an
in-game comparison, the console accepts:

```text
ms_scenery_distance 0   // original full-distance scenery
ms_scenery_distance 1   // default optimized view
ms_scenery_distance 1.5 // longer scenery distance
cl_showfps 1            // display gameplay FPS
ms_scenery_stats        // report per-category rendering decisions
```

Positive distance scales are limited to 0.5–2.0; zero disables fading. The setting
is saved by the client. The local launcher also accepts `-ShowFPS` for this test.

| Scenery | Fully visible through | Fully culled beyond |
| --- | ---: | ---: |
| Grass | 2400 | 4400 |
| Bushes | 4200 | 6500 |
| Rocks | 5000 | 7500 |
| Trees | 8000 | 12000 |

Distances are map units measured from the active render camera to the closest
point of each transformed model's bounds, not its origin. Broad grass sections
remain visible when their near edge is close. Between distances, smooth coverage
fading uses ordered stippling while preserving opaque depth and masked textures.
The screen-space pattern may be visible in the transition band; this playtest
needs feedback while walking and riding, especially on how noticeable fading is.

## Implementation and validation

The client applies an exact allowlist of authored plains foliage assets only to
normal, nonsolid, unattached static models. It reads the final camera inside the
studio draw callback, after view calculation, and preserves animation events.
It restores the OpenGL stipple and pixel unpack state after the scoped draw.
Unknown assets and malformed bounds remain visible.

Built x86 Debug. Standalone C++ policy tests passed for strict classification,
near/far boundaries, large bounds, scale changes, invalid values, monotonic
fading, all 65 coverage masks, and guarded mask writes. Independent source review
found no blocking issue. Native screenshots were inspected at the plains and
village viewpoints: close scenery, buildings and the terrain remained intact.
Water reflection and extended mounted traversal have not been visually verified.

At 1280×720, engine `timerefresh` results on the same candidate client were:

| Fixed position | Full distance | Optimized |
| --- | ---: | ---: |
| Plains (1000, 6000, settled ground), yaw 90 | 39.39–39.43 FPS | 84.62–88.27 FPS |
| Village (-2100, 5500, settled ground), yaw 25 | 46.84 FPS | 114.96 FPS |

These are a 128-view renderer throughput benchmark, not normal gameplay FPS or
a guarantee at other resolutions. The older binary measured 54.90–55.92 FPS at
the first point; the strongest comparison is enabled/disabled in the same new
binary. No resolution, texture quality or gameplay FPS ceiling was reduced.
Runtime diagnostics at the first point excluded 64 of 81 submitted grass
sections, 122 of 165 bushes, 49 of 65 rocks, and 55 of 174 trees from drawing.
Additional distant models remained in their fade bands.

## Local deployment and rollback

Only client.dll and its matching client.pdb were replaced in the two Daragoth
preview roots. Map, server, FN manifest and player profiles were not changed.
The previous client is backed up under the sibling lab directory:
`daragoth-development/backups/scenery-distance-20261003T121214Z/receipt.json`.
Close preview clients before restoring the four original files listed there.
This change has not been published or deployed to public realms.

- Client DLL SHA-256: `c943dfb3c35624471db0f7b5b7d9030d5b109282115c80f9ac908c66fdcf3fe2`
- Client PDB SHA-256: `df7ec3cdfc82be1c203939f7418424bc818dda91b4aeabce79ff8f2e42c77895`
- Local raw benchmark/build logs: `daragoth-development/scenery-distance/`
- Collected repository evidence: `Verification/Daragoth-Scenery/2026-10-03/`
