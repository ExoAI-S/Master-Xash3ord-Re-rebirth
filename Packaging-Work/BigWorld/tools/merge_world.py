"""Compose several compiled GoldSrc maps into one BSP30ext "world" map.

The maps are merged at the compiled-BSP level, so every region keeps its
original geometry, lightmaps, visibility and collision hulls exactly. Each
extra region's world model is translated by an offset; its brush entities keep
their local geometry and receive the offset through their "origin" key.
Regions are joined under new axis-aligned root nodes/clipnodes placed in the
empty gap between them, and PVS rows are rebuilt so no region sees another.

Usage: python merge_world.py <config.json>
"""
from __future__ import annotations

import copy
import json
import math
import struct
import sys
from pathlib import Path

from bsp30 import (BSP, ClipNode, Entity, Face, Leaf, Model, Node, Plane, TexInfo, compress_vis,
                   decompress_vis, hull_point_contents)

sys.setrecursionlimit(20000)
F32 = struct.Struct("<f")


def f32(x: float) -> float:
    return F32.unpack(F32.pack(x))[0]


# ---------------------------------------------------------------------------
# engine-exact lightmap extents (Xash3D FWGS Mod_CalcSurfaceExtents)
# ---------------------------------------------------------------------------
def face_extents(bsp: BSP, face: Face, sample_size: int = 16):
    tex = bsp.texinfo[face.texinfo]
    mins = [999999.0, 999999.0]
    maxs = [-999999.0, -999999.0]
    for i in range(face.numedges):
        e = bsp.surfedges[face.firstedge + i]
        v = bsp.vertexes[bsp.edges[e][0]] if e >= 0 else bsp.vertexes[bsp.edges[-e][1]]
        for j in range(2):
            vec = tex.vecs[j]
            val = f32(float(v[0]) * vec[0] + float(v[1]) * vec[1] + float(v[2]) * vec[2] + vec[3])
            mins[j] = min(val, mins[j])
            maxs[j] = max(val, maxs[j])
    out = []
    for j in range(2):
        bmin = math.floor(f32(mins[j] / sample_size))
        bmax = math.ceil(f32(maxs[j] / sample_size))
        out.append((bmin, bmax))
    return tuple(out)


# ---------------------------------------------------------------------------
class RegionSource:
    """One input map and how it is placed in the world."""

    def __init__(self, cfg: dict, base: Path):
        self.name = cfg["name"]
        self.path = (base / cfg["bsp"]).resolve()
        self.bsp = BSP.load(self.path)
        self.offset = tuple(float(x) for x in cfg.get("offset", (0, 0, 0)))
        self.rename_prefix = cfg.get("rename_prefix", self.name[:3] + "_")
        self.cfg = cfg
        b = self.bsp
        w = b.models[0]
        self.world_faces = set(range(w.firstface, w.firstface + w.numfaces))
        self.world_nodes = self._reach(w.headnode[0], b.nodes)
        self.world_clip = set()
        for h in range(1, 4):
            self.world_clip |= self._reach(w.headnode[h], b.clipnodes)
        self.visleafs = w.visleafs

    @staticmethod
    def _reach(head, items):
        seen, stack = set(), [head]
        while stack:
            n = stack.pop()
            if n < 0 or n in seen or n >= len(items):
                continue
            seen.add(n)
            stack.extend(items[n].children)
        return seen

    def shifted(self, point):
        return tuple(point[k] + self.offset[k] for k in range(3))


DECOR_SKINS = {None, "", "0", "-1"}   # func_illusionary skin = contents; -1 is CONTENTS_EMPTY


class WorldBuilder:
    def __init__(self, regions: list[RegionSource], stack_order: list[int] | None = None):
        self.regions = regions
        self.stack_order = stack_order or list(range(len(regions)))
        # Non-solid decoration (func_illusionary with empty contents) is drawn from its
        # face range and never traced, so its node tree can be replaced by a stub to
        # stay under the 32767-node limit of 16-bit node children.
        self.decor_models = set()
        self.pruned_leaves = set()
        for r, reg in enumerate(regions):
            if not reg.cfg.get("prune_decor"):
                continue
            users = {}
            for e in reg.bsp.entities:
                m = e.get("model") or ""
                if m.startswith("*"):
                    users.setdefault(int(m[1:]), []).append(e)
            for mi, ents in users.items():
                if all(e.classname == "func_illusionary" and e.get("skin") in DECOR_SKINS for e in ents):
                    self.decor_models.add((r, mi))
                    stack = [reg.bsp.models[mi].headnode[0]]
                    while stack:
                        n = stack.pop()
                        if n < 0:
                            if n != -1:
                                self.pruned_leaves.add((r, -n - 1))
                            continue
                        stack.extend(reg.bsp.nodes[n].children)
        self.out = BSP()
        self.out.bsp30ext = True
        self.plane_map = {}
        self.vert_map = {}
        self.edge_map = {}
        self.texinfo_map = {}
        self.tex_map = {}          # (region idx, miptex idx) -> out miptex idx
        self.face_map = {}         # (region idx, face idx) -> out face idx
        self.node_map = {}
        self.clip_map = {}
        self.leaf_map = {}         # (region idx, leaf idx) -> out leaf idx
        self.model_map = {}        # (region idx, model idx) -> out model idx
        self.light_base = {}
        self.report = {"renamed_textures": {}, "renamed_targets": {}, "restyled_lights": {},
                       "texinfo_adjustments": 0}

    # ---------------------------------------------------------------- primitives
    def plane(self, r: int, idx: int, shift: bool) -> int:
        key = (r, idx, shift)
        if key not in self.plane_map:
            p = self.regions[r].bsp.planes[idx]
            dist = p.dist
            if shift:
                off = self.regions[r].offset
                dist = f32(p.dist + sum(p.normal[k] * off[k] for k in range(3)))
            self.plane_map[key] = len(self.out.planes)
            self.out.planes.append(Plane(p.normal, dist, p.type))
        return self.plane_map[key]

    def new_plane(self, axis: int, dist: float) -> int:
        normal = [0.0, 0.0, 0.0]
        normal[axis] = 1.0
        self.out.planes.append(Plane(tuple(normal), float(dist), axis))
        return len(self.out.planes) - 1

    def vertex(self, r: int, idx: int, shift: bool) -> int:
        key = (r, idx, shift)
        if key not in self.vert_map:
            v = self.regions[r].bsp.vertexes[idx]
            if shift:
                v = tuple(f32(c) for c in self.regions[r].shifted(v))
            self.vert_map[key] = len(self.out.vertexes)
            self.out.vertexes.append(v)
        return self.vert_map[key]

    def edge(self, r: int, idx: int, shift: bool) -> int:
        key = (r, idx, shift)
        if key not in self.edge_map:
            a, b = self.regions[r].bsp.edges[idx]
            self.edge_map[key] = len(self.out.edges)
            self.out.edges.append((self.vertex(r, a, shift), self.vertex(r, b, shift)))
        return self.edge_map[key]

    def texinfo(self, r: int, idx: int, shift: bool) -> int:
        key = (r, idx, shift)
        if key not in self.texinfo_map:
            t = self.regions[r].bsp.texinfo[idx]
            vecs = [list(t.vecs[0]), list(t.vecs[1])]
            if shift:
                off = self.regions[r].offset
                for j in range(2):
                    vecs[j][3] = f32(vecs[j][3] - sum(vecs[j][k] * off[k] for k in range(3)))
            self.texinfo_map[key] = len(self.out.texinfo)
            self.out.texinfo.append(TexInfo(vecs, self.tex_map[(r, t.miptex)], t.flags))
        return self.texinfo_map[key]

    # ---------------------------------------------------------------- textures
    def merge_textures(self):
        by_name = {}
        for r, reg in enumerate(self.regions):
            for i, tex in enumerate(reg.bsp.textures):
                if tex.raw is None:
                    self.tex_map[(r, i)] = len(self.out.textures)
                    self.out.textures.append(copy.copy(tex))
                    continue
                key = tex.name.lower()
                if key in by_name:
                    existing = self.out.textures[by_name[key]]
                    if existing.raw.rstrip(b"\0") == tex.raw.rstrip(b"\0"):
                        self.tex_map[(r, i)] = by_name[key]
                        continue
                    new_name = self.unique_texture_name(tex.name, reg.rename_prefix, by_name)
                    raw = new_name.encode("latin-1").ljust(16, b"\0") + tex.raw[16:]
                    self.report["renamed_textures"][f"{reg.name}:{tex.name}"] = new_name
                    tex = type(tex)(new_name, raw)
                    key = new_name.lower()
                by_name[key] = len(self.out.textures)
                self.tex_map[(r, i)] = len(self.out.textures)
                self.out.textures.append(tex)

    @staticmethod
    def unique_texture_name(name, prefix, taken):
        if name[:1] in "+-":
            # animation/random-tiling frames must be renamed as a whole sequence
            raise ValueError(f"conflicting animated texture {name} needs a sequence-aware rename")
        special = name[0] if name[0] in "{!~" else ""
        stem = name[len(special):]
        tag = prefix.rstrip("_")[:2]
        for n in range(1, 100):
            candidate = (special + stem)[: 15 - len(tag) - (1 if n > 1 else 0)] + tag + (str(n) if n > 1 else "")
            candidate = candidate[:15]
            if candidate.lower() not in taken:
                return candidate
        raise ValueError(f"cannot rename texture {name}")

    # ---------------------------------------------------------------- faces
    def face(self, r: int, idx: int, shift: bool, style_map: dict) -> int:
        key = (r, idx)
        if key in self.face_map:
            return self.face_map[key]
        src = self.regions[r].bsp
        f = src.faces[idx]
        first = len(self.out.surfedges)
        for i in range(f.numedges):
            e = src.surfedges[f.firstedge + i]
            ne = self.edge(r, abs(e), shift)
            self.out.surfedges.append(ne if e >= 0 else -ne)
        styles = [style_map.get(s, s) if s != 255 else 255 for s in f.styles]
        lightofs = f.lightofs if f.lightofs < 0 else f.lightofs + self.light_base[r]
        nf = Face(self.plane(r, f.planenum, shift), f.side, first, f.numedges,
                  self.texinfo(r, f.texinfo, shift), styles, lightofs)
        self.face_map[key] = len(self.out.faces)
        self.out.faces.append(nf)
        return self.face_map[key]

    # ---------------------------------------------------------------- trees
    def node(self, r: int, idx: int, shift: bool) -> int:
        key = (r, idx)
        if key in self.node_map:
            return self.node_map[key]
        src = self.regions[r].bsp
        n = src.nodes[idx]
        out_idx = len(self.out.nodes)
        self.node_map[key] = out_idx
        self.out.nodes.append(None)
        children = []
        for c in n.children:
            if c >= 0:
                children.append(self.node(r, c, shift))
            else:
                children.append(-(self.leaf_map[(r, -c - 1)]) - 1)
        mins, maxs = n.mins, n.maxs
        if shift:
            mins = self.shift_short(r, mins)
            maxs = self.shift_short(r, maxs)
        firstface = self.face_map[(r, n.firstface)] if n.numfaces else 0
        # node face ranges must stay contiguous in the output
        for k in range(n.numfaces):
            assert self.face_map[(r, n.firstface + k)] == firstface + k, "node face range split"
        self.out.nodes[out_idx] = Node(self.plane(r, n.planenum, shift), children, mins, maxs,
                                       firstface, n.numfaces)
        return out_idx

    def stub_node(self, r: int, idx: int) -> int:
        """One solid node standing in for a pruned decoration tree (keeps plane and bounds)."""
        n = self.regions[r].bsp.nodes[idx]
        self.out.nodes.append(Node(self.plane(r, n.planenum, False), [-1, -1], n.mins, n.maxs, 0, 0))
        return len(self.out.nodes) - 1

    def shift_short(self, r, vec):
        off = self.regions[r].offset
        out = []
        for k in range(3):
            v = int(round(vec[k] + off[k]))
            if not -32768 <= v <= 32767:
                raise ValueError("shifted bbox exceeds 16-bit range")
            out.append(v)
        return tuple(out)

    def clipnode(self, r: int, idx: int, shift: bool) -> int:
        key = (r, idx)
        if key in self.clip_map:
            return self.clip_map[key]
        src = self.regions[r].bsp
        c = src.clipnodes[idx]
        out_idx = len(self.out.clipnodes)
        self.clip_map[key] = out_idx
        self.out.clipnodes.append(None)
        children = [self.clipnode(r, ch, shift) if ch >= 0 else ch for ch in c.children]
        self.out.clipnodes[out_idx] = ClipNode(self.plane(r, c.planenum, shift), children)
        return out_idx

    # ---------------------------------------------------------------- build
    def build(self, split_axis: int, split_dist: float):
        regions = self.regions
        out = self.out
        self.merge_textures()

        # lighting: concatenate
        blob = bytearray()
        for r, reg in enumerate(regions):
            self.light_base[r] = len(blob)
            blob += reg.bsp.lighting
        out.lighting = bytes(blob)

        style_maps = [reg.cfg.get("_style_map", {}) for reg in regions]

        # faces: world faces of every region first (keeps world range contiguous), then submodels
        for r, reg in enumerate(regions):
            w = reg.bsp.models[0]
            for i in range(w.firstface, w.firstface + w.numfaces):
                self.face(r, i, reg.offset != (0.0, 0.0, 0.0), style_maps[r])
        world_face_count = len(out.faces)
        for r, reg in enumerate(regions):
            for m in reg.bsp.models[1:]:
                for i in range(m.firstface, m.firstface + m.numfaces):
                    self.face(r, i, False, style_maps[r])
        missing = [(r, i) for r, reg in enumerate(regions) for i in range(len(reg.bsp.faces))
                   if (r, i) not in self.face_map]
        if missing:
            raise ValueError(f"{len(missing)} faces are not owned by any model")

        # leaves: shared solid leaf 0, world leaves of each region, then submodel leaves
        out.leafs.append(copy.copy(regions[0].bsp.leafs[0]))
        for r in range(len(regions)):
            self.leaf_map[(r, 0)] = 0
        for r, reg in enumerate(regions):
            for i in range(1, reg.visleafs + 1):
                self.leaf_map[(r, i)] = len(out.leafs)
                out.leafs.append(None)
        total_visleafs = len(out.leafs) - 1
        for r, reg in enumerate(regions):
            for i in range(reg.visleafs + 1, len(reg.bsp.leafs)):
                self.leaf_map[(r, i)] = len(out.leafs)
                out.leafs.append(None)
        # fill leaves with marksurfaces in output order
        for (r, i), li in sorted(self.leaf_map.items(), key=lambda kv: kv[1]):
            if li == 0 and r > 0:
                continue
            src_leaf = regions[r].bsp.leafs[i]
            first = len(out.marksurfaces)
            count = 0 if (r, i) in self.pruned_leaves else src_leaf.nummarksurfaces
            for k in range(count):
                out.marksurfaces.append(self.face_map[(r, regions[r].bsp.marksurfaces[src_leaf.firstmarksurface + k])])
            is_world = 1 <= i <= regions[r].visleafs
            shift = is_world and regions[r].offset != (0.0, 0.0, 0.0)
            mins = self.shift_short(r, src_leaf.mins) if shift else src_leaf.mins
            maxs = self.shift_short(r, src_leaf.maxs) if shift else src_leaf.maxs
            out.leafs[li] = Leaf(src_leaf.contents, src_leaf.visofs, mins, maxs, first,
                                 count, src_leaf.ambient)

        # node trees and clip hulls. Regions are stacked along one axis and
        # joined by a chain of split nodes: split k sends everything above
        # split_dists[k] to region k and the rest down the chain. The engine
        # rejects a child index lower than its hull's first node
        # (PM_RecursiveHullCheck "bad node number"), so the joining nodes take
        # the first slots and every subtree follows in preorder, exactly like
        # compiler output.
        order = self.stack_order          # region indices, positive side of each split first
        # split_dist: list of distances along split_axis, or list of (axis, dist) pairs
        splits = [(split_axis, d) if not isinstance(d, (list, tuple)) else (int(d[0]), float(d[1]))
                  for d in split_dist]
        if len(splits) != len(order) - 1:
            raise ValueError("need one split plane between each pair of stacked regions")
        n_joins = len(splits)
        out.nodes.extend([None] * n_joins)
        out.clipnodes.extend([None] * (3 * n_joins))
        heads = {}
        for r, reg in enumerate(regions):
            shift = reg.offset != (0.0, 0.0, 0.0)
            w = reg.bsp.models[0]
            h0 = self.node(r, w.headnode[0], shift)
            hc = [self.clipnode(r, w.headnode[h], shift) if w.headnode[h] >= 0 else w.headnode[h]
                  for h in range(1, 4)]
            heads[r] = (h0, hc)
        for k in range(n_joins):
            region_above = order[k]
            plane = self.new_plane(splits[k][0], splits[k][1])
            below_node = k + 1 if k + 1 < n_joins else heads[order[-1]][0]
            below_clip = [(3 * (k + 1) + h) if k + 1 < n_joins else heads[order[-1]][1][h] for h in range(3)]
            members = [heads[r][0] for r in order[k:]]
            mins = tuple(min(out.nodes[n].mins[a] for n in members) for a in range(3))
            maxs = tuple(max(out.nodes[n].maxs[a] for n in members) for a in range(3))
            out.nodes[k] = Node(plane, [heads[region_above][0], below_node], mins, maxs, 0, 0)
            for h in range(3):
                out.clipnodes[3 * k + h] = ClipNode(plane, [heads[region_above][1][h], below_clip[h]])
        root = 0
        clip_roots = [0, 1, 2]

        # submodels
        world_mins = [min(reg.bsp.models[0].mins[k] + reg.offset[k] for reg in regions) for k in range(3)]
        world_maxs = [max(reg.bsp.models[0].maxs[k] + reg.offset[k] for reg in regions) for k in range(3)]
        out.models.append(Model(tuple(world_mins), tuple(world_maxs), (0.0, 0.0, 0.0),
                                [root] + clip_roots, total_visleafs, 0, world_face_count))
        for r, reg in enumerate(regions):
            self.model_map[(r, 0)] = 0
            for mi, m in enumerate(reg.bsp.models[1:], 1):
                if (r, mi) in self.decor_models:
                    h0 = self.stub_node(r, m.headnode[0])
                else:
                    h0 = self.node(r, m.headnode[0], False)
                hc = []
                for h in range(1, 4):
                    hn = m.headnode[h]
                    if hn < 0 or hn >= len(reg.bsp.clipnodes):
                        hc.append(-1)
                    else:
                        hc.append(self.clipnode(r, hn, False))
                first = self.face_map[(r, m.firstface)] if m.numfaces else 0
                for k in range(m.numfaces):
                    assert self.face_map[(r, m.firstface + k)] == first + k
                self.model_map[(r, mi)] = len(out.models)
                out.models.append(Model(m.mins, m.maxs, m.origin, [h0] + hc, m.visleafs, first, m.numfaces))

        # visibility
        self.build_vis(total_visleafs)
        return out

    def build_vis(self, total_visleafs):
        out = self.out
        row_bytes = (total_visleafs + 7) // 8
        blob = bytearray()
        cache = {}
        base = 0
        for r, reg in enumerate(self.regions):
            src = reg.bsp
            src_bytes = (reg.visleafs + 7) // 8
            for i in range(1, reg.visleafs + 1):
                li = self.leaf_map[(r, i)]
                leaf = out.leafs[li]
                if src.leafs[i].visofs < 0:
                    leaf.visofs = -1
                    continue
                row = decompress_vis(src.visdata, src.leafs[i].visofs, src_bytes)
                bits = bytearray(row_bytes)
                for b in range(reg.visleafs):
                    if row[b >> 3] & (1 << (b & 7)):
                        nb = base + b
                        bits[nb >> 3] |= 1 << (nb & 7)
                packed = compress_vis(bytes(bits))
                if packed not in cache:
                    cache[packed] = len(blob)
                    blob += packed
                leaf.visofs = cache[packed]
            base += reg.visleafs
        for li, leaf in enumerate(out.leafs):
            if li == 0 or li > total_visleafs:
                leaf.visofs = -1
        out.visdata = bytes(blob)


# ---------------------------------------------------------------------------
# entity processing
# ---------------------------------------------------------------------------
NAME_KEYS = {"targetname", "target", "killtarget", "perishtarget", "spawnarea", "master",
             "netname_target", "LightningStart", "LightningEnd", "changetarget", "firetarget",
             "touchtarget", "teleport"}
MULTI_CLASSES = {"multi_manager", "mstrig_multi"}


def fmt_vec(v):
    return " ".join(f"{c:g}" for c in v)


TRANSITION_CLASSES = {"msarea_transition", "trigger_changelevel", "mstrig_changelevel", "trigger_teleport"}


def spectator_spot_triggers(builder: WorldBuilder, reg, spec: Entity, rename: dict) -> list[Entity]:
    """A map's spectator spot is where every joining player stands first, so triggers placed
    around it run once per map load (Helena rolls day or night there, Northern Thornlands
    brings in its mage). In the world only the start region's spot is used, so a dropped
    spot's triggers become a trigger_auto that fires whenever the region loads."""
    o = [float(x) for x in (spec.get("origin") or "0 0 0").split()]
    reach = (16.0, 16.0, 36.0)  # player hull around the spot
    transitions = {dict(x.pairs).get("targetname") for x in reg.bsp.entities
                   if dict(x.pairs).get("classname") in TRANSITION_CLASSES and dict(x.pairs).get("targetname")}
    made = []
    for src in reg.bsp.entities:
        d = dict(src.pairs)
        model = d.get("model") or ""
        if d.get("classname") not in ("trigger_once", "trigger_multiple") or not model.startswith("*") or not d.get("target"):
            continue
        m = reg.bsp.models[int(model[1:])]
        if not all(m.mins[k] - reach[k] <= o[k] <= m.maxs[k] + reach[k] for k in range(3)):
            continue
        if d["target"] in transitions:
            continue  # the spot sits in an exit (the Sewers): nothing to replay
        auto = Entity([["classname", "trigger_auto"], ["target", rename.get(d["target"], d["target"])],
                       ["triggerstate", "2"], ["spawnflags", "1"], ["origin", fmt_vec(reg.shifted(o))]])
        if d.get("delay") and float(d["delay"]) > 0:
            auto.set("delay", d["delay"])
        auto.region = reg.name
        made.append(auto)
        builder.report.setdefault("spectator_spot_triggers", {}).setdefault(reg.name, []).append(
            {"trigger": d.get("targetname"), "target": auto.get("target")})
    return made


def process_entities(builder: WorldBuilder, cfg: dict) -> list[Entity]:
    regions = builder.regions
    out: list[Entity] = []
    names = [set() for _ in regions]
    for r, reg in enumerate(regions):
        for e in reg.bsp.entities:
            for k, v in e.pairs:
                if k == "targetname" and v:
                    names[r].add(v)
    taken = set(names[0])
    for r in range(1, len(regions)):
        rename = {}
        for n in sorted(names[r]):
            if n in taken:
                new = regions[r].rename_prefix + n
                rename[n] = new
            taken.add(rename.get(n, n))
        regions[r].cfg["_rename"] = rename
        builder.report["renamed_targets"][regions[r].name] = rename

    world_spawn = None
    for r, reg in enumerate(regions):
        rename = reg.cfg.get("_rename", {})
        style_map = reg.cfg.get("_style_map", {})
        drop = set(reg.cfg.get("drop_classes", []))
        for e in reg.bsp.entities:
            e = Entity([list(p) for p in e.pairs])
            cls = e.classname
            if cls == "worldspawn":
                if world_spawn is None:
                    world_spawn = e
                    for k, v in cfg.get("worldspawn", {}).items():
                        e.set(k, v)
                    out.insert(0, e)
                continue
            if cls in drop:
                if cls == "ms_player_spec":
                    out.extend(spectator_spot_triggers(builder, reg, e, rename))
                continue
            # rename conflicting names
            for pair in e.pairs:
                k, v = pair
                if k in NAME_KEYS and v in rename:
                    pair[1] = rename[v]
                elif cls in MULTI_CLASSES and k in rename:
                    pair[0] = rename[k]
            # light styles
            if cls.startswith("light") and e.get("style") and int(e.get("style")) in style_map:
                builder.report["restyled_lights"][f"{reg.name}:{e.get('targetname')}"] = style_map[int(e.get('style'))]
                e.set("style", str(style_map[int(e.get("style"))]))
            # models
            model = e.get("model") or ""
            if model.startswith("*"):
                e.set("model", "*%d" % builder.model_map[(r, int(model[1:]))])
            # config entries (bosses) name entities by their position in the source map
            e.source_origin = e.get("origin")
            if reg.offset != (0.0, 0.0, 0.0):
                if e.get("origin"):
                    o = [float(x) for x in e.get("origin").split()]
                    e.set("origin", fmt_vec(reg.shifted(o)))
                elif model.startswith("*"):
                    e.set("origin", fmt_vec(reg.offset))
            e.region = reg.name
            out.append(e)
    return out


# ---------------------------------------------------------------------------
# verification
# ---------------------------------------------------------------------------
def min_plane_distance(bsp: BSP, headnode: int, point, hull: int) -> float:
    """Smallest |distance| from point to the planes crossed while descending the tree."""
    num, best = headnode, float("inf")
    items = bsp.nodes if hull == 0 else bsp.clipnodes
    while num >= 0:
        node = items[num]
        p = bsp.planes[node.planenum]
        d = sum(point[k] * p.normal[k] for k in range(3)) - p.dist
        best = min(best, abs(d))
        num = node.children[0] if d >= 0 else node.children[1]
    return best


def tree_order_errors(world: BSP) -> int:
    """Count children that precede their hull's head node (the engine rejects them)."""
    errors = 0
    for m in world.models:
        for h in range(4):
            head = m.headnode[h]
            if head < 0:
                continue
            items = world.nodes if h == 0 else world.clipnodes
            if head >= len(items):
                continue
            stack = [head]
            while stack:
                n = stack.pop()
                for c in items[n].children:
                    if c >= 0:
                        if c < head or c >= len(items):
                            errors += 1
                        else:
                            stack.append(c)
    return errors


def verify(builder: WorldBuilder, world: BSP, samples_per_leaf: int = 3) -> dict:
    """Compare merged hull contents and lightmap extents against the source maps."""
    import random
    rnd = random.Random(1234)
    result = {"hull_checks": 0, "hull_mismatch": 0, "extent_checks": 0, "extent_mismatch": 0,
              "vis_checks": 0, "vis_mismatch": 0, "tree_order_errors": tree_order_errors(world)}
    for r, reg in enumerate(builder.regions):
        src = reg.bsp
        w = src.models[0]
        for li in range(1, len(src.leafs)):
            leaf = src.leafs[li]
            if li > reg.visleafs:
                break
            for _ in range(samples_per_leaf):
                p = tuple(rnd.uniform(leaf.mins[k], leaf.maxs[k]) for k in range(3))
                q = reg.shifted(p)
                for h in range(4):
                    # a point within 0.01 of a plane can round to either side once the region is
                    # translated (float32 dist); the engine's own contact epsilon is 1/32
                    if min_plane_distance(src, w.headnode[h], p, h) < 0.01:
                        result["boundary_samples_skipped"] = result.get("boundary_samples_skipped", 0) + 1
                        continue
                    a = hull_point_contents(src, w.headnode[h], p, h)
                    b = hull_point_contents(world, world.models[0].headnode[h], q, h)
                    result["hull_checks"] += 1
                    if a != b:
                        result["hull_mismatch"] += 1
                        result.setdefault("hull_mismatch_samples", []).append(
                            {"region": reg.name, "leaf": li, "hull": h, "src_point": [round(c, 2) for c in p],
                             "world_point": [round(c, 2) for c in q], "src": a, "world": b})
        for fi, face in enumerate(src.faces):
            if src.texinfo[face.texinfo].flags & 1:
                continue
            of = world.faces[builder.face_map[(r, fi)]]
            a = face_extents(src, face)
            b = face_extents(world, of)
            result["extent_checks"] += 1
            if a != b:
                result["resampled_faces"] = result.get("resampled_faces", 0) + 1
            # every luxel both grids share must carry the original light
            la, lb = face_luxels(src, face, a), face_luxels(world, of, b)
            shared = la.keys() & lb.keys()
            if any(la[k] != lb[k] for k in shared) or (la and not shared):
                result["extent_mismatch"] += 1
        # PVS equivalence for a sample of leaves
        nb_src = (reg.visleafs + 7) // 8
        nb_out = (world.models[0].visleafs + 7) // 8
        for li in rnd.sample(range(1, reg.visleafs + 1), min(200, reg.visleafs)):
            if src.leafs[li].visofs < 0:
                continue
            row_a = decompress_vis(src.visdata, src.leafs[li].visofs, nb_src)
            ol = builder.leaf_map[(r, li)]
            row_b = decompress_vis(world.visdata, world.leafs[ol].visofs, nb_out)
            vis_a = {builder.leaf_map[(r, b + 1)] for b in range(reg.visleafs) if row_a[b >> 3] & (1 << (b & 7))}
            vis_b = {b + 1 for b in range(world.models[0].visleafs) if row_b[b >> 3] & (1 << (b & 7))}
            result["vis_checks"] += 1
            if vis_a != vis_b:
                result["vis_mismatch"] += 1
    return result


def face_luxels(bsp: BSP, face: Face, ext) -> dict:
    """{(style slot, s luxel, t luxel): rgb} in absolute luxel-grid coordinates."""
    if face.lightofs < 0:
        return {}
    w = ext[0][1] - ext[0][0] + 1
    h = ext[1][1] - ext[1][0] + 1
    out = {}
    for slot in range(sum(1 for s in face.styles if s != 255)):
        blk = face.lightofs + slot * w * h * 3
        for t in range(h):
            for s in range(w):
                p = blk + (t * w + s) * 3
                out[(slot, ext[0][0] + s, ext[1][0] + t)] = bsp.lighting[p:p + 3]
    return out


def repair_extents(builder: WorldBuilder, world: BSP) -> int:
    """Resample lightmaps of shifted faces whose luxel grid moved by float rounding.

    Translating a face changes its texture offsets; with scaled or rotated
    textures the float32 result can land a hair across a 16-texel boundary,
    which grows or shrinks the lightmap by one row. The luxel grid itself does
    not move, so the original samples are copied onto the new grid and the
    new edge row repeats its neighbour.
    """
    fixed = 0
    extra = bytearray()
    base = len(world.lighting)
    for r, reg in enumerate(builder.regions):
        if reg.offset == (0.0, 0.0, 0.0):
            continue
        src = reg.bsp
        for fi, face in enumerate(src.faces):
            if src.texinfo[face.texinfo].flags & 1:
                continue
            of = world.faces[builder.face_map[(r, fi)]]
            want = face_extents(src, face)
            got = face_extents(world, of)
            if got == want:
                continue
            fixed += 1
            if face.lightofs < 0:
                continue
            ow, oh = want[0][1] - want[0][0] + 1, want[1][1] - want[1][0] + 1
            nw, nh = got[0][1] - got[0][0] + 1, got[1][1] - got[1][0] + 1
            ds, dt = got[0][0] - want[0][0], got[1][0] - want[1][0]
            block = bytearray()
            for slot in range(sum(1 for s in face.styles if s != 255)):
                src_blk = face.lightofs + slot * ow * oh * 3
                for t in range(nh):
                    ot = min(max(t + dt, 0), oh - 1)
                    for s in range(nw):
                        os_ = min(max(s + ds, 0), ow - 1)
                        p = src_blk + (ot * ow + os_) * 3
                        block += src.lighting[p:p + 3]
            of.lightofs = base + len(extra)
            extra += block
    world.lighting = bytes(world.lighting) + bytes(extra)
    return fixed
