"""Independent render-only QA of the original gateway post's side and top.

This checker does not import the builder. It verifies exact old data, the two
independently specified physical interfaces, front winding, UV/lightmaps and
visibility marks. No game, compiler or motion test is launched. A fresh native
visual verdict remains separate from this static preservation receipt.
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

REPO = Path(__file__).resolve().parents[1]
PARSER = REPO / 'Packaging-Work/BigWorld/tools/bsp30.py'
sys.path.insert(0, str(PARSER.parent))
from bsp30 import BSP

BASE_SHA = '9a8e78380ee79271a911749d089fb1576a1f6f3ef54bb3f0e360ad91f200f2d6'
BSP_SHA = '77611d302aa1cf309550a517bed2c169388986341ff3bd02f06b5e1e8acdb4d7'
REPORT_SHA = '6c75b8e03c9dddd521deb96c187f5c89a54798d5393cdeec7b1c86fcccba4229'
BUILDER_SHA = '95659d43025a0f058e903fd69538c57d42851d9731f5884c6b3e57f3af8aae15'
CHANGED = {3, 5, 6, 7, 8, 10, 11, 12, 13, 14}
TARGETS = {
    75: {'node': 64, 'plane': 1354, 'axis': 2, 'coord': 3336., 'leaf': 30,
         'points': {(1920., 3088., 3336.), (1920., 3216., 3336.),
                    (1936., 3216., 3336.), (1936., 3088., 3336.)},
         'area': 2048., 'samples': 32, 'dimensions': [3, 9]},
    121: {'node': 79, 'plane': 7250, 'axis': 0, 'coord': 1936., 'leaf': 36,
          'points': {(1936., 3088., 3072.), (1936., 3088., 3336.),
                     (1936., 3216., 3336.), (1936., 3216., 3072.)},
          'area': 33792., 'samples': 528, 'dimensions': [12, 14]},
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def section():
    return {'failure_count': 0, 'failures': []}


def check(result, condition, message, **details):
    if not condition:
        result['failure_count'] += 1
        if len(result['failures']) < 25:
            result['failures'].append({'message': message, **details})


def finish(result):
    result['pass'] = result['failure_count'] == 0
    return result


def lump(raw, index):
    offset, size = struct.unpack_from('<2i', raw, 4 + index * 8)
    if offset < 0 or size < 0 or offset + size > len(raw):
        raise ValueError('Invalid BSP lump range')
    return raw[offset:offset + size]


def mapped(index):
    return index + (index >= 75) + (index >= 120)


def points(bsp, face):
    return [tuple(bsp.vertexes[bsp.edges[abs(s)][0 if s >= 0 else 1]])
            for s in bsp.surfedges[face.firstedge:face.firstedge + face.numedges]]


def area_vector(poly):
    return tuple(sum(a[(k + 1) % 3] * b[(k + 2) % 3] -
                     a[(k + 2) % 3] * b[(k + 1) % 3]
                     for a, b in zip(poly, poly[1:] + poly[:1])) / 2
                 for k in range(3))


def leaf_at(bsp, point):
    node = bsp.models[0].headnode[0]
    visited = 0
    while node >= 0:
        visited += 1
        if visited > len(bsp.nodes):
            raise ValueError('Cyclic BSP node tree')
        n = bsp.nodes[node]
        p = bsp.planes[n.planenum]
        distance = (point[p.type] - p.dist if p.type < 3 else
                    sum(point[k] * p.normal[k] for k in range(3)) - p.dist)
        node = n.children[0 if distance >= 0 else 1]
    return -node - 1


def projected_inside(poly, point, axis):
    axes = [k for k in range(3) if k != axis]
    u, v = axes
    crosses = [(b[u] - a[u]) * (point[v] - a[v]) -
               (b[v] - a[v]) * (point[u] - a[u])
               for a, b in zip(poly, poly[1:] + poly[:1])]
    return min(crosses) >= -.0001 or max(crosses) <= .0001


def coplanar_fronts(bsp, spec):
    matches = []
    for i in range(bsp.models[0].firstface,
                   bsp.models[0].firstface + bsp.models[0].numfaces):
        f = bsp.faces[i]
        p = bsp.planes[f.planenum]
        sign = -1 if f.side else 1
        if p.normal[spec['axis']] * sign < .999:
            continue
        poly = points(bsp, f)
        if all(abs(v[spec['axis']] - spec['coord']) < .001 for v in poly):
            matches.append((i, poly))
    return matches


def uv(vecs, point):
    return [sum(point[k] * v[k] for k in range(3)) + v[3] for v in vecs]


def dimensions(bsp, face):
    values = [uv(bsp.texinfo[face.texinfo].vecs, p) for p in points(bsp, face)]
    return [math.ceil(max(v[k] for v in values) / 16) -
            math.floor(min(v[k] for v in values) / 16) + 1 for k in range(2)]


def verify(base, candidate, build_report):
    builder = REPO / 'Design-Source/Daragoth-Meadow/build_entrance_side_closure.py'
    inputs = {'base': base, 'bsp': candidate, 'report_source': build_report,
              'builder_source': builder, 'parser_source': PARSER,
              'checker_source': Path(__file__)}
    hashes = {key: digest(path) for key, path in inputs.items()}
    metadata, preservation, geometry, lighting = [section() for _ in range(4)]
    for key, expected in [('base', BASE_SHA), ('bsp', BSP_SHA),
                          ('report_source', REPORT_SHA), ('builder_source', BUILDER_SHA)]:
        check(metadata, hashes[key] == expected, 'Frozen input hash mismatch', input=key)
    declared = json.loads(build_report.read_text())
    check(metadata, declared['base_sha256'] == hashes['base'] and
          declared['output_sha256'] == hashes['bsp'] and
          declared['source_builder_sha256'] == hashes['builder_source'],
          'Build report hashes do not identify the actual files')
    check(metadata, declared['old_face_index_map'] ==
          [mapped(i) for i in range(declared['original_face_count'])],
          'Reported remap differs from independently specified two cuts')
    old, new = BSP.load(base), BSP.load(candidate)
    before, after = base.read_bytes(), candidate.read_bytes()
    immutable = {str(i): lump(before, i) == lump(after, i)
                 for i in range(15) if i not in CHANGED}
    for i, same in immutable.items():
        check(preservation, same, 'Entity/collision/PVS/texture bytes changed', lump=i)
    prefix = bytearray(after[:len(before)])
    for i in CHANGED:
        prefix[4 + 8 * i:12 + 8 * i] = before[4 + 8 * i:12 + 8 * i]
    check(preservation, prefix == before,
          'Original file or XASH extras changed outside render descriptors')
    for i in (3, 6, 8, 12, 13):
        check(preservation, lump(after, i).startswith(lump(before, i)),
              'Old render primitive/light prefix changed', lump=i)
    deltas = {'vertexes': 8, 'texinfo': 2, 'edges': 8, 'surfedges': 8,
              'faces': 2, 'marksurfaces': 6, 'nodes': 0, 'leafs': 0, 'models': 0}
    for name, added in deltas.items():
        check(preservation, len(getattr(new, name)) == len(getattr(old, name)) + added,
              'Unexpected record count delta', record=name)
    check(preservation, len(new.entities) == 1053 and
          [e.pairs for e in old.entities] == [e.pairs for e in new.entities],
          'Ordered entity inventory changed')
    check(preservation, new.extra_lumps == old.extra_lumps, 'XASH extra data changed')
    for i, f in enumerate(old.faces):
        check(preservation, new.faces[mapped(i)] == f,
              'Old face geometry/material/light descriptor changed', source_face=i)
    for i, (a, b) in enumerate(zip(old.nodes, new.nodes)):
        expected_range = ((75, 1) if i == 64 else (121, 1) if i == 79 else
                          (mapped(a.firstface) if a.numfaces else a.firstface, a.numfaces))
        check(preservation, (a.planenum, a.children, a.mins, a.maxs) ==
              (b.planenum, b.children, b.mins, b.maxs) and
              (b.firstface, b.numfaces) == expected_range,
              'Node topology/bounds or remapped face ownership changed', node=i)
    references = Counter()
    expected_holders = {1: [75, 121], 30: [75], 36: [121], 3541: [75, 121]}
    for i, (a, b) in enumerate(zip(old.leafs, new.leafs)):
        check(preservation, (a.contents, a.visofs, a.mins, a.maxs, a.ambient) ==
              (b.contents, b.visofs, b.mins, b.maxs, b.ambient),
              'Leaf contents/PVS/bounds/ambient changed', leaf=i)
        expected_marks = [mapped(fi) for fi in old.marksurfaces[
            a.firstmarksurface:a.firstmarksurface + a.nummarksurfaces]] + expected_holders.get(i, [])
        actual_marks = new.marksurfaces[b.firstmarksurface:b.firstmarksurface + b.nummarksurfaces]
        check(preservation, actual_marks == expected_marks, 'Leaf marks differ from exact ordered remap/additions', leaf=i)
        references.update(fi for fi in actual_marks if fi in TARGETS)
    check(preservation, references == Counter({75: 3, 121: 3}), 'New visibility mark references differ')
    for i, (a, b) in enumerate(zip(old.models, new.models)):
        check(preservation, (a.mins, a.maxs, a.origin, a.headnode, a.visleafs) ==
              (b.mins, b.maxs, b.origin, b.headnode, b.visleafs) and
              b.firstface == (mapped(a.firstface) if a.numfaces else a.firstface) and
              b.numfaces == a.numfaces + (2 if i == 0 else 0),
              'Old model bounds/heads/face range changed', model=i)
    check(preservation, new.models[165].firstface == 21067 and new.models[165].numfaces == 6,
          'Shared six-house door model did not retain its exact geometry range')
    check(preservation, all(e.get('model') == '*165' for e in new.entities[1047:1053]),
          'Six house-door model references changed')
    check(metadata, declared['ordered_entity_count'] == len(new.entities) and
          declared['output_face_count'] == len(new.faces), 'Reported counts differ')
    source = old.faces[119]
    source_ti = old.texinfo[source.texinfo]
    source_size = math.prod(dimensions(old, source))
    source_rgb = old.lighting[source.lightofs:source.lightofs + 3 * source_size]
    color = [round(sum(source_rgb[k::3]) / source_size) for k in range(3)]
    check(lighting, source.texinfo == 14 and source.styles == [0, 255, 255, 255]
          and len(source_rgb) == 3 * source_size and color == [137, 135, 125],
          'Independent adjacent-rock mean or source lighting differs')
    next_light = len(old.lighting)
    surveys = {}
    for index, spec in TARGETS.items():
        f = new.faces[index]
        poly = points(new, f)
        pl = new.planes[f.planenum]
        normal = tuple(1. if k == spec['axis'] else 0. for k in range(3))
        check(geometry, f.planenum == spec['plane'] and f.side == 0 and
              pl.normal == normal and pl.dist == spec['coord'] and
              len(poly) == 4 and set(poly) == spec['points'],
              'New face is not the exact independently diagnosed rectangle', face=index)
        av = area_vector(poly)
        check(geometry, abs(av[spec['axis']] + spec['area']) < .001 and
              all(abs(av[k]) < .001 for k in range(3) if k != spec['axis']),
              'New clockwise front winding/area differs', face=index)
        for holder in [spec['node']]:
            node = new.nodes[holder]
            check(geometry, all(node.mins[k] <= p[k] <= node.maxs[k]
                  for p in poly for k in range(3)), 'Face outside owner-node bounds', face=index)
        for li in [1, 3541, spec['leaf']]:
            leaf = new.leafs[li]
            check(geometry, all(leaf.mins[k] <= p[k] <= leaf.maxs[k]
                  for p in poly for k in range(3)), 'Face outside visibility-holder bounds', face=index, leaf=li)
        a, b = [k for k in range(3) if k != spec['axis']]
        fronts_old, fronts_new = coplanar_fronts(old, spec), coplanar_fronts(new, spec)
        count, misses_before, misses_after = 0, 0, 0
        for u in range(round(min(p[a] for p in poly)) + 4, round(max(p[a] for p in poly)), 8):
            for v in range(round(min(p[b] for p in poly)) + 4, round(max(p[b] for p in poly)), 8):
                p = [0., 0., 0.]
                p[spec['axis']], p[a], p[b] = spec['coord'], float(u), float(v)
                inner, outer = p.copy(), p.copy()
                inner[spec['axis']] -= .01
                outer[spec['axis']] += .01
                li, lo = leaf_at(old, inner), leaf_at(old, outer)
                check(geometry, old.leafs[li].contents == -2 and lo == spec['leaf'] and
                      old.leafs[lo].contents == -1 and leaf_at(new, inner) == li and leaf_at(new, outer) == lo,
                      'Physical interface or new contents differs', face=index, point=p)
                previous = [fi for fi, pts in fronts_old if projected_inside(pts, p, spec['axis'])]
                current = [fi for fi, pts in fronts_new if projected_inside(pts, p, spec['axis'])]
                misses_before += not previous
                misses_after += not current
                check(geometry, not previous and current == [index],
                      'Missing interface not covered exactly once', face=index, point=p,
                      before=previous, after=current)
                count += 1
        check(geometry, count == spec['samples'] and misses_before == count and misses_after == 0,
              'Expected independent eight-unit coverage survey differs', face=index)
        surveys[str(index)] = {'samples': count, 'missing_before': misses_before,
                              'missing_after': misses_after, 'area': spec['area']}
        ti = new.texinfo[f.texinfo]
        texture = new.textures[ti.miptex]
        dims = dimensions(new, f)
        size = math.prod(dims) * 3
        check(lighting, texture.name == 'rock01a_ewok' and texture.raw and not texture.external and
              ti.miptex == source_ti.miptex and ti.flags == -65536 and
              all(abs(sum(vec[k] * normal[k] for k in range(3))) < .0001 for vec in ti.vecs),
              'Original embedded rock/tangent UV/default16 sentinel differs', face=index)
        check(lighting, dims == spec['dimensions'] and f.styles == [0, 255, 255, 255] and
              f.lightofs == next_light and new.lighting[f.lightofs:f.lightofs + size] == bytes(color) * math.prod(dims),
              'New style0 lightmap extents/offset/RGB differs', face=index)
        # Independent corner continuity with the existing south wall at Y3088.
        corner = (1936., 3088., 3336.)
        check(lighting, max(abs(a - b) for a, b in zip(uv(ti.vecs, corner), uv(source_ti.vecs, corner))) < .0003,
              'Texture phase differs at the shared upper corner', face=index)
        next_light += size
    check(lighting, next_light == len(new.lighting), 'Unaccounted appended lighting bytes')
    unchanged = all(digest(path) == hashes[key] for key, path in inputs.items())
    preservation.update({'immutable_lumps_identical': immutable,
                         'original_file_prefix_preserved_except_render_descriptors': prefix == before,
                         'entities_preserved': len(new.entities), 'models_headnodes_preserved': len(new.models),
                         'collision_nodes_preserved': len(new.nodes), 'leaves_preserved': len(new.leafs),
                         'old_faces_exact_after_remap': len(old.faces), 'door_model': 165,
                         'door_geometry_and_all_angle_states_preserved_by_exact_local_geometry_and_hulls': True,
                         'water_and_grass_entity_records_preserved': lump(before, 0) == lump(after, 0)})
    geometry.update({'added_faces': 2, 'coverage_surveys': surveys,
                     'holder_leaves': expected_holders, 'world_motion_traces_repeated': False})
    lighting.update({'material': 'rock01a_ewok', 'rgb': color, 'lightmap_step': 16,
                     'appended_rgb_bytes': len(new.lighting) - len(old.lighting)})
    result = {'schema': 'independent-entrance-side-closure-static-qa-v1',
              'input_sha256': {k: hashes[k] for k in ('base', 'bsp', 'report_source')},
              'builder_source_sha256': hashes['builder_source'],
              'checker_source_sha256': hashes['checker_source'],
              'checker_dependency_sha256': {str(PARSER): hashes['parser_source']},
              'metadata': finish(metadata), 'preservation': finish(preservation),
              'geometry': finish(geometry), 'lighting': finish(lighting),
              'inputs_unchanged_during_verification': unchanged,
              'actual_c': {'status': 'not_requested', 'pass': None,
                           'scope': 'Collision planes/clipnodes/world nodes/model heads are identical; no new motion trace needed.'},
              'native_visual_acceptance': None}
    result['static_pass'] = unchanged and all(result[k]['pass'] for k in
                                               ('metadata', 'preservation', 'geometry', 'lighting'))
    result['pass'] = result['static_pass']
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--bsp', type=Path, required=True)
    parser.add_argument('--build-report', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists() or args.report.resolve() in {
            p.resolve() for p in (args.base, args.bsp, args.build_report, Path(__file__))}:
        raise ValueError('Write only a new receipt; do not overwrite evidence')
    result = verify(args.base, args.bsp, args.build_report)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open('x', encoding='utf-8') as output:
        output.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in
                      ('pass', 'static_pass', 'input_sha256', 'checker_source_sha256')}, indent=2))
    sys.exit(0 if result['pass'] else 1)
