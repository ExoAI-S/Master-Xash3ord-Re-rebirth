"""Read and write GoldSrc BSP30 maps, including Xash3D's BSP30ext variant.

Every lump is decoded into plain Python lists so tools can rebuild a map
without losing data. BSP30ext adds an 'XASH' extra header after the standard
header; its main use here is allowing more than 32767 clipnodes, which the
Xash3D FWGS loader remaps into per-model 16-bit hulls.
"""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field
from pathlib import Path

HLBSP_VERSION = 30
IDEXTRAHEADER = struct.unpack("<i", b"XASH")[0]
EXTRA_VERSION = 4
EXTRA_LUMPS = 12

(LUMP_ENTITIES, LUMP_PLANES, LUMP_TEXTURES, LUMP_VERTEXES, LUMP_VISIBILITY, LUMP_NODES,
 LUMP_TEXINFO, LUMP_FACES, LUMP_LIGHTING, LUMP_CLIPNODES, LUMP_LEAFS, LUMP_MARKSURFACES,
 LUMP_EDGES, LUMP_SURFEDGES, LUMP_MODELS) = range(15)
HEADER_LUMPS = 15

CONTENTS_EMPTY = -1
CONTENTS_SOLID = -2

PLANE = struct.Struct("<4fi")
VERTEX = struct.Struct("<3f")
NODE = struct.Struct("<i2h3h3hHH")
TEXINFO = struct.Struct("<8fii")
FACE = struct.Struct("<Hhihh4Bi")
CLIPNODE16 = struct.Struct("<ihh")
CLIPNODE32 = struct.Struct("<iii")
LEAF = struct.Struct("<ii3h3hHH4B")
EDGE = struct.Struct("<HH")
MODEL = struct.Struct("<9f4i3i")
MIPTEX_HEADER = struct.Struct("<16sII4I")


@dataclass
class Plane:
    normal: tuple
    dist: float
    type: int


@dataclass
class Node:
    planenum: int
    children: list          # >= 0 node index, < 0 is -(leaf + 1)
    mins: tuple
    maxs: tuple
    firstface: int
    numfaces: int


@dataclass
class TexInfo:
    vecs: list              # [[sx, sy, sz, soff], [tx, ty, tz, toff]]
    miptex: int
    flags: int              # raw 32-bit value (flags | faceinfo << 16)


@dataclass
class Face:
    planenum: int
    side: int
    firstedge: int
    numedges: int
    texinfo: int
    styles: list
    lightofs: int


@dataclass
class ClipNode:
    planenum: int
    children: list          # >= 0 clipnode index, < 0 contents


@dataclass
class Leaf:
    contents: int
    visofs: int
    mins: tuple
    maxs: tuple
    firstmarksurface: int
    nummarksurfaces: int
    ambient: tuple


@dataclass
class Model:
    mins: tuple
    maxs: tuple
    origin: tuple
    headnode: list
    visleafs: int
    firstface: int
    numfaces: int


@dataclass
class MipTex:
    name: str
    raw: bytes | None       # complete miptex record (header + pixel data), None for a missing slot

    @property
    def external(self) -> bool:
        return self.raw is not None and struct.unpack_from("<I", self.raw, 24)[0] == 0


@dataclass
class Entity:
    pairs: list = field(default_factory=list)   # ordered [key, value] pairs

    def get(self, key, default=None):
        for k, v in self.pairs:
            if k == key:
                return v
        return default

    def set(self, key, value):
        for pair in self.pairs:
            if pair[0] == key:
                pair[1] = value
                return
        self.pairs.append([key, value])

    def remove(self, key):
        self.pairs = [p for p in self.pairs if p[0] != key]

    @property
    def classname(self):
        return self.get("classname", "")


def parse_entities(text: str) -> list[Entity]:
    ents = []
    for block in re.findall(r"\{([^{}]*)\}", text):
        ents.append(Entity([[k, v] for k, v in re.findall(r'"([^"]*)"\s+"([^"]*)"', block)]))
    return ents


def format_entities(ents: list[Entity]) -> bytes:
    out = []
    for e in ents:
        out.append("{\n")
        for k, v in e.pairs:
            out.append(f'"{k}" "{v}"\n')
        out.append("}\n")
    return "".join(out).encode("latin-1") + b"\0"


class BSP:
    def __init__(self):
        self.version = HLBSP_VERSION
        self.entities: list[Entity] = []
        self.planes: list[Plane] = []
        self.textures: list[MipTex] = []
        self.vertexes: list[tuple] = []
        self.visdata = b""
        self.nodes: list[Node] = []
        self.texinfo: list[TexInfo] = []
        self.faces: list[Face] = []
        self.lighting = b""
        self.clipnodes: list[ClipNode] = []
        self.leafs: list[Leaf] = []
        self.marksurfaces: list[int] = []
        self.edges: list[tuple] = []
        self.surfedges: list[int] = []
        self.models: list[Model] = []
        self.extra_lumps: dict[int, bytes] = {}
        self.bsp30ext = False

    # ------------------------------------------------------------------ reading
    @classmethod
    def load(cls, path: str | Path) -> "BSP":
        data = Path(path).read_bytes()
        if data[:4] == b"BSP2":
            return cls._load_bsp2(data)
        bsp = cls()
        bsp.version = struct.unpack_from("<i", data, 0)[0]
        if bsp.version != HLBSP_VERSION:
            raise ValueError(f"{path}: unsupported BSP version {bsp.version}")
        lumps = [struct.unpack_from("<ii", data, 4 + i * 8) for i in range(HEADER_LUMPS)]
        ext_ofs = 4 + HEADER_LUMPS * 8
        if len(data) > ext_ofs + 8 and struct.unpack_from("<i", data, ext_ofs)[0] == IDEXTRAHEADER:
            bsp.bsp30ext = True
            ver = struct.unpack_from("<i", data, ext_ofs + 4)[0]
            if ver != EXTRA_VERSION:
                raise ValueError(f"{path}: unsupported XASH extra header version {ver}")
            for i in range(EXTRA_LUMPS):
                o, l = struct.unpack_from("<ii", data, ext_ofs + 8 + i * 8)
                if l > 0:
                    bsp.extra_lumps[i] = data[o:o + l]

        def lump(i):
            o, l = lumps[i]
            return data[o:o + l]

        bsp.entities = parse_entities(lump(LUMP_ENTITIES).rstrip(b"\0").decode("latin-1"))
        bsp.planes = [Plane(tuple(p[0:3]), p[3], p[4]) for p in PLANE.iter_unpack(lump(LUMP_PLANES))]
        bsp.vertexes = [tuple(v) for v in VERTEX.iter_unpack(lump(LUMP_VERTEXES))]
        bsp.visdata = lump(LUMP_VISIBILITY)
        bsp.nodes = [Node(n[0], [n[1], n[2]], tuple(n[3:6]), tuple(n[6:9]), n[9], n[10])
                     for n in NODE.iter_unpack(lump(LUMP_NODES))]
        bsp.texinfo = [TexInfo([list(t[0:4]), list(t[4:8])], t[8], t[9])
                       for t in TEXINFO.iter_unpack(lump(LUMP_TEXINFO))]
        bsp.faces = [Face(f[0], f[1], f[2], f[3], f[4], list(f[5:9]), f[9])
                     for f in FACE.iter_unpack(lump(LUMP_FACES))]
        bsp.lighting = lump(LUMP_LIGHTING)
        raw_clip = lump(LUMP_CLIPNODES)
        if bsp.bsp30ext and (len(raw_clip) % 8 or len(raw_clip) // 12 >= 32767):
            bsp.clipnodes = [ClipNode(c[0], [c[1], c[2]]) for c in CLIPNODE32.iter_unpack(raw_clip)]
        else:
            bsp.clipnodes = [ClipNode(c[0], [c[1], c[2]]) for c in CLIPNODE16.iter_unpack(raw_clip)]
        bsp.leafs = [Leaf(l[0], l[1], tuple(l[2:5]), tuple(l[5:8]), l[8], l[9], tuple(l[10:14]))
                     for l in LEAF.iter_unpack(lump(LUMP_LEAFS))]
        bsp.marksurfaces = [m[0] for m in struct.iter_unpack("<H", lump(LUMP_MARKSURFACES))]
        bsp.edges = [tuple(e) for e in EDGE.iter_unpack(lump(LUMP_EDGES))]
        bsp.surfedges = [s[0] for s in struct.iter_unpack("<i", lump(LUMP_SURFEDGES))]
        bsp.models = [Model(tuple(m[0:3]), tuple(m[3:6]), tuple(m[6:9]), list(m[9:13]), m[13], m[14], m[15])
                      for m in MODEL.iter_unpack(lump(LUMP_MODELS))]
        bsp.textures = cls._parse_textures(lump(LUMP_TEXTURES))
        return bsp

    @classmethod
    def _load_bsp2(cls, data: bytes) -> "BSP":
        """Read a BSP2 file written by save_bsp2 (RGB lighting from BSPX; lightofs -> RGB bytes)."""
        bsp = cls()
        bsp.version = HLBSP_VERSION        # in-memory model is the same; save() picks the format
        lumps = [struct.unpack_from("<ii", data, 4 + i * 8) for i in range(HEADER_LUMPS)]

        def lump(i):
            o, l = lumps[i]
            return data[o:o + l]

        bsp.entities = parse_entities(lump(LUMP_ENTITIES).rstrip(b"\0").decode("latin-1"))
        bsp.planes = [Plane(tuple(p[0:3]), p[3], p[4]) for p in PLANE.iter_unpack(lump(LUMP_PLANES))]
        bsp.vertexes = [tuple(v) for v in VERTEX.iter_unpack(lump(LUMP_VERTEXES))]
        bsp.visdata = lump(LUMP_VISIBILITY)
        bsp.nodes = [Node(n[0], [n[1], n[2]], tuple(n[3:6]), tuple(n[6:9]), n[9], n[10])
                     for n in struct.iter_unpack("<iii3f3fii", lump(LUMP_NODES))]
        bsp.texinfo = [TexInfo([list(t[0:4]), list(t[4:8])], t[8], t[9])
                       for t in TEXINFO.iter_unpack(lump(LUMP_TEXINFO))]
        bsp.faces = [Face(f[0], f[1], f[2], f[3], f[4], list(f[5:9]), f[9] * 3 if f[9] >= 0 else -1)
                     for f in struct.iter_unpack("<iiiii4Bi", lump(LUMP_FACES))]
        bsp.clipnodes = [ClipNode(c[0], [c[1], c[2]]) for c in CLIPNODE32.iter_unpack(lump(LUMP_CLIPNODES))]
        bsp.leafs = [Leaf(l[0], l[1], tuple(l[2:5]), tuple(l[5:8]), l[8], l[9], tuple(l[10:14]))
                     for l in struct.iter_unpack("<ii3f3fii4B", lump(LUMP_LEAFS))]
        bsp.marksurfaces = [m[0] for m in struct.iter_unpack("<i", lump(LUMP_MARKSURFACES))]
        bsp.edges = [tuple(e) for e in struct.iter_unpack("<ii", lump(LUMP_EDGES))]
        bsp.surfedges = [s[0] for s in struct.iter_unpack("<i", lump(LUMP_SURFEDGES))]
        bsp.models = [Model(tuple(m[0:3]), tuple(m[3:6]), tuple(m[6:9]), list(m[9:13]), m[13], m[14], m[15])
                      for m in MODEL.iter_unpack(lump(LUMP_MODELS))]
        bsp.textures = cls._parse_textures(lump(LUMP_TEXTURES))
        end = (max(o + l for o, l in lumps) + 3) & ~3
        bid, count = struct.unpack_from("<ii", data, end)
        bsp.lighting = b""
        if bid == struct.unpack("<i", b"BSPX")[0]:
            for k in range(count):
                name = data[end + 8 + k * 32:end + 32 + k * 32].split(b"\0")[0]
                o, l = struct.unpack_from("<ii", data, end + 32 + k * 32)
                if name == b"RGBLIGHTING":
                    bsp.lighting = data[o:o + l]
        return bsp

    @staticmethod
    def _parse_textures(raw: bytes) -> list[MipTex]:
        if not raw:
            return []
        count = struct.unpack_from("<i", raw, 0)[0]
        offsets = struct.unpack_from(f"<{count}i", raw, 4)
        valid = sorted(o for o in offsets if o >= 0)
        out = []
        for ofs in offsets:
            if ofs < 0:
                out.append(MipTex("", None))
                continue
            later = [o for o in valid if o > ofs]
            end = later[0] if later else len(raw)
            rec = raw[ofs:end]
            name = rec[:16].split(b"\0", 1)[0].decode("latin-1")
            out.append(MipTex(name, rec))
        return out

    # ------------------------------------------------------------------ writing
    def texture_lump(self) -> bytes:
        count = len(self.textures)
        header = 4 + 4 * count
        offsets, blob = [], bytearray()
        for tex in self.textures:
            if tex.raw is None:
                offsets.append(-1)
                continue
            while (header + len(blob)) % 4:
                blob += b"\0"
            offsets.append(header + len(blob))
            blob += tex.raw
        return struct.pack(f"<i{count}i", count, *offsets) + bytes(blob)

    def save(self, path: str | Path, bsp30ext: bool | None = None) -> None:
        ext = self.bsp30ext if bsp30ext is None else bsp30ext
        big_clip = len(self.clipnodes) >= 32767
        if big_clip and not ext:
            raise ValueError("more than 32766 clipnodes requires BSP30ext")

        def pack_clip():
            if big_clip:
                return b"".join(CLIPNODE32.pack(c.planenum, *c.children) for c in self.clipnodes)
            return b"".join(CLIPNODE16.pack(c.planenum, *c.children) for c in self.clipnodes)

        lumps = [None] * HEADER_LUMPS
        lumps[LUMP_ENTITIES] = format_entities(self.entities)
        lumps[LUMP_PLANES] = b"".join(PLANE.pack(*p.normal, p.dist, p.type) for p in self.planes)
        lumps[LUMP_TEXTURES] = self.texture_lump()
        lumps[LUMP_VERTEXES] = b"".join(VERTEX.pack(*v) for v in self.vertexes)
        lumps[LUMP_VISIBILITY] = self.visdata
        lumps[LUMP_NODES] = b"".join(NODE.pack(n.planenum, *n.children, *n.mins, *n.maxs, n.firstface, n.numfaces)
                                     for n in self.nodes)
        lumps[LUMP_TEXINFO] = b"".join(TEXINFO.pack(*t.vecs[0], *t.vecs[1], t.miptex, t.flags) for t in self.texinfo)
        lumps[LUMP_FACES] = b"".join(FACE.pack(f.planenum, f.side, f.firstedge, f.numedges, f.texinfo,
                                               *f.styles, f.lightofs) for f in self.faces)
        lumps[LUMP_LIGHTING] = self.lighting
        lumps[LUMP_CLIPNODES] = pack_clip()
        lumps[LUMP_LEAFS] = b"".join(LEAF.pack(l.contents, l.visofs, *l.mins, *l.maxs, l.firstmarksurface,
                                               l.nummarksurfaces, *l.ambient) for l in self.leafs)
        lumps[LUMP_MARKSURFACES] = struct.pack(f"<{len(self.marksurfaces)}H", *self.marksurfaces)
        lumps[LUMP_EDGES] = b"".join(EDGE.pack(*e) for e in self.edges)
        lumps[LUMP_SURFEDGES] = struct.pack(f"<{len(self.surfedges)}i", *self.surfedges)
        lumps[LUMP_MODELS] = b"".join(MODEL.pack(*m.mins, *m.maxs, *m.origin, *m.headnode, m.visleafs,
                                                 m.firstface, m.numfaces) for m in self.models)

        header_size = 4 + HEADER_LUMPS * 8
        extra_size = 8 + EXTRA_LUMPS * 8 if ext else 0
        body = bytearray()
        directory = []
        cursor = header_size + extra_size
        # GoldSrc tools write planes before entities for their own reasons; keep the classic order.
        for i in range(HEADER_LUMPS):
            while (cursor + len(body)) % 4:
                body += b"\0"
            directory.append((cursor + len(body), len(lumps[i])))
            body += lumps[i]
        extra_dir = []
        if ext:
            for i in range(EXTRA_LUMPS):
                data = self.extra_lumps.get(i, b"")
                while (cursor + len(body)) % 4:
                    body += b"\0"
                extra_dir.append((cursor + len(body) if data else 0, len(data)))
                body += data
        out = bytearray(struct.pack("<i", self.version))
        for o, l in directory:
            out += struct.pack("<ii", o, l)
        if ext:
            out += struct.pack("<ii", IDEXTRAHEADER, EXTRA_VERSION)
            for o, l in extra_dir:
                out += struct.pack("<ii", o, l)
        out += body
        Path(path).write_bytes(bytes(out))


    # ------------------------------------------------------------------ BSP2
    def save_bsp2(self, path: str | Path, light_sizes: list[int]) -> dict:
        """Write the map as 32-bit 'BSP2' with Half-Life data.

        Xash3D FWGS reads BSP2 lighting as one sample per luxel, so the RGB
        lighting goes into a BSPX RGBLIGHTING lump exactly three times the size
        of a monochrome LIGHTING lump (mod_bmodel.c Mod_LoadLighting). Lighting
        is repacked face by face without gaps so the loader's sample-count
        heuristic sees exactly 1. light_sizes[i] is face i's lightmap size in
        RGB bytes (all styles).
        """
        rgb = bytearray()
        lightofs = []
        for face, size in zip(self.faces, light_sizes):
            if face.lightofs < 0 or size <= 0:
                lightofs.append(-1)
                continue
            lightofs.append(len(rgb) // 3)
            rgb += self.lighting[face.lightofs:face.lightofs + size]
        mono = bytes((rgb[i] * 77 + rgb[i + 1] * 150 + rgb[i + 2] * 29) >> 8 for i in range(0, len(rgb), 3))

        node32 = struct.Struct("<iii3f3fii")
        face32 = struct.Struct("<iiiii4Bi")
        leaf32 = struct.Struct("<ii3f3fii4B")
        lumps = [None] * HEADER_LUMPS
        lumps[LUMP_ENTITIES] = format_entities(self.entities)
        lumps[LUMP_PLANES] = b"".join(PLANE.pack(*p.normal, p.dist, p.type) for p in self.planes)
        lumps[LUMP_TEXTURES] = self.texture_lump()
        lumps[LUMP_VERTEXES] = b"".join(VERTEX.pack(*v) for v in self.vertexes)
        lumps[LUMP_VISIBILITY] = self.visdata
        lumps[LUMP_NODES] = b"".join(node32.pack(n.planenum, *n.children, *map(float, n.mins), *map(float, n.maxs),
                                                 n.firstface, n.numfaces) for n in self.nodes)
        lumps[LUMP_TEXINFO] = b"".join(TEXINFO.pack(*t.vecs[0], *t.vecs[1], t.miptex, t.flags) for t in self.texinfo)
        lumps[LUMP_FACES] = b"".join(face32.pack(f.planenum, f.side, f.firstedge, f.numedges, f.texinfo, *f.styles, lo)
                                     for f, lo in zip(self.faces, lightofs))
        lumps[LUMP_LIGHTING] = mono
        lumps[LUMP_CLIPNODES] = b"".join(CLIPNODE32.pack(c.planenum, *c.children) for c in self.clipnodes)
        lumps[LUMP_LEAFS] = b"".join(leaf32.pack(l.contents, l.visofs, *map(float, l.mins), *map(float, l.maxs),
                                                 l.firstmarksurface, l.nummarksurfaces, *l.ambient) for l in self.leafs)
        lumps[LUMP_MARKSURFACES] = struct.pack(f"<{len(self.marksurfaces)}i", *self.marksurfaces)
        lumps[LUMP_EDGES] = b"".join(struct.pack("<ii", *e) for e in self.edges)
        lumps[LUMP_SURFEDGES] = struct.pack(f"<{len(self.surfedges)}i", *self.surfedges)
        lumps[LUMP_MODELS] = b"".join(MODEL.pack(*m.mins, *m.maxs, *m.origin, *m.headnode, m.visleafs,
                                                 m.firstface, m.numfaces) for m in self.models)

        header_size = 4 + HEADER_LUMPS * 8
        body = bytearray()
        directory = []
        for i in range(HEADER_LUMPS):
            while (header_size + len(body)) % 4:
                body += b"\0"
            directory.append((header_size + len(body), len(lumps[i])))
            body += lumps[i]
        # BSPX directly at the 4-byte-aligned end of the last lump (Mod_FindBSPX)
        while (header_size + len(body)) % 4:
            body += b"\0"
        bspx_at = header_size + len(body)
        data_at = bspx_at + 8 + 32
        body += struct.pack("<ii", struct.unpack("<i", b"BSPX")[0], 1)
        body += b"RGBLIGHTING".ljust(24, b"\0") + struct.pack("<ii", data_at, len(rgb))
        body += rgb
        out = bytearray(b"BSP2")
        for o, l in directory:
            out += struct.pack("<ii", o, l)
        out += body
        Path(path).write_bytes(bytes(out))
        return {"rgb_bytes": len(rgb), "mono_bytes": len(mono), "file_bytes": len(out)}


# ---------------------------------------------------------------------- vis
def decompress_vis(data: bytes, ofs: int, numbytes: int) -> bytearray:
    out = bytearray()
    i = ofs
    while len(out) < numbytes:
        b = data[i]
        if b:
            out.append(b)
            i += 1
        else:
            out.extend(b"\0" * data[i + 1])
            i += 2
    return out[:numbytes]


def compress_vis(row: bytes) -> bytes:
    out = bytearray()
    i, n = 0, len(row)
    while i < n:
        if row[i]:
            out.append(row[i])
            i += 1
            continue
        run = 0
        while i < n and row[i] == 0 and run < 255:
            run += 1
            i += 1
        out += bytes((0, run))
    return bytes(out)


# ---------------------------------------------------------------------- hull queries
def hull_point_contents(bsp: BSP, headnode: int, point, hull: int) -> int:
    """Contents of a point in hull 0 (nodes/leafs) or hulls 1-3 (clipnodes)."""
    num = headnode
    if hull == 0:
        while num >= 0:
            node = bsp.nodes[num]
            p = bsp.planes[node.planenum]
            d = (point[p.type] - p.dist) if p.type < 3 else (
                sum(point[k] * p.normal[k] for k in range(3)) - p.dist)
            num = node.children[0] if d >= 0 else node.children[1]
        return bsp.leafs[-num - 1].contents
    while num >= 0:
        node = bsp.clipnodes[num]
        p = bsp.planes[node.planenum]
        d = (point[p.type] - p.dist) if p.type < 3 else (
            sum(point[k] * p.normal[k] for k in range(3)) - p.dist)
        num = node.children[0] if d >= 0 else node.children[1]
    return num


def count_tree(bsp: BSP, headnode: int, clip: bool) -> int:
    """Number of distinct nodes reachable from headnode (iterative)."""
    if headnode < 0:
        return 0
    seen, stack = set(), [headnode]
    items = bsp.clipnodes if clip else bsp.nodes
    while stack:
        n = stack.pop()
        if n < 0 or n in seen or n >= len(items):
            continue
        seen.add(n)
        stack.extend(items[n].children)
    return len(seen)
