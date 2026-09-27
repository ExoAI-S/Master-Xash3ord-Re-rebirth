"""List every entity in every MSR map whose key values reference the given map names.

Usage: python scan_links.py <maps_dir> edana thornlands
"""
import re
import struct
import sys
from pathlib import Path


def entity_lump(path: Path) -> str:
    data = path.read_bytes()
    if len(data) < 8:
        return ""
    ofs, ln = struct.unpack_from("<ii", data, 4)
    return data[ofs:ofs + ln].decode("latin-1", "replace")


def main() -> None:
    maps_dir = Path(sys.argv[1])
    names = {n.lower() for n in sys.argv[2:]}
    for bsp in sorted(maps_dir.glob("*.bsp")):
        for block in re.findall(r"\{([^{}]*)\}", entity_lump(bsp)):
            kv = re.findall(r'"([^"]*)"\s+"([^"]*)"', block)
            hits = [(k, v) for k, v in kv if v.lower() in names and k.lower() not in ("classname",)]
            if hits:
                d = dict(kv)
                print(f"{bsp.stem}: {d.get('classname')} targetname={d.get('targetname', '')} "
                      + " ".join(f"{k}={v}" for k, v in kv if k in ("destmap", "desttrans", "destname", "map", "landmark")))


if __name__ == "__main__":
    main()
