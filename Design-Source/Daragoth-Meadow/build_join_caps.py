"""Close exposed solid cuts on both sides of the continuous meadow join.

Partition the two existing render trees at the join, subtract already rendered
coplanar surfaces, and add only missing faces. Collision planes, children,
clipnodes, water and all other entities are preserved.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import struct
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'Packaging-Work/BigWorld/tools'))
from bsp30 import BSP, Face, VERTEX, NODE, FACE, LEAF, EDGE, MODEL

spec = importlib.util.spec_from_file_location('join_geometry', REPO / 'Design-Source/Daragoth-Expanded/build_expanded.py')
join = importlib.util.module_from_spec(spec)
spec.loader.exec_module(join)

BASE_SHA = '9b3ae9aaeb56ff274f0caa3979661de8970c0cdf43de603c0b06355bc098c064'
SEAM = 3216.0


def digest(data):
    return hashlib.sha256(data).hexdigest()


def area(poly):
    return sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(poly, poly[1:] + poly[:1])) / 2


def bounds(poly):
    return min(p[0] for p in poly), min(p[1] for p in poly), max(p[0] for p in poly), max(p[1] for p in poly)


def intersects(a, b):
    return a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]


def section(bsp, head, poly):
    stack = [(head, poly)]
    while stack:
        node, part = stack.pop()
        if not part:
            continue
        if node < 0:
            leaf = -node - 1
            yield leaf, bsp.leafs[leaf].contents, part
            continue
        record = bsp.nodes[node]
        plane = bsp.planes[record.planenum]
        a, b = plane.normal[0], plane.normal[2]
        c = plane.normal[1] * SEAM - plane.dist
        if abs(a) + abs(b) < 1e-10:
            stack.append((record.children[0 if c >= 0 else 1], part))
        else:
            for positive, child in ((True, record.children[0]), (False, record.children[1])):
                clipped = join.clip_2d(part, a, b, c, positive)
                if clipped:
                    stack.append((child, clipped))


def subtract(poly, cover):
    """Convex polygon difference: retain outside pieces as each edge clips in."""
    remaining = poly
    positive = area(cover) > 0
    result = []
    for p, q in zip(cover, cover[1:] + cover[:1]):
        if not remaining:
            break
        dx, dz = q[0] - p[0], q[1] - p[1]
        a, b, c = -dz, dx, dz * p[0] - dx * p[1]
        outside = join.clip_2d(remaining, a, b, c, not positive)
        if outside:
            result.append(outside)
        remaining = join.clip_2d(remaining, a, b, c, positive)
    return result


def missing_sections(bsp):
    root = bsp.nodes[bsp.models[0].headnode[0]]
    plane = bsp.planes[root.planenum]
    if plane.normal != (0.0, 1.0, 0.0) or plane.dist != SEAM:
        raise ValueError('Expected the accepted axial continuous join')
    existing = {0: [], 1: []}
    old_caps = []
    world = bsp.models[0]
    for i in range(world.firstface, world.firstface + world.numfaces):
        face = bsp.faces[i]
        points = join.polygon(bsp, face)
        if points and all(abs(p[1] - SEAM) < .0001 for p in points):
            normal = bsp.planes[face.planenum].normal
            effective_y = normal[1] * (-1 if face.side else 1)
            if abs(effective_y) > .9999:
                side = 0 if effective_y > 0 else 1
                poly = [(p[0], p[2]) for p in points]
                existing[side].append((bounds(poly), poly))
                old_caps.append(i)
    generated = []
    # Small tiles bound texture extents and keep all section clipping local.
    xmin, zmin, xmax, zmax = world.mins[0], world.mins[2], world.maxs[0], world.maxs[2]
    x = xmin
    while x < xmax - .001:
        right = min(x + 256, xmax)
        z = zmin
        while z < zmax - .001:
            top = min(z + 256, zmax)
            initial = [(x, z), (right, z), (right, top), (x, top)]
            for north_leaf, north, north_poly in section(bsp, root.children[0], initial):
                for south_leaf, south, part in section(bsp, root.children[1], north_poly):
                    side = 1 if north == -2 and south in (-1, -6) else 0 if south == -2 and north in (-1, -6) else None
                    if side is None:
                        continue
                    pieces = [part]
                    for cover_bounds, cover in existing[side]:
                        if not intersects(bounds(part), cover_bounds):
                            continue
                        pieces = [fragment for piece in pieces for fragment in subtract(piece, cover)]
                        if not pieces:
                            break
                    for piece in pieces:
                        if abs(area(piece)) > .05:
                            generated.append({'side': side, 'poly': piece,
                                              'empty_leaf': south_leaf if side else north_leaf,
                                              'north_contents': north, 'south_contents': south})
            z = top
        x = right
    return generated, old_caps


def build(base, out):
    data = base.read_bytes()
    if digest(data) != BASE_SHA:
        raise ValueError('Use the frozen creek candidate as input')
    target = out / 'daragoth_meadow_repaired.bsp'
    if target.resolve() == base.resolve():
        raise ValueError('Keep the frozen input separate')
    bsp = BSP.load(base)
    parts, old_caps = missing_sections(bsp)
    if not parts:
        raise ValueError('No missing solid cut faces found')
    world = bsp.models[0]
    root = bsp.nodes[world.headnode[0]]
    at = world.firstface + world.numfaces
    if root.firstface + root.numfaces != at:
        raise ValueError('Join faces must end the accepted contiguous world range')
    ti = next(bsp.faces[i].texinfo for i in old_caps
              if bsp.textures[bsp.texinfo[bsp.faces[i].texinfo].miptex].name == 'DPROCK')
    light = bytearray(bsp.lighting)
    new_faces = []
    holders = {}
    # Existing cap anchors are already conservatively visible across the join.
    common_holders = [i for i, leaf in enumerate(bsp.leafs)
                      if set(old_caps).issubset(set(bsp.marksurfaces[leaf.firstmarksurface:leaf.firstmarksurface + leaf.nummarksurfaces]))]
    if len(common_holders) != 2:
        raise ValueError('Expected the two previously audited join visibility anchors')
    for n, part in enumerate(parts):
        poly = part['poly']
        if area(poly) < 0:
            poly = list(reversed(poly))
        if part['side']:
            poly = list(reversed(poly))
        points = [(x, SEAM, z) for x, z in poly]
        ids = []
        for point in points:
            ids.append(len(bsp.vertexes))
            bsp.vertexes.append(point)
        first = len(bsp.surfedges)
        for a, b in zip(ids, ids[1:] + ids[:1]):
            bsp.surfedges.append(len(bsp.edges))
            bsp.edges.append((a, b))
        face = Face(root.planenum, part['side'], first, len(ids), ti, [0, 255, 255, 255], len(light))
        ext = join.face_extents(bsp, face, 16)
        for t in range(ext[1][0], ext[1][1] + 1):
            for s in range(ext[0][0], ext[0][1] + 1):
                z = -t * 64
                blend = max(0, min(1, (z - 3072) / 512))
                noise = 4 * math.sin(s * 1.93 + t * 3.1)
                light.extend(bytes(int(max(0, min(255, v))) for v in
                                   (112 + 25 * blend + noise, 103 + 23 * blend + noise, 94 + 21 * blend + noise)))
        new_faces.append(face)
        for leaf in set(common_holders + [part['empty_leaf']]):
            holders.setdefault(leaf, []).append(at + n)
    count = len(new_faces)
    if len(bsp.faces) + count >= 65536 or len(bsp.vertexes) >= 65536:
        raise ValueError('New cut faces exceed BSP30 index budgets')
    for node in bsp.nodes:
        if node.numfaces and node.firstface >= at:
            node.firstface += count
    for model in bsp.models[1:]:
        if model.numfaces and model.firstface >= at:
            model.firstface += count
    bsp.faces[at:at] = new_faces
    world.numfaces += count
    root.numfaces += count
    old_marks = bsp.marksurfaces
    bsp.marksurfaces = []
    enlarged = {}
    for i, leaf in enumerate(bsp.leafs):
        marks = [f + count if f >= at else f for f in
                 old_marks[leaf.firstmarksurface:leaf.firstmarksurface + leaf.nummarksurfaces]]
        additions = holders.get(i, [])
        marks.extend(additions)
        leaf.firstmarksurface = len(bsp.marksurfaces)
        leaf.nummarksurfaces = len(marks)
        if leaf.firstmarksurface >= 65536 or leaf.nummarksurfaces >= 65536:
            raise ValueError('Marksurface range exceeds BSP30 leaf budget')
        bsp.marksurfaces.extend(marks)
        if additions:
            vertices = [p for f in additions for p in join.polygon(bsp, bsp.faces[f])]
            lo = tuple(math.floor(min(p[k] for p in vertices)) for k in range(3))
            hi = tuple(math.ceil(max(p[k] for p in vertices)) for k in range(3))
            leaf.mins = tuple(min(leaf.mins[k], lo[k]) for k in range(3))
            leaf.maxs = tuple(max(leaf.maxs[k], hi[k]) for k in range(3))
            enlarged[-i - 1] = (leaf.mins, leaf.maxs)
    parents = {}
    for n, node in enumerate(bsp.nodes):
        for child in node.children:
            parents.setdefault(child, []).append(n)
    pending = list(enlarged)
    while pending:
        child = pending.pop()
        lo, hi = enlarged[child]
        for n in parents.get(child, []):
            node = bsp.nodes[n]
            updated_lo = tuple(min(node.mins[k], lo[k]) for k in range(3))
            updated_hi = tuple(max(node.maxs[k], hi[k]) for k in range(3))
            if updated_lo != node.mins or updated_hi != node.maxs:
                node.mins, node.maxs = updated_lo, updated_hi
                enlarged[n] = (updated_lo, updated_hi)
                pending.append(n)
    bsp.lighting = bytes(light)
    # Append only changed render lumps; retain all collision and source bytes.
    changed = {
        3: b''.join(VERTEX.pack(*v) for v in bsp.vertexes),
        5: b''.join(NODE.pack(n.planenum, *n.children, *n.mins, *n.maxs, n.firstface, n.numfaces) for n in bsp.nodes),
        7: b''.join(FACE.pack(f.planenum, f.side, f.firstedge, f.numedges, f.texinfo, *f.styles, f.lightofs) for f in bsp.faces),
        8: bsp.lighting,
        10: b''.join(LEAF.pack(l.contents, l.visofs, *l.mins, *l.maxs, l.firstmarksurface, l.nummarksurfaces, *l.ambient) for l in bsp.leafs),
        11: struct.pack(f'<{len(bsp.marksurfaces)}H', *bsp.marksurfaces),
        12: b''.join(EDGE.pack(*e) for e in bsp.edges),
        13: struct.pack(f'<{len(bsp.surfedges)}i', *bsp.surfedges),
        14: b''.join(MODEL.pack(*m.mins, *m.maxs, *m.origin, *m.headnode, m.visleafs, m.firstface, m.numfaces) for m in bsp.models),
    }
    output = bytearray(data)
    for i, blob in changed.items():
        output.extend(b'\0' * (-len(output) % 4))
        offset = len(output)
        output.extend(blob)
        struct.pack_into('<2i', output, 4 + 8 * i, offset, len(blob))
    if digest(base.read_bytes()) != BASE_SHA:
        raise ValueError('Input changed during build')
    out.mkdir(parents=True, exist_ok=True)
    target.write_bytes(output)
    report = {'base_sha256': BASE_SHA, 'output_sha256': digest(output),
              'seam_y': SEAM, 'insert_face_at': at, 'added_faces': count,
              'north_facing_faces': sum(p['side'] == 0 for p in parts),
              'south_facing_faces': sum(p['side'] == 1 for p in parts),
              'changed_lumps': list(changed), 'common_visibility_anchors': common_holders,
              'entities_preserved': len(bsp.entities), 'collision_geometry_preserved': True,
              'existing_surfaces_subtracted': True, 'material': 'DPROCK',
              'parts': parts, 'requires_native_verification': True}
    (out / 'join-caps-build-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('output_sha256', 'added_faces', 'north_facing_faces', 'south_facing_faces')}, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    build(args.base, args.out)
