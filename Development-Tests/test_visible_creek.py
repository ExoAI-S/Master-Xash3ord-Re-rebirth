"""Independently audit the appended water model that fixes stock rendering.

All original geometry, collision records and world data must remain exact
prefixes. Four existing water instances switch to a model with baked Z2720
and entity Z0; their world mesh, UVs and float32 fluid overlay must agree.
The renderer selection check replays gl_rsurf.c rather than trusting a build
claim. Native appearance and waterlevel still require separate game evidence.
"""
from __future__ import annotations

import argparse
from collections import Counter
import copy
import json
import math
from pathlib import Path
import random
import struct
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / 'Packaging-Work/BigWorld/tools'),
               str(REPO / 'Design-Source/Daragoth-Meadow')]
from bsp30 import BSP
from meadow_surface import SurfaceIndex
from test_meadow_creek import (actual_c, brush_contents, contents, creek, f32,
                               fail, finish, section, sha, solid_floor, vec,
                               world_contents)

BASE_SHA = '827f22e886c679f44cdfe8584d339feae841e49b9f43e4ec2da3fb2949b26cf8'
CANDIDATE_SHA = '22288e02f3b9b83a2f6bcb4bcebd05fefba3bb86460469ce11ec67525c6ea0f3'
SOURCE_REPORT_SHA = '44e3bccb930b25fdad1176803a52b874288ce7f367d9bb413f7c7c64def9b4cc'
Z_BAKE = 2720.0
SOURCE_MODEL, NEW_MODEL = 162, 164
CHANGED_LUMPS = (0, 1, 3, 5, 6, 7, 9, 10, 11, 12, 13, 14)
GROUND_TEXTURES = ('DPGRASS', 'DPPATH', 'DPDIRT')


def translated(point):
    return (point[0], point[1], point[2] + Z_BAKE)


def polygon(bsp, index):
    f = bsp.faces[index]
    return [bsp.vertexes[bsp.edges[abs(e)][0 if e >= 0 else 1]]
            for e in bsp.surfedges[f.firstedge:f.firstedge + f.numedges]]


def reached(records, head, leaf_indices=None):
    found, active = set(), set()

    def visit(n):
        if n < 0:
            if leaf_indices is not None:
                leaf_indices.add(-1 - n)
            return
        if n in active or n >= len(records):
            raise ValueError('Invalid or cyclic source hull')
        if n in found:
            return
        active.add(n)
        for child in records[n].children:
            visit(child)
        active.remove(n)
        found.add(n)

    visit(head)
    return found


def independent_maps(old):
    """Derive the clone inventory from compiled source, without builder code."""
    m = old.models[SOURCE_MODEL]
    faces = set(range(m.firstface, m.firstface + m.numfaces))
    leaves = set()
    nodes = reached(old.nodes, m.headnode[0], leaves)
    clips = set().union(*(reached(old.clipnodes, h) for h in m.headnode[1:]))
    edges = {abs(e) for i in faces for e in old.surfedges[
        old.faces[i].firstedge:old.faces[i].firstedge + old.faces[i].numedges]}
    vertices = {v for i in edges for v in old.edges[i]}
    texinfos = {old.faces[i].texinfo for i in faces}
    planes = ({old.faces[i].planenum for i in faces} |
              {old.nodes[i].planenum for i in nodes} |
              {old.clipnodes[i].planenum for i in clips})
    sets = {'planes': planes, 'vertices': vertices, 'edges': edges,
            'texinfos': texinfos, 'faces': faces, 'render_nodes': nodes,
            'leaves': leaves, 'clipnodes': clips}
    attrs = {'vertices': 'vertexes', 'texinfos': 'texinfo',
             'render_nodes': 'nodes', 'leaves': 'leafs'}
    maps = {name: {i: len(getattr(old, attrs.get(name, name))) + j
                   for j, i in enumerate(sorted(indices))}
            for name, indices in sets.items()}
    return maps


def preservation(args, old, new):
    result = section()
    a, b = args.base.read_bytes(), args.bsp.read_bytes()
    result['original_non_entity_prefixes'] = {}
    result['immutable_lumps_identical'] = {}
    for i in range(1, 15):
        ao, al = struct.unpack_from('<2i', a, 4 + 8 * i)
        bo, bl = struct.unpack_from('<2i', b, 4 + 8 * i)
        same = bl >= al and a[ao:ao + al] == b[bo:bo + al]
        result['original_non_entity_prefixes'][str(i)] = same
        if not same:
            fail(result, 'An original non-entity record was changed', lump=i)
        if i not in CHANGED_LUMPS:
            exact = al == bl and a[ao:ao + al] == b[bo:bo + bl]
            result['immutable_lumps_identical'][str(i)] = exact
            if not exact:
                fail(result, 'An immutable lump changed', lump=i)
    prefix = bytearray(b[:len(a)])
    for i in CHANGED_LUMPS:
        prefix[4 + i * 8:12 + i * 8] = a[4 + i * 8:12 + i * 8]
    if prefix != a:
        fail(result, 'Source file prefix or extra header changed outside descriptors')
    if len(old.models) != NEW_MODEL or len(new.models) != NEW_MODEL + 1:
        fail(result, 'Unexpected model inventory', old=len(old.models), new=len(new.models))
    if new.models[:len(old.models)] != old.models:
        fail(result, 'World or an original brush model changed')
    if len(old.entities) != 1047 or len(new.entities) != 1047:
        fail(result, 'Expected 1047 entity records')
    changed = []
    for i, (aent, bent) in enumerate(zip(old.entities, new.entities)):
        if not creek(aent):
            if aent.pairs != bent.pairs:
                fail(result, 'Unrelated ordered entity record changed', entity=i)
            continue
        expected = copy.deepcopy(aent)
        o = vec(aent)
        expected.set('model', '*' + str(NEW_MODEL))
        expected.set('origin', f'{o[0]:g} {o[1]:g} 0')
        if expected.pairs != bent.pairs:
            fail(result, 'Water record has changes beyond model and baked origin', entity=i)
        if aent.get('model') != '*162' or o[2] != Z_BAKE or bent.get('skin') != '-3':
            fail(result, 'Unexpected frozen water policy', entity=i)
        if vec(bent)[2] != 0 or vec(bent, 'angles') != (0., 0., 0.):
            fail(result, 'New instance translation or rotation is invalid', entity=i)
        changed.append(i)
    if changed != [482, 1044, 1045, 1046]:
        fail(result, 'Exactly the four reviewed water records must change', actual=changed)
    result.update({'changed_water_records': changed, 'preserved_other_entity_records':
                   len(old.entities) - len(changed), 'total_entities': len(new.entities),
                   'preserved_original_models': len(old.models),
                   'world_headnodes': new.models[0].headnode,
                   'original_file_prefix_preserved_except_descriptors': prefix == a})
    return finish(result)


def clone_check(old, new, source):
    result = section()
    maps = independent_maps(old)
    attrs = {'vertices': 'vertexes', 'texinfos': 'texinfo',
             'render_nodes': 'nodes', 'leaves': 'leafs'}
    reported = {k: {int(a): b for a, b in v.items()}
                for k, v in source.get('index_maps', {}).items()}
    if reported != maps:
        fail(result, 'Builder mapping differs from independently derived source closure')
    for name, mapping in maps.items():
        attr = attrs.get(name, name)
        if len(getattr(new, attr)) != len(getattr(old, attr)) + len(mapping):
            fail(result, 'Unexpected appended record count', record=name)
    for a, b in maps['planes'].items():
        p, q = old.planes[a], new.planes[b]
        if q.normal != p.normal or q.type != p.type or q.dist != f32(p.dist + p.normal[2] * Z_BAKE):
            fail(result, 'Baked plane differs from exact translation', source=a, candidate=b)
    vertex_error = uv_error = 0.0
    for a, b in maps['vertices'].items():
        p, q = old.vertexes[a], new.vertexes[b]
        vertex_error = max(vertex_error, *(abs(q[k] - f32(translated(p)[k])) for k in range(3)))
    for a, b in maps['texinfos'].items():
        p, q = old.texinfo[a], new.texinfo[b]
        expected = [[*v[:3], f32(v[3] - v[2] * Z_BAKE)] for v in p.vecs]
        if q.vecs != expected or q.miptex != p.miptex or q.flags != p.flags:
            fail(result, 'Texture projection or flags changed beyond inverse translation', source=a)
        for va, vb in maps['vertices'].items():
            x, y = old.vertexes[va], new.vertexes[vb]
            for axis in range(2):
                before = sum(x[k] * p.vecs[axis][k] for k in range(3)) + p.vecs[axis][3]
                after = sum(y[k] * q.vecs[axis][k] for k in range(3)) + q.vecs[axis][3]
                uv_error = max(uv_error, abs(after - before))
    for a, b in maps['edges'].items():
        if new.edges[b] != tuple(maps['vertices'][v] for v in old.edges[a]):
            fail(result, 'Edge winding or vertex association changed', source=a)
    for a, b in maps['faces'].items():
        p, q = old.faces[a], new.faces[b]
        if (q.planenum != maps['planes'][p.planenum] or q.side != p.side or
                q.numedges != p.numedges or q.texinfo != maps['texinfos'][p.texinfo] or
                q.styles != p.styles or q.lightofs != p.lightofs):
            fail(result, 'Face plane, side, texture or lightmap descriptor changed', source=a)
        before = old.surfedges[p.firstedge:p.firstedge + p.numedges]
        expected = [maps['edges'][abs(e)] * (1 if e >= 0 else -1) for e in before]
        after = new.surfedges[q.firstedge:q.firstedge + q.numedges]
        if after != expected:
            fail(result, 'Face edge sequence changed', source=a)
        if polygon(new, b) != [translated(v) for v in polygon(old, a)]:
            fail(result, 'Face world vertex sequence changed', source=a)
        if new.textures[new.texinfo[q.texinfo].miptex].name != '!DPWATER':
            fail(result, 'Animated water texture changed', face=b)
    for a, b in maps['render_nodes'].items():
        p, q = old.nodes[a], new.nodes[b]
        expected = [maps['render_nodes'][v] if v >= 0 else -1 - maps['leaves'][-1 - v]
                    for v in p.children]
        if (q.planenum != maps['planes'][p.planenum] or q.children != expected or
                q.mins != translated(p.mins) or q.maxs != translated(p.maxs) or
                q.numfaces != p.numfaces):
            fail(result, 'Render tree clone differs from translated source', source=a)
        expected_faces = [maps['faces'][i] for i in range(p.firstface, p.firstface + p.numfaces)]
        if list(range(q.firstface, q.firstface + q.numfaces)) != expected_faces:
            fail(result, 'Render node face range differs', source=a)
    for a, b in maps['leaves'].items():
        p, q = old.leafs[a], new.leafs[b]
        if (q.contents != p.contents or q.visofs != p.visofs or q.ambient != p.ambient or
                q.mins != translated(p.mins) or q.maxs != translated(p.maxs) or
                q.nummarksurfaces != p.nummarksurfaces):
            fail(result, 'Leaf contents, bounds or visibility changed', source=a)
        expected = [maps['faces'][v] for v in old.marksurfaces[
            p.firstmarksurface:p.firstmarksurface + p.nummarksurfaces]]
        if new.marksurfaces[q.firstmarksurface:q.firstmarksurface + q.nummarksurfaces] != expected:
            fail(result, 'Leaf surface references changed', source=a)
    for a, b in maps['clipnodes'].items():
        p, q = old.clipnodes[a], new.clipnodes[b]
        expected = [maps['clipnodes'][v] if v >= 0 else v for v in p.children]
        if q.planenum != maps['planes'][p.planenum] or q.children != expected:
            fail(result, 'Clip hull clone differs from source', source=a)
    p, q = old.models[SOURCE_MODEL], new.models[NEW_MODEL]
    heads = [maps['render_nodes'][p.headnode[0]],
             *(maps['clipnodes'][v] for v in p.headnode[1:])]
    if (q.mins != translated(p.mins) or q.maxs != translated(p.maxs) or
            q.origin != p.origin or q.headnode != heads or q.visleafs != p.visleafs or
            q.firstface != maps['faces'][p.firstface] or q.numfaces != p.numfaces):
        fail(result, 'Appended model bounds, origin, hull heads or surface range differ')
    if vertex_error > .0001 or uv_error > .0001:
        fail(result, 'Baked geometry or UVs changed', vertex_error=vertex_error, uv_error=uv_error)
    result.update({'appended_counts': {k: len(v) for k, v in maps.items()},
                   'maximum_vertex_error': vertex_error, 'maximum_uv_error': uv_error,
                   'model_world_z_bounds': [q.mins[2], q.maxs[2]], 'new_headnodes': heads,
                   'source_texture_and_lightmap_descriptors_preserved': True})
    return finish(result), maps


def clip_contents(bsp, head, point):
    point = tuple(map(f32, point))
    count, n = 0, head
    while n >= 0:
        count += 1
        if n >= len(bsp.clipnodes) or count > len(bsp.clipnodes):
            raise ValueError('Invalid or cyclic clip hull')
        record = bsp.clipnodes[n]
        p = bsp.planes[record.planenum]
        if p.type < 3:
            d = f32(point[p.type] - p.dist)
        else:
            product = f32(f32(f32(point[0] * p.normal[0]) + f32(point[1] * p.normal[1])) +
                          f32(point[2] * p.normal[2]))
            d = f32(product - p.dist)
        n = record.children[0 if d >= 0 else 1]
    return n


def xy_inside(points, x, y):
    values = [(b[0] - a[0]) * (y - a[1]) - (b[1] - a[1]) * (x - a[0])
              for a, b in zip(points, points[1:] + points[:1])]
    return min(values) >= -.01 or max(values) <= .01


def renderer_check(old, new, old_waters, waters):
    result = section()
    summaries = []
    for label, bsp, entities in [('source', old, old_waters), ('candidate', new, waters)]:
        counts = Counter()
        fronts = []
        e = entities[0]
        model = bsp.models[int(e.get('model')[1:])]
        world_min = f32(vec(e)[2] + model.mins[2])
        for i in range(model.firstface, model.firstface + model.numfaces):
            f = bsp.faces[i]
            pl = bsp.planes[f.planenum]
            if pl.type != 2:
                counts['side_faces_skipped_without_EF_WATERSIDES'] += 1
                continue
            if f32(world_min + 1.) >= pl.dist:
                counts['height_test_skipped'] += 1
                continue
            counts['admitted_horizontal_faces'] += 1
            if pl.normal == (0., 0., 1.) and not f.side:
                fronts.append(i)
                counts['upward_top_faces'] += 1
        if label == 'source' and counts['admitted_horizontal_faces'] != 0:
            fail(result, 'Expected the independently reproduced original water render defect')
        if label == 'candidate':
            if counts['upward_top_faces'] < 1:
                fail(result, 'No upward animated water top face survives stock selection')
            area = 0.0
            polys = []
            for i in fronts:
                p = polygon(bsp, i)
                area += abs(sum(a[0] * b[1] - b[0] * a[1]
                                for a, b in zip(p, p[1:] + p[:1]))) / 2
                if any(abs(v[2] - 2936.) > .001 for v in p):
                    fail(result, 'Selected top surface is at an incorrect world water height', face=i)
                polys.append(p)
            expected_area = (model.maxs[0] - model.mins[0]) * (model.maxs[1] - model.mins[1])
            if abs(area - expected_area) > .1:
                fail(result, 'Selected top faces do not cover exact brush footprint', area=area)
            samples = 0
            for x in range(-11968, 11981, 128):
                for y in range(1424, 2180, 16):
                    if not any(xy_inside(p, x, y) for p in polys):
                        fail(result, 'Selected water top geometry contains a coverage gap', xy=[x, y])
                    samples += 1
            result.update({'water_top_geometry_coverage_samples': samples,
                           'selected_upward_top_area': area, 'expected_top_area': expected_area,
                           'top_height_world': 2936.})
        summaries.append({'map': label, 'world_model_min_z_plus_one': world_min + 1.,
                          'counts': dict(counts), 'selected_upward_faces': fronts})
    result['stock_renderer_selection'] = summaries
    result['renderer_source_sha256'] = sha(REPO / 'Engine-Source/Xash3D/ref/gl/gl_rsurf.c')
    result['scope'] = 'Stock turbulent-face selection and exact compiled top footprint; native visibility and appearance are still unproven.'
    return finish(result)


def fluid_equivalence(old, new, old_waters, waters, maps):
    result = section()
    if len(old_waters) != 4 or len(waters) != 4:
        fail(result, 'Expected four water instances for fluid equivalence')
        return finish(result), []
    names = [e.get('targetname') for e in old_waters]
    new_by_name = {e.get('targetname'): e for e in waters}
    if set(names) != set(new_by_name):
        fail(result, 'Water instance names changed')
        return finish(result), []
    model = old.models[SOURCE_MODEL]
    rng = random.Random(0xC2EE7)
    local_samples = []
    for axis in range(3):
        for value in (model.mins[axis], model.maxs[axis]):
            for delta in (-.01, 0., .01):
                p = [(a + b) / 2 for a, b in zip(model.mins, model.maxs)]
                p[axis] = value + delta
                local_samples.append(tuple(p))
    local_samples.extend(tuple(rng.uniform(model.mins[k] - 64, model.maxs[k] + 64)
                               for k in range(3)) for _ in range(4096))
    # Replay every axial boundary used by all four source hulls, including their
    # different player extents. A moved clip plane must preserve boundary ties.
    for pi in maps['planes']:
        p = old.planes[pi]
        if p.type < 3 and p.normal[p.type] == 1:
            for delta in (-.01, 0., .01):
                q = [(a + b) / 2 for a, b in zip(model.mins, model.maxs)]
                q[p.type] = p.dist + delta
                local_samples.append(tuple(q))
    raw_counts = Counter()
    from test_meadow_creek import hull0_contents
    for a in old_waters:
        b = new_by_name[a.get('targetname')]
        origin = vec(a)
        for p in local_samples:
            world = tuple(f32(origin[k] + p[k]) for k in range(3))
            for hull in range(4):
                pa = tuple(f32(world[k] - f32(vec(a)[k])) for k in range(3))
                pb = tuple(f32(world[k] - f32(vec(b)[k])) for k in range(3))
                if hull == 0:
                    ca = hull0_contents(old, model.headnode[0], pa)
                    cb = hull0_contents(new, new.models[NEW_MODEL].headnode[0], pb)
                else:
                    ca = clip_contents(old, model.headnode[hull], pa)
                    cb = clip_contents(new, new.models[NEW_MODEL].headnode[hull], pb)
                raw_counts[str(hull)] += 1
                if ca != cb:
                    fail(result, 'Translated float32 brush hull changed', hull=hull,
                         instance=a.get('targetname'), world=world, before=ca, after=cb)
    ox = vec(old_waters[0])[0]
    index = SurfaceIndex(old)
    counts = Counter()

    def compare(p, label):
        ca, cb = contents(old, old_waters, p), contents(new, waters, p)
        counts[label] += 1
        counts['world_' + str(world_contents(old, p))] += 1
        if ca != cb:
            fail(result, 'Engine float32 world/fluid overlay changed', label=label,
                 point=p, before=ca, after=cb)

    # Independently replay the original coverage grid at every available bed,
    # including inaccessible solid and dry shore points rather than skipping them.
    for x in range(-11000, 11001, 128):
        for y in range(13496, 16537, 32):
            wx = ox + x
            surface = index.at(wx, y, GROUND_TEXTURES)
            if surface is None:
                counts['pre_existing_missing_rendered_grid_floor'] += 1
                continue
            for z in (surface['z'] - 8., surface['z'] + 8.,
                      (surface['z'] + 2936.) / 2., 2935.99, 2936., 2936.01):
                compare((wx, y, z), 'creek_grid_overlay')
    missing_bed = 0
    for x in range(-288, 289, 32):
        for y in range(14320, 15713, 32):
            wx = ox + x
            surface = index.at(wx, y, GROUND_TEXTURES)
            if surface is None:
                missing_bed += 1
                z = solid_floor(old, wx, y, 2932., 2808.)
            else:
                z = surface['z']
            if z is None:
                fail(result, 'Bridge bed has no preserved floor', xy=[wx, y])
                continue
            for height in (z - 8., min(2932., z + 8.), 2935.99, 2936., 2936.01):
                compare((wx, y, height), 'bridge_opening_overlay')
    for y in (14256., 15016., 15776.):
        for x in (-2000., -700., 0., 700., 2000.):
            for delta in (-.01, 0., .01):
                for z in (2815.99, 2816., 2816.01, 2928., 2935.99, 2936., 2936.01):
                    compare((ox + x, y + delta, z), 'water_seam_overlay')
    floor_probes = []
    for x in (-288, 0, 288):
        for local_y in range(700, 2901, 50):
            y, wx = 13216. + local_y, ox + x
            s = index.at(wx, y)
            if s is None:
                fail(result, 'Dry bridge/approach lacks a preserved rendered floor')
                continue
            point = (wx, y, s['z'] + 8.)
            compare(point, 'dry_bridge_and_approach_overlay')
            if contents(new, waters, point) != -1:
                fail(result, 'Bridge or approach became wet or obstructed', point=point)
            floor_probes.append({'world_xy': [wx, y], 'rendered_floor_z': s['z'],
                                 'label': f'bridge-x{x}-y{local_y}'})
    result.update({'raw_brush_hull_float32_probes': dict(raw_counts),
                   'world_fluid_overlay_probes': dict(counts),
                   'bridge_pre_existing_missing_rendered_bed_probes': missing_bed,
                   'linked_world_floor_probe_count': len(floor_probes),
                   'scope': 'Compiled float32 four-hull clone and SV/PM skin overlay equivalence; actual native swimming and appearance require fresh game evidence.'})
    return finish(result), floor_probes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('base', 'bsp', 'report-source', 'report'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--actual-c', action='store_true')
    args = parser.parse_args()
    sys.setrecursionlimit(20000)
    inputs = {'base': args.base, 'bsp': args.bsp, 'report_source': args.report_source}
    if args.report.resolve() in {p.resolve() for p in inputs.values()}:
        parser.error('Report may not overwrite an input')
    hashes = {k: sha(p) for k, p in inputs.items()}
    source = json.loads(args.report_source.read_text())
    metadata = section()
    for key, expected in [('base', BASE_SHA), ('bsp', CANDIDATE_SHA), ('report_source', SOURCE_REPORT_SHA)]:
        if hashes[key] != expected:
            fail(metadata, 'Input differs from frozen visible-water review', input=key,
                 expected=expected, actual=hashes[key])
    if (source.get('base_sha256') != hashes['base'] or
            source.get('output_sha256') != hashes['bsp'] or
            source.get('z_bake') != Z_BAKE or source.get('source_model') != SOURCE_MODEL or
            source.get('new_model') != NEW_MODEL):
        fail(metadata, 'Builder report does not describe these inputs')
    old, new = BSP.load(args.base), BSP.load(args.bsp)
    old_waters = [e for e in old.entities if creek(e)]
    waters = [e for e in new.entities if creek(e)]
    report = {'input_sha256': hashes, 'metadata': finish(metadata),
              'actual_c_requested': args.actual_c,
              'checker_source_sha256': sha(Path(__file__))}
    print('Checking immutable old geometry and independently derived water clone', flush=True)
    report['preservation'] = preservation(args, old, new)
    report['clone_geometry'], maps = clone_check(old, new, source)
    report['renderer_selection'] = renderer_check(old, new, old_waters, waters)
    print('Replaying translated float32 hulls, creek beds, seams and dry bridge', flush=True)
    report['fluid_equivalence'], probes = fluid_equivalence(old, new, old_waters, waters, maps)
    report['actual_c'] = actual_c(args.bsp, probes) if args.actual_c else {
        'status': 'not_requested', 'pass': None,
        'reason': 'Original world hulls are byte-preserved; existing creek receipt proves135world floors. No new C trace requested.'}
    report['inputs_unchanged_during_verification'] = hashes == {k: sha(p) for k, p in inputs.items()}
    report['static_pass'] = report['inputs_unchanged_during_verification'] and all(
        report[k]['pass'] for k in ('metadata', 'preservation', 'clone_geometry',
                                    'renderer_selection', 'fluid_equivalence'))
    report['pass'] = report['static_pass'] and (not args.actual_c or report['actual_c']['pass'] is True)
    report['native_visual_acceptance'] = None
    report['scope'] = 'Independent frozen water-model translation, world preservation, renderer face admission and fluid-overlay equivalence. Native waterlevel, replication and visual acceptance are not claimed.'
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'pass': report['pass'], 'static_pass': report['static_pass'],
                      'bsp_sha256': hashes['bsp'], 'report_sha256': sha(args.report),
                      'report': str(args.report), 'actual_c': report['actual_c']['status']}, indent=2))
    return 0 if report['pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
