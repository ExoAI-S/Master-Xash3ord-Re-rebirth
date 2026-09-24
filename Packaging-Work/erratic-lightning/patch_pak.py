"""Replace Erratic Lightning's three MScript entries in the recovery PACK.

The release carries scripts.pak as a binary, so keep these authored script
overrides beside the patcher and refuse to modify an unfamiliar pack.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import zlib


HEADER = struct.Struct("<4sII")
ENTRY = struct.Struct("<256sII")
EXPECTED_COUNT = 2923
EXPECTED_PACK_SHA256 = "5168d4d04a6207bf48769f69eca9ddfb26209adbfe4a2366f6be93bcd7079d9b"
SCRIPT_ROOT = Path(__file__).resolve().parent
ORIGINAL_SHA256 = {
    "effects/sfx_lightning.script": "58c5d48c010631e1cdb5239f73a52dbf368c829aa1505404e52ee2a65042bad3",
    "items/magic_hand_lightning_weak.script": "4ebcc87a6a76e501bc2c186f23100e1614817aa5fafd623dddd8e768e4cc4d90",
    "items/magic_hand_lightning_weak_cl.script": "b6c20bba61e294d6632cb8f426ffe0ee2ca694618d9820fe95be579ef679bcfb",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_entries(blob: bytes) -> list[tuple[bytes, str, bytes]]:
    if len(blob) < HEADER.size:
        raise ValueError("PACK is too small")
    magic, directory_offset, count = HEADER.unpack_from(blob)
    if magic != b"PACK" or directory_offset != HEADER.size or count != EXPECTED_COUNT:
        raise ValueError("Expected the 2923-entry recovery scripts.pak")
    directory_end = directory_offset + count * ENTRY.size
    if directory_end > len(blob):
        raise ValueError("PACK directory is truncated")
    entries = []
    names = set()
    for index in range(count):
        raw_name, offset, size = ENTRY.unpack_from(blob, directory_offset + index * ENTRY.size)
        name = raw_name.split(b"\0", 1)[0].decode("latin1")
        if not name or name in names or offset < directory_end or offset + size > len(blob):
            raise ValueError(f"Invalid PACK entry {index}: {name!r}")
        names.add(name)
        entries.append((raw_name, name, blob[offset : offset + size]))
    return entries


def make_pack(entries: list[tuple[bytes, str, bytes]]) -> bytes:
    count = len(entries)
    data_offset = HEADER.size + count * ENTRY.size
    directory = bytearray()
    payload = bytearray()
    for raw_name, _, data in entries:
        directory += ENTRY.pack(raw_name, data_offset + len(payload), len(data))
        payload += data
    return HEADER.pack(b"PACK", HEADER.size, count) + directory + payload


def patch(pak: Path, manifest: Path | None, backup: Path | None) -> int:
    original = pak.read_bytes()
    entries = read_entries(original)
    replacements = {
        name: (SCRIPT_ROOT / name).read_bytes().replace(b"\r\n", b"\n")
        for name in ORIGINAL_SHA256
    }
    changed = set()
    output = []
    for raw_name, name, data in entries:
        if name in replacements:
            existing_hash = sha256(data)
            if existing_hash == ORIGINAL_SHA256[name]:
                data = replacements[name]
                changed.add(name)
            elif existing_hash != sha256(replacements[name]):
                raise ValueError(f"Unexpected contents in {name}; refusing to overwrite custom scripts")
        output.append((raw_name, name, data))
    if {name for name in ORIGINAL_SHA256 if name not in {entry[1] for entry in entries}}:
        raise ValueError("Recovery PACK is missing an Erratic Lightning script")
    if changed and sha256(original) != EXPECTED_PACK_SHA256:
        raise ValueError("Expected the unmodified September 13 recovery scripts.pak")
    new_pack = make_pack(output) if changed else original
    if len(read_entries(new_pack)) != EXPECTED_COUNT:
        raise ValueError("Patched PACK failed verification")
    crc = zlib.crc32(new_pack) & 0xFFFFFFFF

    new_manifest = None
    if manifest is not None:
        new_manifest = json.loads(manifest.read_text(encoding="utf-8-sig"))
        if "scripts_crc32" not in new_manifest:
            raise ValueError("FN content manifest has no scripts_crc32")
        new_manifest["scripts_crc32"] = crc

    if changed:
        if backup is not None:
            if backup.exists():
                raise FileExistsError(f"Backup already exists: {backup}")
            shutil.copy2(pak, backup)
        temporary = pak.with_name(pak.name + ".erratic-tmp")
        temporary.write_bytes(new_pack)
        os.replace(temporary, pak)
    if manifest is not None:
        temporary = manifest.with_name(manifest.name + ".erratic-tmp")
        temporary.write_text(json.dumps(new_manifest, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, manifest)
    print(f"{'Patched' if changed else 'Already patched'} {pak}; scripts CRC32 {crc}")
    return crc


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pak", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--backup", type=Path)
    args = parser.parse_args()
    patch(args.pak, args.manifest, args.backup)
