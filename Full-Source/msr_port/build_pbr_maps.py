#!/usr/bin/env python3
"""Build conservative normal and PrimeXT gloss/ORM maps from a diffuse texture."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageFilter


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("diffuse", type=Path)
    parser.add_argument("normal", type=Path)
    parser.add_argument("gloss", type=Path)
    parser.add_argument("--strength", type=float, default=2.2)
    args = parser.parse_args()

    diffuse = Image.open(args.diffuse).convert("RGB")
    width, height = diffuse.size
    height_map = diffuse.convert("L").filter(ImageFilter.GaussianBlur(radius=max(1, width // 512)))
    source = height_map.load()

    normal = Image.new("RGB", diffuse.size)
    normal_pixels = normal.load()
    for y in range(height):
        previous_y = max(0, y - 1)
        next_y = min(height - 1, y + 1)
        for x in range(width):
            previous_x = max(0, x - 1)
            next_x = min(width - 1, x + 1)
            dx = (source[next_x, y] - source[previous_x, y]) / 255.0 * args.strength
            dy = (source[x, next_y] - source[x, previous_y]) / 255.0 * args.strength
            nx, ny, nz = -dx, -dy, 1.0
            length = math.sqrt(nx * nx + ny * ny + nz * nz)
            normal_pixels[x, y] = (
                round((nx / length * 0.5 + 0.5) * 255),
                round((ny / length * 0.5 + 0.5) * 255),
                round((nz / length * 0.5 + 0.5) * 255),
            )

    gloss = Image.new("RGBA", diffuse.size)
    gloss_pixels = gloss.load()
    diffuse_pixels = diffuse.load()
    for y in range(height):
        for x in range(width):
            normalized_x = x / max(1, width - 1)
            # The original shortsword sheet places the blade at the left,
            # wooden grip in the center, and guard/pommel islands at the right.
            metal = normalized_x < 0.23 or normalized_x > 0.74
            red, green, blue = diffuse_pixels[x, y]
            luminance = (red * 54 + green * 183 + blue * 19) // 256
            if max(red, green, blue) < 7:
                gloss_pixels[x, y] = (0, 0, 255, 0)
            elif metal:
                gloss_pixels[x, y] = (190 + luminance // 8, 235, 215, 220)
            else:
                gloss_pixels[x, y] = (65 + luminance // 10, 0, 225, 72)

    for path in (args.normal, args.gloss):
        path.parent.mkdir(parents=True, exist_ok=True)
    normal.save(args.normal, optimize=True)
    gloss.save(args.gloss, optimize=True)
    print(f"Wrote {args.normal} and {args.gloss} at {width}x{height}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
