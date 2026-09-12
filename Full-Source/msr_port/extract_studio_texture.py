#!/usr/bin/env python3
"""Extract an indexed GoldSrc studio-model texture as a 24-bit TGA."""

from __future__ import annotations

import argparse
import binascii
import struct
import zlib
from pathlib import Path

STUDIO_IDENT = b"IDST"
STUDIO_VERSION = 10
TEXTURE_COUNT_OFFSET = 180
TEXTURE_INDEX_OFFSET = 184
TEXTURE_RECORD_SIZE = 80


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("texture")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    data = args.model.read_bytes()
    if data[:4] != STUDIO_IDENT or struct.unpack_from("<i", data, 4)[0] != STUDIO_VERSION:
        raise SystemExit("Not a GoldSrc version 10 studio model")

    count = struct.unpack_from("<i", data, TEXTURE_COUNT_OFFSET)[0]
    table = struct.unpack_from("<i", data, TEXTURE_INDEX_OFFSET)[0]
    requested = Path(args.texture).stem.casefold()

    for index in range(count):
        record = table + index * TEXTURE_RECORD_SIZE
        name = data[record : record + 64].split(b"\0", 1)[0].decode("latin-1")
        if Path(name).stem.casefold() != requested:
            continue

        width, height, pixels_at = struct.unpack_from("<iii", data, record + 68)
        pixel_count = width * height
        indices = data[pixels_at : pixels_at + pixel_count]
        palette = data[pixels_at + pixel_count : pixels_at + pixel_count + 768]
        if len(indices) != pixel_count or len(palette) != 768:
            raise SystemExit("Texture data extends beyond the model")

        rows = bytearray()
        for y in range(height):
            rows.append(0)  # PNG filter type: none
            for palette_index in indices[y * width : (y + 1) * width]:
                rows.extend(palette[palette_index * 3 : palette_index * 3 + 3])

        def chunk(kind: bytes, payload: bytes) -> bytes:
            checksum = binascii.crc32(kind + payload) & 0xFFFFFFFF
            return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", checksum)

        image = b"\x89PNG\r\n\x1a\n"
        image += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        image += chunk(b"IDAT", zlib.compress(bytes(rows), level=9))
        image += chunk(b"IEND", b"")

        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(image)
        print(f"Extracted {name} ({width}x{height}) to {args.output}")
        return 0

    raise SystemExit(f"Texture not found: {args.texture}")


if __name__ == "__main__":
    raise SystemExit(main())
