from __future__ import annotations

import argparse
import struct
from pathlib import Path


HEADER = struct.Struct("<4sII")
ENTRY_SIZE = 264
NAME_SIZE = 256
TARGET = "items/base_item_extras.script"
BEFORE = b"{ game_spawn\ncallevent 0.1 vanish_item \n}"
AFTER = b"{ game_spawn\nif game.serverside\ncallevent 0.1 vanish_item \n}"


def patch_pak(path: Path) -> None:
    blob = path.read_bytes()
    magic, directory_offset, count = HEADER.unpack_from(blob)
    if magic != b"PACK" or directory_offset != HEADER.size:
        raise RuntimeError("Unsupported scripts.pak format")

    entries: list[tuple[bytes, bytes]] = []
    found = False
    for index in range(count):
        entry_offset = directory_offset + index * ENTRY_SIZE
        raw_name = blob[entry_offset : entry_offset + NAME_SIZE]
        name = raw_name.split(b"\0", 1)[0].decode("latin1")
        data_offset, data_size = struct.unpack_from("<II", blob, entry_offset + NAME_SIZE)
        data = blob[data_offset : data_offset + data_size]
        if name == TARGET:
            if data.count(BEFORE) != 1:
                if data.count(AFTER) == 1:
                    print(f"{TARGET} is already patched")
                    return
                raise RuntimeError(f"Expected server-only guard site was not found in {TARGET}")
            data = data.replace(BEFORE, AFTER, 1)
            found = True
        entries.append((raw_name, data))

    if not found:
        raise RuntimeError(f"{TARGET} is missing from scripts.pak")

    data_offset = directory_offset + count * ENTRY_SIZE
    directory = bytearray()
    payload = bytearray()
    for raw_name, data in entries:
        directory.extend(raw_name)
        directory.extend(struct.pack("<II", data_offset + len(payload), len(data)))
        payload.extend(data)

    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_bytes(HEADER.pack(b"PACK", directory_offset, count) + directory + payload)
    temporary.replace(path)
    print(f"Patched {TARGET} in {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Guard the server-only vanish_item script event")
    parser.add_argument("pak", type=Path)
    patch_pak(parser.parse_args().pak)
