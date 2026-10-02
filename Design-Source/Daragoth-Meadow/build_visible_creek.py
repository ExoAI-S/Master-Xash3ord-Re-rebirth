"""Bake the creek's common height into an appended animated water brush model.

The stock renderer compares a water face's local plane height with translated
model bounds. A nonzero vertical entity origin therefore hides this creek.
This map-only repair clones the complete brush model at +2720 Z, then removes
that same Z offset from its four instances. Geometry, UVs and fluid contents
remain at their original world positions; no engine or game change is needed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'Packaging-Work/BigWorld/tools'))
from bsp30 import (BSP, Entity, format_entities, PLANE, VERTEX, NODE, TEXINFO,
                   FACE, CLIPNODE32, LEAF, EDGE, MODEL)

BASE_SHA256 = '827f22e886c679f44cdfe8584d339feae841e49b9f43e4ec2da3fb2949b26cf8'
SOURCE_MODEL = 162
Z_BAKE = 2720
ALLOWED_OUT = REPO.parent / 'daragoth-development/meadow-visible-creek'
CHANGED_LUMPS = (0, 1, 3, 5, 6, 7, 9, 10, 11, 12, 13, 14)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def f32(value):
    return struct.unpack('<f', struct.pack('<f', value))[0]


def shifted(point):
    return (point[0], point[1], point[2] + Z_BAKE)


def closure(records, root, leaves=None):
    """Collect one acyclic hull without assuming contiguous compiler records."""
    reached, active = set(), set()

    def visit(index):
        if index < 0:
            if leaves is not None:
                leaves.add(-1 - index)
            return
        if index in active:
            raise ValueError('Cyclic source hull')
        if index in reached:
            return
        if index >= len(records):
            raise ValueError('Source hull references an invalid record')
        active.add(index)
        for child in records[index].children:
            visit(child)
        active.remove(index)
        reached.add(index)

    visit(root)
    return reached


def checked_short_bounds(values):
    if any(v != int(v) or not -32768 <= v <= 32767 for v in values):
        raise ValueError('Translated node/leaf bounds exceed BSP30 short limits')
    return tuple(map(int, values))


def build(base: Path, out: Path):
    if out.resolve() != ALLOWED_OUT.resolve():
        raise ValueError('This bounded build writes only the meadow-visible-creek lab directory')
    data = base.read_bytes()
    if sha(data) != BASE_SHA256:
        raise ValueError('Use the frozen final entrance/creek candidate as the base')
    target = out / 'daragoth_meadow_visible_creek.bsp'
    if target.resolve() == base.resolve() or target.exists():
        raise ValueError('Do not overwrite the frozen base or an existing candidate')
    bsp = BSP.load(base)
    if not bsp.bsp30ext or len(bsp.models) != 164:
        raise ValueError('Expected the reviewed BSP30ext model inventory')
    directory = [struct.unpack_from('<2i', data, 4 + i * 8) for i in range(15)]
    raw = [data[o:o + size] for o, size in directory]
    if len(raw[9]) != len(bsp.clipnodes) * CLIPNODE32.size:
        raise ValueError('Expected the original 32-bit clipnode encoding')
    model = bsp.models[SOURCE_MODEL]
    if model.mins != (-11980., 1420., 96.) or model.maxs != (11980., 2180., 216.):
        raise ValueError('Source creek dimensions changed')
    face_ids = list(range(model.firstface, model.firstface + model.numfaces))
    if len(face_ids) != 20:
        raise ValueError('Expected all twenty original water faces')
    leaf_ids = set()
    node_ids = sorted(closure(bsp.nodes, model.headnode[0], leaf_ids))
    leaf_ids = sorted(leaf_ids)
    clip_ids = sorted(set().union(*(closure(bsp.clipnodes, h) for h in model.headnode[1:])))
    face_set = set(face_ids)
    for n in node_ids:
        node = bsp.nodes[n]
        if not set(range(node.firstface, node.firstface + node.numfaces)) <= face_set:
            raise ValueError('Source render hull references faces outside the creek model')
    for n in leaf_ids:
        leaf = bsp.leafs[n]
        marks = bsp.marksurfaces[leaf.firstmarksurface:leaf.firstmarksurface + leaf.nummarksurfaces]
        if leaf.visofs != -1 or not set(marks) <= face_set:
            raise ValueError('Source water leaf has unexpected visibility or foreign faces')
    edge_ids = sorted({abs(se) for f in face_ids for se in
                       bsp.surfedges[bsp.faces[f].firstedge:bsp.faces[f].firstedge + bsp.faces[f].numedges]})
    vertex_ids = sorted({v for e in edge_ids for v in bsp.edges[e]})
    texinfo_ids = sorted({bsp.faces[f].texinfo for f in face_ids})
    plane_ids = sorted({bsp.faces[f].planenum for f in face_ids} |
                       {bsp.nodes[n].planenum for n in node_ids} |
                       {bsp.clipnodes[n].planenum for n in clip_ids})
    for f in face_ids:
        if bsp.textures[bsp.texinfo[bsp.faces[f].texinfo].miptex].name != '!DPWATER':
            raise ValueError('The animated embedded water texture must be retained')

    def mapping(ids, count):
        return {old: count + i for i, old in enumerate(ids)}

    plane_map = mapping(plane_ids, len(bsp.planes))
    vertex_map = mapping(vertex_ids, len(bsp.vertexes))
    edge_map = mapping(edge_ids, len(bsp.edges))
    texinfo_map = mapping(texinfo_ids, len(bsp.texinfo))
    face_map = mapping(face_ids, len(bsp.faces))
    node_map = mapping(node_ids, len(bsp.nodes))
    leaf_map = mapping(leaf_ids, len(bsp.leafs))
    clip_map = mapping(clip_ids, len(bsp.clipnodes))
    if max(plane_map.values()) >= 65536 or max(vertex_map.values()) >= 65536 or \
       max(face_map.values()) >= 65536 or max(node_map.values()) >= 32768 or \
       max(leaf_map.values()) >= 32768 or max(texinfo_map.values()) >= 32768:
        raise ValueError('Appended model exceeds BSP30 indexed field limits')
    appended = {i: bytearray() for i in CHANGED_LUMPS}
    for n in plane_ids:
        p = bsp.planes[n]
        appended[1].extend(PLANE.pack(*p.normal, p.dist + p.normal[2] * Z_BAKE, p.type))
    for n in vertex_ids:
        appended[3].extend(VERTEX.pack(*shifted(bsp.vertexes[n])))
    for n in texinfo_ids:
        t = bsp.texinfo[n]
        vecs = [v[:3] + [v[3] - v[2] * Z_BAKE] for v in t.vecs]
        appended[6].extend(TEXINFO.pack(*vecs[0], *vecs[1], t.miptex, t.flags))
    for n in edge_ids:
        appended[12].extend(EDGE.pack(*(vertex_map[v] for v in bsp.edges[n])))
    for n in face_ids:
        f = bsp.faces[n]
        firstedge = len(bsp.surfedges) + len(appended[13]) // 4
        for se in bsp.surfedges[f.firstedge:f.firstedge + f.numedges]:
            appended[13].extend(struct.pack('<i', edge_map[abs(se)] * (1 if se >= 0 else -1)))
        appended[7].extend(FACE.pack(plane_map[f.planenum], f.side, firstedge, f.numedges,
                                    texinfo_map[f.texinfo], *f.styles, f.lightofs))
    for n in leaf_ids:
        leaf = bsp.leafs[n]
        firstmark = len(bsp.marksurfaces) + len(appended[11]) // 2
        for face in bsp.marksurfaces[leaf.firstmarksurface:leaf.firstmarksurface + leaf.nummarksurfaces]:
            appended[11].extend(struct.pack('<H', face_map[face]))
        appended[10].extend(LEAF.pack(leaf.contents, leaf.visofs,
                                    *checked_short_bounds(shifted(leaf.mins)),
                                    *checked_short_bounds(shifted(leaf.maxs)),
                                    firstmark, leaf.nummarksurfaces, *leaf.ambient))
    for n in node_ids:
        node = bsp.nodes[n]
        children = [node_map[c] if c >= 0 else -1 - leaf_map[-1 - c] for c in node.children]
        firstface = face_map[node.firstface] if node.numfaces else len(bsp.faces)
        appended[5].extend(NODE.pack(plane_map[node.planenum], *children,
                                    *checked_short_bounds(shifted(node.mins)),
                                    *checked_short_bounds(shifted(node.maxs)), firstface, node.numfaces))
    for n in clip_ids:
        node = bsp.clipnodes[n]
        appended[9].extend(CLIPNODE32.pack(plane_map[node.planenum],
                                         *(clip_map[c] if c >= 0 else c for c in node.children)))
    new_model_index = len(bsp.models)
    new_heads = [node_map[model.headnode[0]], *(clip_map[h] for h in model.headnode[1:])]
    appended[14].extend(MODEL.pack(*shifted(model.mins), *shifted(model.maxs), *model.origin,
                                  *new_heads, model.visleafs, face_map[model.firstface], model.numfaces))

    entities = [Entity([p.copy() for p in e.pairs]) for e in bsp.entities]
    changed_entities = []
    for index, (old, new) in enumerate(zip(bsp.entities, entities)):
        if old.get('model') != '*162':
            continue
        if old.classname != 'func_water' or old.get('targetname') not in {
            'plains_creek_water_00', 'plains_creek_water_01', 'plains_creek_water_02', 'plains_creek_water_03'}:
            raise ValueError('Unexpected user of the source brush model')
        origin = tuple(map(float, old.get('origin').split()))
        if origin[2] != Z_BAKE or old.get('skin') != '-3':
            raise ValueError('Water contents or common translation changed')
        new.set('model', f'*{new_model_index}')
        new.set('origin', ' '.join(f'{v:g}' for v in (origin[0], origin[1], 0)))
        changed_entities.append({'index': index, 'targetname': old.get('targetname'),
                                 'old_origin': list(origin), 'new_origin': [origin[0], origin[1], 0]})
    if len(changed_entities) != 4:
        raise ValueError('Expected exactly four translated water instances')
    appended[0] = bytearray(format_entities(entities))

    # Retain the entire original file. Only descriptors for appended lumps move.
    output = bytearray(data)
    for i in CHANGED_LUMPS:
        output.extend(b'\0' * (-len(output) % 4))
        at = len(output)
        payload = bytes(appended[i]) if i == 0 else raw[i] + bytes(appended[i])
        output.extend(payload)
        struct.pack_into('<2i', output, 4 + i * 8, at, len(payload))
    prefix = bytearray(output[:len(data)])
    for i in CHANGED_LUMPS:
        prefix[4 + i * 8:12 + i * 8] = data[4 + i * 8:12 + i * 8]
    if prefix != data:
        raise ValueError('Original file prefix changed outside the reviewed lump descriptors')
    for i in range(1, 15):
        at, size = struct.unpack_from('<2i', output, 4 + i * 8)
        if output[at:at + len(raw[i])] != raw[i]:
            raise ValueError('An original geometry or collision record was overwritten')

    # Construction proof; independent fluid/render/native verification is separate.
    maximum_vertex_error = maximum_uv_error = 0.0
    for n in vertex_ids:
        source = bsp.vertexes[n]
        compiled = VERTEX.unpack_from(appended[3], (vertex_map[n] - len(bsp.vertexes)) * VERTEX.size)
        maximum_vertex_error = max(maximum_vertex_error, *(abs(compiled[i] - source[i] - (Z_BAKE if i == 2 else 0)) for i in range(3)))
    for n in texinfo_ids:
        source = bsp.texinfo[n]
        compiled = TEXINFO.unpack_from(appended[6], (texinfo_map[n] - len(bsp.texinfo)) * TEXINFO.size)
        for point_id in vertex_ids:
            point = bsp.vertexes[point_id]
            baked = shifted(point)
            for axis in range(2):
                before = sum(point[i] * source.vecs[axis][i] for i in range(3)) + source.vecs[axis][3]
                after = sum(baked[i] * compiled[axis * 4 + i] for i in range(3)) + compiled[axis * 4 + 3]
                maximum_uv_error = max(maximum_uv_error, abs(before - after))
    if maximum_vertex_error > .0001 or maximum_uv_error > .0001:
        raise ValueError('Geometry or authored UVs changed during baking')
    if sha(base.read_bytes()) != BASE_SHA256:
        raise ValueError('Frozen base changed during construction')
    out.mkdir(parents=True, exist_ok=True)
    target.write_bytes(output)
    report = {
        'base_sha256': BASE_SHA256, 'output_sha256': sha(output), 'output_path': str(target.resolve()),
        'source_builder_sha256': sha(Path(__file__).read_bytes()), 'z_bake': Z_BAKE,
        'source_model': SOURCE_MODEL, 'new_model': new_model_index,
        'source_model_headnodes': model.headnode, 'new_model_headnodes': new_heads,
        'source_model_bounds': [list(model.mins), list(model.maxs)],
        'new_model_bounds': [list(shifted(model.mins)), list(shifted(model.maxs))],
        'model_origin_preserved': True, 'changed_entities': changed_entities,
        'total_entities': len(entities), 'other_entities_preserved': len(entities) - 4,
        'original_lump_prefixes_preserved': {str(i): True for i in range(1, 15)},
        'immutable_lumps_identical': {str(i): True for i in (2, 4, 8)},
        'original_file_prefix_preserved_except_descriptors': True,
        'world_model_and_collision_topology_preserved': True,
        'appended_counts': {k: len(v) for k, v in
                            {'planes': plane_ids, 'vertices': vertex_ids, 'edges': edge_ids,
                             'texinfos': texinfo_ids, 'faces': face_ids, 'render_nodes': node_ids,
                             'leaves': leaf_ids, 'clipnodes': clip_ids}.items()},
        'index_maps': {k: {str(a): z for a, z in v.items()} for k, v in
                       {'planes': plane_map, 'vertices': vertex_map, 'edges': edge_map,
                        'texinfos': texinfo_map, 'faces': face_map, 'render_nodes': node_map,
                        'leaves': leaf_map, 'clipnodes': clip_map}.items()},
        'maximum_baked_vertex_error': maximum_vertex_error, 'maximum_uv_error': maximum_uv_error,
        'water_texture': '!DPWATER', 'embedded_texture_lump_preserved': True,
        'face_lightmap_descriptors_preserved': True, 'turbulent_animation_retained': True,
        'renderer_top_test': {'world_model_min_z_plus_one': model.mins[2] + Z_BAKE + 1,
                              'local_top_plane_dist': model.maxs[2] + Z_BAKE,
                              'passes': model.mins[2] + 1 < model.maxs[2]},
        'requires_independent_fluid_equivalence': True, 'requires_native_visual_verification': True,
    }
    (out / 'visible-creek-build-report.json').write_text(json.dumps(report, indent=2) + '\n')
    if sha(base.read_bytes()) != BASE_SHA256 or sha(target.read_bytes()) != report['output_sha256']:
        raise ValueError('Build inputs or output changed during freezing')
    print(json.dumps({k: report[k] for k in ('output_sha256', 'new_model', 'appended_counts', 'renderer_top_test')}, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    build(args.base, args.out)
