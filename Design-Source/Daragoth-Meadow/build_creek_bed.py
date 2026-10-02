"""Restore absent compiled creek-bed render polygons; preserve every hull.

The broad creek survey distinguishes dry banks and bridge supports from actual
missing underwater faces. Two adjacent cells are audited; only the one missing
EMPTY/SOLID interface is repaired.
Existing coplanar faces are subtracted, and adjacent grass UV/lightmaps are used.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO / 'Packaging-Work/BigWorld/tools'), str(Path(__file__).parent)]
from bsp30 import BSP, Face, VERTEX, NODE, FACE, LEAF, EDGE, MODEL
from meadow_surface import SurfaceIndex

BASE_SHA = 'a82d997a153543198f01c2d36199b7d78498f309c6a251fa70891abacbf69f29'
TOP = 2936.0
GROUND = ('DPGRASS', 'DPPATH', 'DPDIRT')
EMPTY, SOLID = -1, -2
SOURCES = {8807: 13410, 8808: 13412}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def f32(v):
    return struct.unpack('<f', struct.pack('<f', v))[0]


def area(poly):
    return sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(poly, poly[1:] + poly[:1])) / 2


def clip(poly, a, b, c, positive=True):
    if not poly:
        return []
    out = []
    for p, q in zip(poly, poly[1:] + poly[:1]):
        dp, dq = a * p[0] + b * p[1] + c, a * q[0] + b * q[1] + c
        ip = dp >= -1e-8 if positive else dp <= 1e-8
        iq = dq >= -1e-8 if positive else dq <= 1e-8
        if ip:
            out.append(p)
        if ip != iq:
            t = dp / (dp - dq)
            out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    clean = []
    for p in out:
        if not clean or math.dist(p, clean[-1]) > 1e-7:
            clean.append(p)
    if len(clean) > 1 and math.dist(clean[0], clean[-1]) < 1e-7:
        clean.pop()
    return clean if len(clean) >= 3 and abs(area(clean)) > 1e-7 else []


def subtract(poly, cover):
    remaining = poly
    outside = []
    positive = area(cover) > 0
    for p, q in zip(cover, cover[1:] + cover[:1]):
        dx, dy = q[0] - p[0], q[1] - p[1]
        a, b, c = -dy, dx, dy * p[0] - dx * p[1]
        part = clip(remaining, a, b, c, not positive)
        if part:
            outside.append(part)
        remaining = clip(remaining, a, b, c, positive)
        if not remaining:
            break
    return outside


def polygon(bsp, face):
    return [bsp.vertexes[bsp.edges[abs(e)][0 if e >= 0 else 1]]
            for e in bsp.surfedges[face.firstedge:face.firstedge + face.numedges]]


def leaf_at(bsp, point, with_path=False):
    point = tuple(map(f32, point))
    head = bsp.models[0].headnode[0]
    path = []
    while head >= 0:
        node = bsp.nodes[head]
        plane = bsp.planes[node.planenum]
        if plane.type < 3:
            d = f32(point[plane.type] - plane.dist)
        else:
            dot = f32(f32(f32(point[0] * plane.normal[0]) + f32(point[1] * plane.normal[1])) + f32(point[2] * plane.normal[2]))
            d = f32(dot - plane.dist)
        side = 0 if d >= 0 else 1
        path.append((head, side))
        head = node.children[side]
    return (-head - 1, path) if with_path else -head - 1


def contents(bsp, point):
    return bsp.leafs[leaf_at(bsp, point)].contents


def floor(bsp, x, y):
    lo, hi = 2808.0, TOP - 4
    if contents(bsp, (x, y, hi)) != EMPTY or contents(bsp, (x, y, lo)) != SOLID:
        return None
    for _ in range(32):
        mid = f32((lo + hi) / 2)
        if mid <= lo or mid >= hi:
            break
        if contents(bsp, (x, y, mid)) == SOLID:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def boundary_owner(bsp, x, y, z):
    # Neighboring sloped planes approach within .013 units at one coarse
    # sample. A larger offset would cross both nodes and misidentify its owner.
    above, ap = leaf_at(bsp, (x, y, z + .002), True)
    below, bp = leaf_at(bsp, (x, y, z - .002), True)
    for a, b in zip(ap, bp):
        if a != b:
            if a[0] != b[0]:
                raise ValueError('Unexpected divergent collision paths')
            return a[0], above, below
    raise ValueError('No solid boundary owner')


def survey(bsp):
    index = SurfaceIndex(bsp)
    counts, missing = Counter(), []
    for x in range(-11000, 11001, 128):
        for y in range(13496, 16537, 32):
            wx = x + 1650.05
            if index.at(wx, y, GROUND) is not None:
                continue
            all_surface = index.at(wx, y)
            below_water = index.at(wx, y, max_z=TOP)
            world = contents(bsp, (wx, y, TOP - .01))
            if world == SOLID:
                kind = 'dry_' + (all_surface['texture'] if all_surface else 'no_surface')
            else:
                z = floor(bsp, wx, y)
                if z is None:
                    raise ValueError('Unclassified wet creek miss')
                if below_water is not None and abs(below_water['z'] - z) < .02:
                    kind = 'wet_other_rendered_material'
                else:
                    owner, above, below = boundary_owner(bsp, wx, y, z)
                    kind = 'wet_missing_bed'
                    missing.append({'xy': [wx, y], 'floor_z': z, 'node': owner,
                                    'plane': bsp.nodes[owner].planenum,
                                    'empty_leaf': above, 'solid_leaf': below,
                                    'covering_surface': all_surface,
                                    'rendered_below_water': below_water})
            counts[kind] += 1
    fine = []
    for x in range(-288, 289, 32):
        for y in range(1104, 2497, 32):
            wx, wy = 1650.05 + x, 13216 + y
            if index.at(wx, wy, GROUND) is None:
                z = floor(bsp, wx, wy)
                if z is None:
                    raise ValueError('Fine bridge miss has no solid floor')
                owner, above, below = boundary_owner(bsp, wx, wy, z)
                fine.append({'xy': [wx, wy], 'floor_z': z, 'node': owner,
                             'empty_leaf': above, 'solid_leaf': below})
    if sum(counts.values()) != 313 or len(missing) != 13 or len(fine) != 49:
        raise ValueError('Frozen source survey differs from diagnosed creek')
    if {p['node'] for p in missing + fine} != {8808}:
        raise ValueError('Additional wet missing-bed cell requires review')
    return {'ground_texture_misses': sum(counts.values()), 'classification': dict(counts),
            'broad_grid': {'local_x': [-11000, 11000, 128], 'world_x_offset': 1650.05,
                          'world_y': [13496, 16536, 32], 'below_water_max_z': TOP},
            'wet_missing_points': missing, 'fine_bridge_missing_points': fine}


def path_to(bsp, target):
    stack = [(bsp.models[0].headnode[0], [])]
    while stack:
        head, path = stack.pop()
        if head == target:
            return path
        if head >= 0:
            for side, child in enumerate(bsp.nodes[head].children):
                stack.append((child, path + [(head, side)]))
    raise ValueError('Diagnosed owner is not in world tree')


def equation(bsp, planenum, target):
    plane = bsp.planes[planenum]
    nx, ny, nz = target.normal
    return (plane.normal[0] - plane.normal[2] * nx / nz,
            plane.normal[1] - plane.normal[2] * ny / nz,
            plane.normal[2] * target.dist / nz - plane.dist)


def partition(bsp, head, poly, target):
    stack = [(head, poly)]
    while stack:
        head, piece = stack.pop()
        if not piece:
            continue
        if head < 0:
            leaf = -head - 1
            yield leaf, bsp.leafs[leaf].contents, piece
            continue
        node = bsp.nodes[head]
        a, b, c = equation(bsp, node.planenum, target)
        if abs(a) + abs(b) < 1e-10:
            stack.append((node.children[0 if c >= 0 else 1], piece))
        else:
            for side, child in enumerate(node.children):
                stack.append((child, clip(piece, a, b, c, side == 0)))


def sections(bsp, owner, source_face):
    node = bsp.nodes[owner]
    plane = bsp.planes[node.planenum]
    if abs(plane.normal[2]) < .2:
        raise ValueError('Bed owner is not an upward plane')
    world = bsp.models[0]
    poly = [(world.mins[0], world.mins[1]), (world.maxs[0], world.mins[1]),
            (world.maxs[0], world.maxs[1]), (world.mins[0], world.maxs[1])]
    path = path_to(bsp, owner)
    for parent, side in path:
        poly = clip(poly, *equation(bsp, bsp.nodes[parent].planenum, plane), side == 0)
    side = 0 if plane.normal[2] > 0 else 1
    empty_child, solid_child = node.children[side], node.children[1 - side]
    covers = []
    for i in range(world.firstface, world.firstface + world.numfaces):
        face = bsp.faces[i]
        if face.planenum == node.planenum and face.side == side:
            covers.append((i, [(p[0], p[1]) for p in polygon(bsp, face)]))
    parts, interface_area, discarded = [], 0., 0.
    for empty_leaf, ec, empty_poly in partition(bsp, empty_child, poly, plane):
        if ec != EMPTY:
            continue
        for solid_leaf, sc, piece in partition(bsp, solid_child, empty_poly, plane):
            if sc != SOLID:
                continue
            interface_area += abs(area(piece))
            pieces = [piece]
            for _, cover in covers:
                pieces = [part for p in pieces for part in subtract(p, cover)]
            for part in pieces:
                if abs(area(part)) <= .05:
                    discarded += abs(area(part))
                    continue
                # Only the existing creek bed height interval is eligible.
                z_values = [(plane.dist - plane.normal[0] * x - plane.normal[1] * y) / plane.normal[2] for x, y in part]
                if min(z_values) < 2808 or max(z_values) > TOP:
                    raise ValueError('Bed closure extends beyond diagnosed underwater bed')
                parts.append({'xy': part, 'empty_leaf': empty_leaf, 'solid_leaf': solid_leaf})
    return {'node': owner, 'plane': node.planenum, 'side': side, 'source_face': source_face,
            'source_texinfo': bsp.faces[source_face].texinfo, 'ancestor_path': path,
            'cell_xy': poly, 'interface_area_xy': interface_area, 'existing_faces': [f for f, p in covers],
            'discarded_sliver_area_xy': discarded, 'parts': parts}


def sample_size(bsp, face):
    index = bsp.texinfo[face.texinfo].flags >> 16
    records = bsp.extra_lumps.get(1, b'')
    return struct.unpack_from('<H', records, index * 22 + 16)[0] if index >= 0 and len(records) >= (index + 1) * 22 else 16


def extents(bsp, points, texinfo, step):
    ti = bsp.texinfo[texinfo]
    return [(math.floor(min(sum(p[k] * v[k] for k in range(3)) + v[3] for p in points) / step),
             math.ceil(max(sum(p[k] * v[k] for k in range(3)) + v[3] for p in points) / step)) for v in ti.vecs]


def new_lightmap(bsp, light, points, source_id):
    source = bsp.faces[source_id]
    if source.styles != [0, 255, 255, 255] or source.lightofs < 0:
        raise ValueError('Adjacent bed must have ordinary style0 lightmap')
    step = sample_size(bsp, source)
    oldext = extents(bsp, polygon(bsp, source), source.texinfo, step)
    newext = extents(bsp, points, source.texinfo, step)
    width = oldext[0][1] - oldext[0][0] + 1
    size = width * (oldext[1][1] - oldext[1][0] + 1) * 3
    source_bytes = bsp.lighting[source.lightofs:source.lightofs + size]
    if len(source_bytes) != size:
        raise ValueError('Adjacent bed lightmap is truncated')
    offset = len(light)
    for t in range(newext[1][0], newext[1][1] + 1):
        for s in range(newext[0][0], newext[0][1] + 1):
            ss = max(oldext[0][0], min(oldext[0][1], s)) - oldext[0][0]
            tt = max(oldext[1][0], min(oldext[1][1], t)) - oldext[1][0]
            at = (tt * width + ss) * 3
            light.extend(source_bytes[at:at + 3])
    return offset, {'sample_step': step, 'source_extents': oldext, 'new_extents': newext,
                    'source_lightofs': source.lightofs, 'policy': 'style0_clamped_adjacent_UV_grid_RGB'}


def build(base, out, survey_only=False):
    data = base.read_bytes()
    if sha(data) != BASE_SHA:
        raise ValueError('Use the frozen material candidate a82 as input')
    bsp = BSP.load(base)
    surveyed = survey(bsp)
    cells = [sections(bsp, owner, face) for owner, face in SOURCES.items()]
    if survey_only:
        print(json.dumps({'survey': surveyed, 'source_cells': cells}, indent=2))
        return
    target = out / 'daragoth_meadow_bed_repaired.bsp'
    if target.exists() or target.resolve() == base.resolve():
        raise ValueError('New private output must not overwrite a frozen candidate')
    old_face_count = len(bsp.faces)
    old_node_ranges = [(n.firstface, n.numfaces) for n in bsp.nodes]
    light = bytearray(bsp.lighting)
    insertions = {}
    additions = []
    for cell in cells:
        node = bsp.nodes[cell['node']]
        at = node.firstface + node.numfaces
        faces = []
        plane = bsp.planes[cell['plane']]
        for part in cell['parts']:
            poly = part['xy']
            if area(poly) > 0:
                poly = list(reversed(poly))
            points = [tuple(map(f32, (x, y, (plane.dist - plane.normal[0] * x - plane.normal[1] * y) / plane.normal[2]))) for x, y in poly]
            if max(abs(sum(p[k] * plane.normal[k] for k in range(3)) - plane.dist) for p in points) > .002:
                raise ValueError('Compiled new bed vertex left its source plane')
            ids = []
            for p in points:
                ids.append(len(bsp.vertexes)); bsp.vertexes.append(p)
            first = len(bsp.surfedges)
            for a, b in zip(ids, ids[1:] + ids[:1]):
                bsp.surfedges.append(len(bsp.edges)); bsp.edges.append((a, b))
            offset, lighting = new_lightmap(bsp, light, points, cell['source_face'])
            face = Face(cell['plane'], cell['side'], first, len(points), cell['source_texinfo'], [0, 255, 255, 255], offset)
            part.update({'points': points, 'lightmap': lighting, 'firstedge': first, 'lightofs': offset})
            faces.append((face, part))
            additions.append((cell, part))
        if faces:
            insertions[at] = faces
    old_faces = bsp.faces
    new_faces, remap = [], {}
    for old_id in range(old_face_count + 1):
        for face, part in insertions.get(old_id, []):
            part['face'] = len(new_faces); new_faces.append(face)
        if old_id < old_face_count:
            remap[old_id] = len(new_faces); new_faces.append(old_faces[old_id])
    bsp.faces = new_faces
    count = len(additions)
    if len(bsp.faces) >= 65536 or len(bsp.vertexes) >= 65536:
        raise ValueError('BSP30 face/vertex index budget exceeded')
    for i, node in enumerate(bsp.nodes):
        first, n = old_node_ranges[i]
        node.firstface = remap[first] if first < old_face_count else first + count
        if i in SOURCES:
            node.numfaces += len(next(c for c in cells if c['node'] == i)['parts'])
        elif n and any(first < at < first + n for at in insertions):
            raise ValueError('An unrelated node range spans inserted bed faces')
    for i, model in enumerate(bsp.models):
        model.firstface = remap[model.firstface]
        if i == 0:
            model.numfaces += count
    common = [1, 3541]  # Existing meadow cross-PVS rendering anchors.
    holders = {}
    for cell, part in additions:
        for leaf in set(common + [part['empty_leaf']]):
            holders.setdefault(leaf, []).append(part['face'])
    old_marks = bsp.marksurfaces
    bsp.marksurfaces = []
    enlarged = {}
    for i, leaf in enumerate(bsp.leafs):
        marks = [remap[f] for f in old_marks[leaf.firstmarksurface:leaf.firstmarksurface + leaf.nummarksurfaces]]
        marks += holders.get(i, [])
        leaf.firstmarksurface, leaf.nummarksurfaces = len(bsp.marksurfaces), len(marks)
        if leaf.firstmarksurface >= 65536 or leaf.nummarksurfaces >= 65536:
            raise ValueError('BSP30 leaf marks budget exceeded')
        bsp.marksurfaces.extend(marks)
        if i in holders:
            points = [p for face in holders[i] for p in polygon(bsp, bsp.faces[face])]
            leaf.mins = tuple(min(leaf.mins[k], math.floor(min(p[k] for p in points))) for k in range(3))
            leaf.maxs = tuple(max(leaf.maxs[k], math.ceil(max(p[k] for p in points))) for k in range(3))
            enlarged[-i - 1] = (leaf.mins, leaf.maxs)
    parents = {}
    for i, node in enumerate(bsp.nodes):
        for child in node.children:
            parents.setdefault(child, []).append(i)
    pending = list(enlarged)
    while pending:
        child = pending.pop()
        lo, hi = enlarged[child]
        for i in parents.get(child, []):
            node = bsp.nodes[i]
            a = tuple(min(node.mins[k], lo[k]) for k in range(3))
            b = tuple(max(node.maxs[k], hi[k]) for k in range(3))
            if a != node.mins or b != node.maxs:
                node.mins, node.maxs = a, b
                enlarged[i] = (a, b); pending.append(i)
    bsp.lighting = bytes(light)
    restored = SurfaceIndex(bsp)
    for point in surveyed['wet_missing_points'] + surveyed['fine_bridge_missing_points']:
        s = restored.at(*point['xy'], max_z=TOP)
        if s is None or abs(s['z'] - point['floor_z']) > .01:
            raise ValueError('New rendered bed does not cover a diagnosed wet omission')
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
        offset = len(output); output.extend(blob)
        struct.pack_into('<2i', output, 4 + 8 * i, offset, len(blob))
    if sha(base.read_bytes()) != BASE_SHA:
        raise ValueError('Frozen source changed during build')
    out.mkdir(parents=True, exist_ok=True)
    target.write_bytes(output)
    report = {'base_sha256': BASE_SHA, 'output_sha256': sha(output), 'builder_sha256': sha(Path(__file__).read_bytes()),
              'output_path': str(target.resolve()), 'added_faces': count, 'changed_lumps': list(changed),
              'source_cells': cells, 'face_insertions': {str(k): len(v) for k, v in insertions.items()},
              'old_face_remapping': [[i, remap[i]] for i in range(old_face_count)],
              'common_visibility_anchors': common, 'leaf_additions': holders,
              'survey_before': surveyed, 'diagnosed_wet_missing_points_covered': len(surveyed['wet_missing_points']),
              'fine_bridge_missing_points_covered': len(surveyed['fine_bridge_missing_points']),
              'entities_preserved': len(bsp.entities), 'collision_geometry_preserved': True,
              'all_old_face_geometry_preserved': True, 'material': 'adjacent_DPGRASS',
              'requires_independent_and_native_verification': True}
    (out / 'creek-bed-build-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'output_sha256': report['output_sha256'], 'added_faces': count,
                      'classification': surveyed['classification'], 'cells': [{k: c[k] for k in ('node', 'plane', 'interface_area_xy', 'discarded_sliver_area_xy')} for c in cells]}, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--survey-only', action='store_true')
    args = parser.parse_args()
    build(args.base, args.out, args.survey_only)
