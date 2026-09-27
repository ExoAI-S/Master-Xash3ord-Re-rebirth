"""Convert a BSP30/BSP30ext world into 32-bit BSP2 (Xash3D FWGS QBSP2) with RGB lighting in BSPX.

Usage: python convert_bsp2.py <in.bsp> <out.bsp>

BSP2 lifts the 16-bit index limits (65536 vertexes/faces/planes/marksurfaces,
32767 nodes/leafs/texinfo, 32767 clipnodes per hull). The output is read back
and every face's RGB lightmap is compared with the source.
"""
import struct
import sys
from pathlib import Path

from bsp30 import BSP
from merge_world import face_extents


def light_size(bsp: BSP, face) -> int:
    if face.lightofs < 0 or bsp.texinfo[face.texinfo].flags & 1:
        return 0
    (smin, smax), (tmin, tmax) = face_extents(bsp, face)
    styles = sum(1 for s in face.styles if s != 255)
    return (smax - smin + 1) * (tmax - tmin + 1) * styles * 3


def read_back(path: Path, src: BSP, sizes: list[int]) -> dict:
    data = path.read_bytes()
    if data[:4] != b"BSP2":
        raise ValueError("not a BSP2 file")
    lumps = [struct.unpack_from("<ii", data, 4 + i * 8) for i in range(15)]
    fo, fl = lumps[7]
    faces = [struct.unpack_from("<iiiii4Bi", data, fo + i * 28) for i in range(fl // 28)]
    end = max(o + l for o, l in lumps)
    end = (end + 3) & ~3
    bid, n = struct.unpack_from("<ii", data, end)
    name = data[end + 8:end + 32].split(b"\0")[0]
    rofs, rlen = struct.unpack_from("<ii", data, end + 32)
    if bid != struct.unpack("<i", b"BSPX")[0] or name != b"RGBLIGHTING":
        raise ValueError("BSPX RGBLIGHTING lump not found where the engine looks for it")
    if rlen != lumps[8][1] * 3:
        raise ValueError("RGBLIGHTING must be exactly 3x the LIGHTING lump")
    rgb = data[rofs:rofs + rlen]
    mismatch = 0
    for i, (f, size) in enumerate(zip(faces, sizes)):
        lo = f[-1]
        if size == 0:
            continue
        a = src.lighting[src.faces[i].lightofs:src.faces[i].lightofs + size]
        b = rgb[lo * 3:lo * 3 + size]
        if a != b:
            mismatch += 1
    counts = {name: lumps[idx][1] // sz for name, idx, sz in
              [("nodes", 5, 44), ("faces", 7, 28), ("clipnodes", 9, 12), ("leafs", 10, 44),
               ("marksurfaces", 11, 4), ("edges", 12, 8)]}
    return {"faces_checked": sum(1 for s in sizes if s), "light_mismatch": mismatch,
            "bspx_at": end, "counts": counts}


def main():
    src_path, out_path = Path(sys.argv[1]), Path(sys.argv[2])
    bsp = BSP.load(src_path)
    sizes = [light_size(bsp, f) for f in bsp.faces]
    info = bsp.save_bsp2(out_path, sizes)
    check = read_back(out_path, bsp, sizes)
    print({**info, **check})
    if check["light_mismatch"]:
        raise SystemExit("lighting mismatch")


if __name__ == "__main__":
    main()
