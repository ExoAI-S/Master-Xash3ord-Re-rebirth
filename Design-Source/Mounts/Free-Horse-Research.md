# Free textured horse research — September 30, 2026

The recommended visual candidate is **Lyndon Daniels' horse, with ChadM's rig**.
The [original author listing](https://opengameart.org/content/realtime-ranchers-3d-model-pack)
and [rig derivative](https://opengameart.org/content/rigged-horse) both identify
their license as CC0. The original author provides 2K textures. The downloaded
rigged Blender file has SHA-256
`9cca670b93a74d50e89263e50d55ab035a6c46aa7d2b21e354bdac6987037f4a`.

Read-only Blender inspection found 14,986 triangles and 19 bones. The body is
skinned, but the mane, tail and eyes have no skin weights or parent attachment.
There are no animation Actions or NLA tracks. Neutral private previews use the
asset's own diffuse textures with reconstructed shaders; the downloaded source
was not modified. This is a conversion candidate, not an installed mount.

Before integration, attach/weight the remaining meshes, reduce unsupported
vertex influences, author or correctly retarget idle/walk/gallop animations,
and make an original saddle. Export evaluated SMD/QC, optimize or split geometry
for the actual client/model compiler, and test indexed diffuse textures and
masked hair in the game renderer. The current server expects sequence indices
0/1/2 for idle/walk/gallop and a +X forward axis. Rider alignment, seat attachment
and performance need native multiplayer verification.

Other candidates:

| Asset | Evidence and suitability |
| --- | --- |
| [Quaternius original Farm Animals](https://opengameart.org/content/lowpoly-animated-farm-animal-pack) | Original author's 2018 download includes CC0 License.txt. Inspected horse has 690 triangles, 28 bones and actual idle/walk/run Actions. Useful animated fallback; its color-only style is simpler than the requested textured upgrade. |
| [Amir's itch.io horse pack](https://ahmedamirdev.itch.io/amir-low-poly-horses-pack) | Free tier advertises four stylized horses and idle/walk/run. Personal/commercial game use is advertised, but explicit source modification/redistribution rights appear in the paid Source tier. Obtain clarification before placing converted free-tier model source in an open repository. |
| [chi3dmodel textured horse](https://sketchfab.com/3d-models/free-to-use-low-poly-horse-527c570af430404ba8458d473db8cc20) | Primary listing describes a 7.7K-triangle, saddle-equipped horse under CC Attribution with an imperfect posing rig. The download, embedded license version and locomotion animations remain unverified. |

Private downloads, rendered previews and full inspection evidence remain in the
development lab. This research adds no external model files or game assets to
the public repository. Preserve author and license provenance when converting
the recommended CC0 candidate.
