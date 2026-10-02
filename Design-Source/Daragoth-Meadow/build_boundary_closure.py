"""Restore the low original entrance boundary around the continuous meadow.

The removed legacy scenery had concealed ten low SKY walls and one missing
solid face. Keep the collision trees and high sky closure; render the low
boundary with the original embedded rock and close its exact eight-unit seam.
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
from bsp30 import BSP, Face, TexInfo, VERTEX, NODE, TEXINFO, FACE, LEAF, EDGE, MODEL

spec = importlib.util.spec_from_file_location('closure_geometry', Path(__file__).with_name('build_join_caps.py'))
caps = importlib.util.module_from_spec(spec)
spec.loader.exec_module(caps)
geometry = caps.join
BASE_SHA = '22288e02f3b9b83a2f6bcb4bcebd05fefba3bb86460469ce11ec67525c6ea0f3'
LOW_SKY = [32, 92, 93, 94, 95, 116, 117, 118, 119, 120]
OLD_CAPS = list(range(18138, 18228))
CHANGED = [3, 5, 6, 7, 8, 10, 11, 12, 13, 14]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def low_seam_parts(bsp):
    root = bsp.nodes[bsp.models[0].headnode[0]]
    initial = [(2432., 3072.), (2440., 3072.), (2440., 3584.), (2432., 3584.)]
    parts = []
    for north_leaf, north, north_poly in caps.section(bsp, root.children[0], initial):
        for _, south, poly in caps.section(bsp, root.children[1], north_poly):
            if north == -1 and south == -6 and abs(caps.area(poly)) > .05:
                parts.append({'poly': poly, 'empty_leaf': north_leaf,
                              'north_contents': north, 'south_contents': south})
    if not parts:
        raise ValueError('Expected the independently diagnosed low SKY/EMPTY seam')
    return parts


def add_polygon(bsp, points, plane, side, texinfo):
    ids = []
    for point in points:
        ids.append(len(bsp.vertexes))
        bsp.vertexes.append(point)
    first = len(bsp.surfedges)
    for a, b in zip(ids, ids[1:] + ids[:1]):
        bsp.surfedges.append(len(bsp.edges))
        bsp.edges.append((a, b))
    return Face(plane, side, first, len(ids), texinfo, [0, 255, 255, 255], -1)


def light_face(bsp, face, light):
    face.styles = [0, 255, 255, 255]
    face.lightofs = len(light)
    ext = geometry.face_extents(bsp, face, 16)
    points = geometry.polygon(bsp, face)
    center_z = sum(p[2] for p in points) / len(points)
    # Neutral outdoor illumination keeps this rock continuous with the banks.
    blend = max(0., min(1., (center_z - 3072.) / 512.))
    rgb = bytes(round(v + 12 * blend) for v in (134, 132, 122))
    light.extend(rgb * ((ext[0][1] - ext[0][0] + 1) * (ext[1][1] - ext[1][0] + 1)))


def insert_faces(bsp, at, faces, owner, holders):
    count = len(faces)
    for node in bsp.nodes:
        if node.numfaces and node.firstface >= at:
            node.firstface += count
    for model in bsp.models[1:]:
        if model.numfaces and model.firstface >= at:
            model.firstface += count
    bsp.faces[at:at] = faces
    bsp.models[0].numfaces += count
    bsp.nodes[owner].numfaces += count
    old_marks = bsp.marksurfaces
    bsp.marksurfaces = []
    enlarged = {}
    for index, leaf in enumerate(bsp.leafs):
        marks = [f + count if f >= at else f for f in
                 old_marks[leaf.firstmarksurface:leaf.firstmarksurface + leaf.nummarksurfaces]]
        additions = holders.get(index, [])
        marks.extend(additions)
        leaf.firstmarksurface = len(bsp.marksurfaces)
        leaf.nummarksurfaces = len(marks)
        bsp.marksurfaces.extend(marks)
        if additions:
            points = [p for f in additions for p in geometry.polygon(bsp, bsp.faces[f])]
            leaf.mins = tuple(min(leaf.mins[k], math.floor(min(p[k] for p in points))) for k in range(3))
            leaf.maxs = tuple(max(leaf.maxs[k], math.ceil(max(p[k] for p in points))) for k in range(3))
            enlarged[-index - 1] = (leaf.mins, leaf.maxs)
        if leaf.firstmarksurface >= 65536 or leaf.nummarksurfaces >= 65536:
            raise ValueError('Marksurface range exceeds the BSP30 budget')
    parents = {}
    for index, node in enumerate(bsp.nodes):
        for child in node.children:
            parents.setdefault(child, []).append(index)
    pending = list(enlarged)
    while pending:
        child = pending.pop()
        lo, hi = enlarged[child]
        for index in parents.get(child, []):
            node = bsp.nodes[index]
            new_lo = tuple(min(node.mins[k], lo[k]) for k in range(3))
            new_hi = tuple(max(node.maxs[k], hi[k]) for k in range(3))
            if new_lo != node.mins or new_hi != node.maxs:
                node.mins, node.maxs = new_lo, new_hi
                enlarged[index] = (new_lo, new_hi)
                pending.append(index)


def build(base, out):
    data = base.read_bytes()
    if sha(data) != BASE_SHA:
        raise ValueError('Use the frozen visible animated creek input')
    target = out / 'daragoth_meadow_final.bsp'
    if target.exists() or target.resolve() == base.resolve():
        raise ValueError('Keep the frozen inputs and previous candidates separate')
    bsp = BSP.load(base)
    parts = low_seam_parts(bsp)
    root_id = bsp.models[0].headnode[0]
    if bsp.nodes[78].firstface != 116 or bsp.nodes[78].numfaces != 3 or bsp.nodes[78].planenum != 24:
        raise ValueError('Original missing boundary face owner changed')
    original = bsp.texinfo[14]
    if bsp.textures[original.miptex].name != 'rock01a_ewok':
        raise ValueError('Original embedded entrance rock is unavailable')
    xwall_ti = len(bsp.texinfo)
    bsp.texinfo.append(TexInfo([[0., original.vecs[0][0], 0., original.vecs[0][3]],
                                list(original.vecs[1])], original.miptex, original.flags))
    light = bytearray(bsp.lighting)
    for index in LOW_SKY + OLD_CAPS:
        face = bsp.faces[index]
        expected = 'sky' if index in LOW_SKY else 'DPROCK'
        if bsp.textures[bsp.texinfo[face.texinfo].miptex].name != expected:
            raise ValueError(f'Unexpected boundary material at original face {index}')
        face.texinfo = xwall_ti if abs(bsp.planes[face.planenum].normal[0]) > .999 else 14
        light_face(bsp, face, light)
    rectangle = add_polygon(bsp, [(1936., 3088., 3072.), (2320., 3088., 3072.),
                                 (2320., 3088., 3336.), (1936., 3088., 3336.)], 24, 0, 14)
    light_face(bsp, rectangle, light)
    insert_faces(bsp, 119, [rectangle], 78, {1: [119], 36: [119], 3541: [119]})
    at = bsp.models[0].firstface + bsp.models[0].numfaces
    root = bsp.nodes[root_id]
    if root.firstface + root.numfaces != at:
        raise ValueError('The join faces must end the contiguous world range')
    new_faces, holders = [], {}
    for n, part in enumerate(parts):
        poly = part['poly']
        if caps.area(poly) < 0:
            poly = list(reversed(poly))
        face = add_polygon(bsp, [(x, 3216., z) for x, z in poly], root.planenum, 0, 14)
        light_face(bsp, face, light)
        new_faces.append(face)
        for leaf in {1, 3541, part['empty_leaf']}:
            holders.setdefault(leaf, []).append(at + n)
    insert_faces(bsp, at, new_faces, root_id, holders)
    bsp.lighting = bytes(light)
    if len(bsp.faces) >= 65536 or len(bsp.vertexes) >= 65536:
        raise ValueError('Boundary rendering exceeds BSP30 index budgets')
    changed = {
        3: b''.join(VERTEX.pack(*v) for v in bsp.vertexes),
        5: b''.join(NODE.pack(n.planenum, *n.children, *n.mins, *n.maxs, n.firstface, n.numfaces) for n in bsp.nodes),
        6: b''.join(TEXINFO.pack(*t.vecs[0], *t.vecs[1], t.miptex, t.flags) for t in bsp.texinfo),
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
    if sha(base.read_bytes()) != BASE_SHA:
        raise ValueError('Frozen input changed during construction')
    out.mkdir(parents=True, exist_ok=True)
    target.write_bytes(output)
    report = {'base_sha256': BASE_SHA, 'output_sha256': sha(output),
              'source_builder_sha256': sha(Path(__file__).read_bytes()),
              'changed_lumps': CHANGED, 'material': 'rock01a_ewok',
              'original_low_sky_faces_retextured': LOW_SKY,
              'previous_join_caps_retextured': OLD_CAPS,
              'missing_original_rectangle': {'face': 119, 'plane': 24, 'node': 78,
                  'bounds': [[1936, 3088, 3072], [2320, 3088, 3336]], 'side': 0},
              'low_sky_seam_insert_at': at, 'low_sky_seam_parts': parts,
              'added_faces': 1 + len(new_faces), 'xwall_texinfo': xwall_ti,
              'all_entities_preserved': True, 'world_collision_trees_preserved': True,
              'water_model_world_geometry_and_animation_preserved': True,
              'high_sky_closure_preserved': True, 'requires_native_verification': True}
    (out / 'boundary-closure-build-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('output_sha256', 'added_faces', 'low_sky_seam_parts')}, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    build(args.base, args.out)
