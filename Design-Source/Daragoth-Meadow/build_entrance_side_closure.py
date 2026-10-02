"""Close the two absent surfaces of the original gateway's sixteen-unit post.

The pictured thin blade is the north cap of an existing SOLID post. Its east
side and top have collision planes, but their render nodes own no faces. Add
only those exact faces to the frozen six-door candidate. Every old world,
water and door polygon, collision tree, PVS row and entity remains preserved.
No map compiler, game process or runtime directory is used.
"""
from __future__ import annotations

import argparse
from bisect import bisect_right
import copy
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'Packaging-Work/BigWorld/tools'))
from bsp30 import BSP, Face, TexInfo, VERTEX, NODE, TEXINFO, FACE, LEAF, EDGE, MODEL

BASE_SHA = '9a8e78380ee79271a911749d089fb1576a1f6f3ef54bb3f0e360ad91f200f2d6'
CHANGED = (3, 5, 6, 7, 8, 10, 11, 12, 13, 14)
SOURCE_ROCK_FACE = 119
SPECS = (
    {'label': 'gateway_post_top', 'node': 64, 'plane': 1354, 'side': 0,
     'insert_at': 75, 'empty_leaf': 30, 'axis': 2, 'outward_sign': 1,
     'points': [(1920., 3088., 3336.), (1920., 3216., 3336.),
                (1936., 3216., 3336.), (1936., 3088., 3336.)]},
    {'label': 'gateway_post_east', 'node': 79, 'plane': 7250, 'side': 0,
     'insert_at': 120, 'empty_leaf': 36, 'axis': 0, 'outward_sign': 1,
     'points': [(1936., 3088., 3072.), (1936., 3088., 3336.),
                (1936., 3216., 3336.), (1936., 3216., 3072.)]},
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def polygon(bsp, face):
    return [bsp.vertexes[bsp.edges[abs(s)][0 if s >= 0 else 1]]
            for s in bsp.surfedges[face.firstedge:face.firstedge + face.numedges]]


def leaf_at(bsp, point):
    n = bsp.models[0].headnode[0]
    while n >= 0:
        node = bsp.nodes[n]
        plane = bsp.planes[node.planenum]
        d = sum(point[k] * plane.normal[k] for k in range(3)) - plane.dist
        n = node.children[0 if d >= 0 else 1]
    return -n - 1


def light_step(bsp, face):
    index = (bsp.texinfo[face.texinfo].flags >> 16) & 65535
    raw = bsp.extra_lumps.get(1, b'')
    if index != 65535 and index * 22 + 22 <= len(raw):
        return struct.unpack_from('<H', raw, index * 22 + 16)[0]
    return 16


def extents(bsp, face):
    ti = bsp.texinfo[face.texinfo]
    points = polygon(bsp, face)
    step = light_step(bsp, face)
    uv = [[sum(v[k] * vec[k] for k in range(3)) + vec[3] for v in points]
          for vec in ti.vecs]
    return [(math.floor(min(a) / step), math.ceil(max(a) / step)) for a in uv]


def area_vector(points):
    return [sum(a[(k+1)%3] * b[(k+2)%3] - a[(k+2)%3] * b[(k+1)%3]
                for a, b in zip(points, points[1:] + points[:1])) / 2
            for k in range(3)]


def validate_empty_solid_rectangle(bsp, spec):
    axis = spec['axis']
    remaining = [k for k in range(3) if k != axis]
    points = spec['points']
    coordinate = points[0][axis]
    ranges = [range(round(min(p[k] for p in points)) + 4,
                    round(max(p[k] for p in points)), 8) for k in remaining]
    count = 0
    for a in ranges[0]:
        for b in ranges[1]:
            p = [0., 0., 0.]
            p[axis], p[remaining[0]], p[remaining[1]] = coordinate, a, b
            inside, outside = p.copy(), p.copy()
            inside[axis] -= .01 * spec['outward_sign']
            outside[axis] += .01 * spec['outward_sign']
            li, lo = leaf_at(bsp, inside), leaf_at(bsp, outside)
            if bsp.leafs[li].contents != -2 or lo != spec['empty_leaf'] or bsp.leafs[lo].contents != -1:
                raise ValueError(f"Unexpected gateway interface at {p}: {li}/{lo}")
            count += 1
    normal = bsp.planes[spec['plane']].normal
    winding = sum(area_vector(points)[k] * normal[k] for k in range(3))
    if winding >= 0:
        raise ValueError('New brush face must use the stock clockwise outward winding')
    for i in range(bsp.models[0].numfaces):
        face = bsp.faces[i]
        effective = bsp.planes[face.planenum].normal[axis] * (-1 if face.side else 1)
        old = polygon(bsp, face)
        if effective < .999 or not all(abs(p[axis] - coordinate) < .001 for p in old):
            continue
        # Existing coplanar faces have disjoint boxes; an overlap must be audited.
        if all(min(p[k] for p in old) < max(p[k] for p in points) - .001 and
               max(p[k] for p in old) > min(p[k] for p in points) + .001 for k in remaining):
            raise ValueError(f'Unexpected overlapping old surface {i}')
    return count


def build(base, out):
    source = base.read_bytes()
    if sha(source) != BASE_SHA:
        raise ValueError('Use the frozen six-house door candidate')
    target = out / 'daragoth_meadow_entrance_closed.bsp'
    report_path = out / 'entrance-side-closure-build-report.json'
    if target.exists() or report_path.exists() or target.resolve() == base.resolve():
        raise ValueError('Keep frozen candidates and reports immutable')
    before = BSP.load(base)
    bsp = copy.deepcopy(before)
    if len(bsp.entities) != 1053 or len(bsp.models) != 166:
        raise ValueError('Six new doors and every preceding entity/model are required')
    source_face = bsp.faces[SOURCE_ROCK_FACE]
    source_ti = bsp.texinfo[source_face.texinfo]
    if source_face.texinfo != 14 or bsp.textures[source_ti.miptex].name != 'rock01a_ewok':
        raise ValueError('Adjacent embedded original rock changed')
    if light_step(bsp, source_face) != 16 or source_face.styles != [0, 255, 255, 255]:
        raise ValueError('Adjacent rock must have ordinary sixteen-unit style0 RGB lighting')
    source_ext = extents(bsp, source_face)
    source_samples = math.prod(hi - lo + 1 for lo, hi in source_ext)
    source_rgb = bsp.lighting[source_face.lightofs:source_face.lightofs + source_samples * 3]
    if len(source_rgb) != source_samples * 3:
        raise ValueError('Adjacent rock lightmap is incomplete')
    rgb = bytes(round(sum(source_rgb[k::3]) / source_samples) for k in range(3))
    light = bytearray(bsp.lighting)
    added = []
    for spec in SPECS:
        node = bsp.nodes[spec['node']]
        if node.planenum != spec['plane'] or node.numfaces:
            raise ValueError('The diagnosed empty face owner changed')
        probes = validate_empty_solid_rectangle(bsp, spec)
        s, t = source_ti.vecs
        if spec['axis'] == 0:
            # Align S with the adjoining Y3088 wall at the X1936 corner.
            vecs = [[0., s[0], 0., s[3] + s[0] * (1936. - 3088.)], list(t)]
        else:
            # The horizontal top shares the source wall's upper-edge UV corner.
            vecs = [list(s), [0., t[2], 0., t[3] + t[2] * (3336. - 3088.)]]
        ti = len(bsp.texinfo)
        bsp.texinfo.append(TexInfo(vecs, source_ti.miptex, -65536))
        ids = []
        for point in spec['points']:
            ids.append(len(bsp.vertexes))
            bsp.vertexes.append(point)
        first = len(bsp.surfedges)
        for a, b in zip(ids, ids[1:] + ids[:1]):
            bsp.surfedges.append(len(bsp.edges))
            bsp.edges.append((a, b))
        face = Face(spec['plane'], spec['side'], first, len(ids), ti,
                    [0, 255, 255, 255], len(light))
        extent = extents(bsp, face)
        dimensions = [hi - lo + 1 for lo, hi in extent]
        light.extend(rgb * math.prod(dimensions))
        added.append((spec, face, {'label': spec['label'], 'owner_node': spec['node'],
                       'plane': spec['plane'], 'side': spec['side'],
                       'points': [list(p) for p in spec['points']],
                       'area': math.sqrt(sum(v*v for v in area_vector(spec['points']))),
                       'source_insert_at': spec['insert_at'], 'source_empty_leaf': spec['empty_leaf'],
                       'texinfo': ti, 'lightofs': face.lightofs, 'lightmap_dimensions': dimensions,
                       'lightmap_rgb': list(rgb), 'lightmap_step': 16,
                       'empty_solid_interface_grid8_samples': probes}))
    cuts = sorted(spec['insert_at'] for spec in SPECS)
    face_map = [i + bisect_right(cuts, i) for i in range(len(before.faces))]
    bsp.faces = []
    added_by_cut = {spec['insert_at']: (spec, face, meta) for spec, face, meta in added}
    for i, face in enumerate(before.faces):
        if i in added_by_cut:
            spec, new, meta = added_by_cut[i]
            meta['face'] = len(bsp.faces)
            bsp.faces.append(new)
        bsp.faces.append(copy.deepcopy(face))
    for node in bsp.nodes:
        if node.numfaces:
            node.firstface = face_map[node.firstface]
    for spec, _, meta in added:
        node = bsp.nodes[spec['node']]
        node.firstface, node.numfaces = meta['face'], 1
    for i, model in enumerate(bsp.models):
        if i == 0:
            model.numfaces += len(added)
        elif model.numfaces:
            model.firstface = face_map[model.firstface]
    holders = {}
    for spec, _, meta in added:
        own = {1, 3541, spec['empty_leaf']}
        meta['marking_leaves'] = sorted(own)
        for i in own:
            holders.setdefault(i, []).append(meta['face'])
    old_marks = bsp.marksurfaces
    bsp.marksurfaces = []
    enlarged = {}
    for i, leaf in enumerate(bsp.leafs):
        marks = [face_map[f] for f in old_marks[leaf.firstmarksurface:leaf.firstmarksurface+leaf.nummarksurfaces]]
        extra = holders.get(i, [])
        marks.extend(extra)
        leaf.firstmarksurface, leaf.nummarksurfaces = len(bsp.marksurfaces), len(marks)
        bsp.marksurfaces.extend(marks)
        if extra:
            points = [p for f in extra for p in polygon(bsp, bsp.faces[f])]
            leaf.mins = tuple(min(leaf.mins[k], math.floor(min(p[k] for p in points))) for k in range(3))
            leaf.maxs = tuple(max(leaf.maxs[k], math.ceil(max(p[k] for p in points))) for k in range(3))
            enlarged[-i-1] = (leaf.mins, leaf.maxs)
        if leaf.firstmarksurface >= 65536 or leaf.nummarksurfaces >= 65536:
            raise ValueError('Leaf marks exceed the BSP30 index budget')
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
            new_lo = tuple(min(node.mins[k], lo[k]) for k in range(3))
            new_hi = tuple(max(node.maxs[k], hi[k]) for k in range(3))
            if (node.mins, node.maxs) != (new_lo, new_hi):
                node.mins, node.maxs = new_lo, new_hi
                enlarged[i] = (new_lo, new_hi)
                pending.append(i)
    bsp.lighting = bytes(light)
    if max(len(bsp.faces), len(bsp.vertexes)) >= 65536:
        raise ValueError('Faces or vertices exceed the BSP30 index budget')
    for i, old in enumerate(before.faces):
        if bsp.faces[face_map[i]] != old:
            raise ValueError(f'Old face {i} changed')
    if any((a.planenum, a.children) != (b.planenum, b.children) for a,b in zip(before.nodes,bsp.nodes)):
        raise ValueError('World collision topology changed')
    if any(a.headnode != b.headnode for a,b in zip(before.models,bsp.models)):
        raise ValueError('A world/water/door collision head changed')
    if any((a.contents,a.visofs,a.ambient) != (b.contents,b.visofs,b.ambient) for a,b in zip(before.leafs,bsp.leafs)):
        raise ValueError('A leaf content or PVS record changed')
    changed = {
        3: b''.join(VERTEX.pack(*v) for v in bsp.vertexes),
        5: b''.join(NODE.pack(n.planenum,*n.children,*n.mins,*n.maxs,n.firstface,n.numfaces) for n in bsp.nodes),
        6: b''.join(TEXINFO.pack(*t.vecs[0],*t.vecs[1],t.miptex,t.flags) for t in bsp.texinfo),
        7: b''.join(FACE.pack(f.planenum,f.side,f.firstedge,f.numedges,f.texinfo,*f.styles,f.lightofs) for f in bsp.faces),
        8: bsp.lighting,
        10: b''.join(LEAF.pack(l.contents,l.visofs,*l.mins,*l.maxs,l.firstmarksurface,l.nummarksurfaces,*l.ambient) for l in bsp.leafs),
        11: struct.pack(f'<{len(bsp.marksurfaces)}H',*bsp.marksurfaces),
        12: b''.join(EDGE.pack(*e) for e in bsp.edges),
        13: struct.pack(f'<{len(bsp.surfedges)}i',*bsp.surfedges),
        14: b''.join(MODEL.pack(*m.mins,*m.maxs,*m.origin,*m.headnode,m.visleafs,m.firstface,m.numfaces) for m in bsp.models),
    }
    output = bytearray(source)
    for i, blob in changed.items():
        output.extend(b'\0' * (-len(output) % 4))
        offset = len(output)
        output.extend(blob)
        struct.pack_into('<2i', output, 4+8*i, offset, len(blob))
    if sha(base.read_bytes()) != BASE_SHA:
        raise ValueError('Frozen input changed during construction')
    prefix = bytearray(output[:len(source)])
    for i in CHANGED:
        prefix[4+8*i:12+8*i] = source[4+8*i:12+8*i]
    if prefix != source:
        raise ValueError('Original file prefix changed outside render descriptors')
    out.mkdir(parents=True, exist_ok=True)
    target.write_bytes(output)
    report = {'base_path':str(base.resolve()), 'base_sha256':BASE_SHA,
              'output_path':str(target.resolve()), 'output_sha256':sha(output),
              'source_builder_sha256':sha(Path(__file__).read_bytes()),
              'changed_lumps':list(CHANGED), 'added_faces':[meta for _,_,meta in added],
              'old_face_index_map':face_map, 'original_face_count':len(before.faces),
              'output_face_count':len(bsp.faces), 'ordered_entity_count':len(bsp.entities),
              'material':'rock01a_ewok', 'source_rock_face':SOURCE_ROCK_FACE,
              'source_texinfo':source_face.texinfo, 'lighting_policy':'adjacent_style0_rgb_mean',
              'all_old_faces_exact_after_remap':True, 'all_entities_byte_identical':True,
              'all_collision_planes_clipnodes_heads_and_topology_preserved':True,
              'pvs_bytes_and_leaf_contents_preserved':True,
              'all_old_world_water_bed_and_door_geometry_preserved':True,
              'original_file_prefix_preserved_except_render_descriptors':True,
              'door_model':165, 'door_firstface_before':before.models[165].firstface,
              'door_firstface_after':bsp.models[165].firstface,
              'requires_independent_qa_and_native_visual_review':True}
    report_path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('output_path','output_sha256','added_faces',
                                          'door_firstface_before','door_firstface_after')},indent=2))
    return report


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    build(args.base.resolve(),args.out.resolve())
