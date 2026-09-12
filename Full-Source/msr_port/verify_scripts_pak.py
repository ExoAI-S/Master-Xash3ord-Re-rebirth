"""Validate the MSR MScript PACK container without modifying it."""

from __future__ import annotations

import struct
import sys
from pathlib import Path


HEADER = struct.Struct("<4sII")
ENTRY = struct.Struct("<256sII")
EXPECTED_ENTRIES = 2923


def main(path: str) -> int:
    pak_path = Path(path)
    blob = pak_path.read_bytes()
    if len(blob) < HEADER.size:
        raise SystemExit(f"{pak_path}: file is too small for a PACK header")

    magic, directory_offset, count = HEADER.unpack_from(blob)
    if magic != b"PACK":
        raise SystemExit(f"{pak_path}: unexpected magic {magic!r}")
    if directory_offset != HEADER.size:
        raise SystemExit(
            f"{pak_path}: expected directory at {HEADER.size}, got {directory_offset}"
        )
    if count != EXPECTED_ENTRIES:
        raise SystemExit(
            f"{pak_path}: expected {EXPECTED_ENTRIES} entries, got {count}"
        )

    directory_end = directory_offset + count * ENTRY.size
    if directory_end > len(blob):
        raise SystemExit(f"{pak_path}: directory exceeds file size")

    names: set[bytes] = set()
    for index in range(count):
        name, data_offset, data_size = ENTRY.unpack_from(
            blob, directory_offset + index * ENTRY.size
        )
        name = name.split(b"\0", 1)[0]
        if not name:
            raise SystemExit(f"{pak_path}: entry {index} has an empty name")
        if name in names:
            raise SystemExit(f"{pak_path}: duplicate entry {name!r}")
        names.add(name)
        if data_offset < directory_end or data_offset + data_size > len(blob):
            raise SystemExit(f"{pak_path}: entry {name!r} points outside payload")

    required = {
        b"global.script",
        b"player/player.script",
        b"items/base_item_extras.script",
        b"edana/game_master.script",
        b"edana/raid_guard.script",
    }
    missing = sorted(required - names)
    if missing:
        raise SystemExit(f"{pak_path}: missing required scripts: {missing!r}")

    print(f"Validated {pak_path}: PACK with {count} unique script entries")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify_scripts_pak.py PATH")
    raise SystemExit(main(sys.argv[1]))
