# Artwork sources

World-Map contains the original Daragoth JPEG supplied for this project, its
atlas tile/pin manifest and the extracted map-transition graph. The source
image was supplied without an author or date; it is not newly authored artwork.
Its SHA-256 is 7a6d2e16907ea494f576bed00107520631010acf747ddd31656b42e8359791d5.
The runtime uses an aspect-preserving reduction split into sixteen1024px tiles.
Named-region coordinates were matched by hand and are approximate.

Shortswords contains editable Blender4.5 source designs and the UV-mapped game
geometry for the new regular and rusty shortswords. Replacement sword geometry
and procedural materials were authored for this project. The compiled model
banks also retain MSR hands, animations and other weapon data. Their fourteen
runtime asset hashes are recorded in package-manifest.json; the runtime files
are in Portable-Package/game/msr. Studio Blender renders and materials differ
from the game's indexed diffuse rendering. Optional normal/gloss maps require
renderer support and are not proof that such effects are active.

The original character model remains installed in this release. Separate male
model and other weapon experiments are not included as completed replacements.
