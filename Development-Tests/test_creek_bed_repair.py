"""Independent render/collision/coverage QA for the frozen creek-bed repair.

No bed-builder imports, game launches or runtime writes. Existing surfaces are
indexed with the shared read-only BSP surface utility; new geometry, collision
interfaces, coplanar overlap and reference remapping are checked separately.
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
sys.path[:0] = [str(REPO / 'Packaging-Work/BigWorld/tools'), str(REPO / 'Design-Source/Daragoth-Meadow')]
from bsp30 import BSP, FACE
from meadow_surface import SurfaceIndex

BASE_SHA = 'a82d997a153543198f01c2d36199b7d78498f309c6a251fa70891abacbf69f29'
GROUND = ('DPGRASS', 'DPPATH', 'DPDIRT')
EMPTY, SOLID, WATER = -1, -2, -3
OWNERS = {8808: (4474, 1, 4517)}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def section():
    return {'failure_count': 0, 'failures': []}


def check(result, condition, message, **details):
    if not condition:
        result['failure_count'] += 1
        if len(result['failures']) < 30:
            result['failures'].append({'message': message, **details})


def finish(result):
    result['pass'] = result['failure_count'] == 0
    return result


def f32(value):
    return struct.unpack('<f', struct.pack('<f', value))[0]


def lump_data(data):
    return [data[o:o + size] for o, size in (struct.unpack_from('<2i', data, 4 + i * 8) for i in range(15))]


def polygon(bsp, face):
    return [bsp.vertexes[bsp.edges[abs(e)][0 if e >= 0 else 1]]
            for e in bsp.surfedges[face.firstedge:face.firstedge + face.numedges]]


def area(poly):
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(poly, poly[1:] + poly[:1])) / 2


def overlap_polygon(subject, clipper):
    """Independent convex XY intersection; the compiler's faces are convex."""
    orientation = 1 if area(clipper) > 0 else -1
    output = list(subject)
    for a, b in zip(clipper, clipper[1:] + clipper[:1]):
        if not output:
            break
        incoming, output = output, []

        def distance(p):
            return orientation * ((b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]))

        previous = incoming[-1]
        pd = distance(previous)
        for current in incoming:
            cd = distance(current)
            if (pd >= 0) != (cd >= 0):
                ratio = pd / (pd - cd)
                output.append((previous[0] + ratio * (current[0] - previous[0]),
                               previous[1] + ratio * (current[1] - previous[1])))
            if cd >= 0:
                output.append(current)
            previous, pd = current, cd
    return output


def hull0(bsp, head, point):
    point = tuple(map(f32, point))
    index, steps = head, 0
    while index >= 0:
        node = bsp.nodes[index]
        plane = bsp.planes[node.planenum]
        if plane.type < 3:
            distance = f32(point[plane.type] - plane.dist)
        else:
            distance = f32(f32(f32(point[0] * plane.normal[0]) + f32(point[1] * plane.normal[1])) + f32(point[2] * plane.normal[2]))
            distance = f32(distance - plane.dist)
        index = node.children[0 if distance >= 0 else 1]
        steps += 1
        if steps > len(bsp.nodes):
            raise ValueError('Invalid cyclic render hull')
    return bsp.leafs[-1 - index].contents


def world(bsp, point):
    return hull0(bsp, bsp.models[0].headnode[0], point)


def fluid(bsp, point):
    contents = world(bsp, point)
    if contents != EMPTY:
        return contents
    for entity in bsp.entities:
        if entity.classname != 'func_water' or entity.get('targetname', '').startswith('plains_creek_water_') is False:
            continue
        if entity.get('skin') != '-3':
            raise ValueError('Unexpected creek liquid skin')
        origin = tuple(f32(float(v)) for v in entity.get('origin').split())
        model = bsp.models[int(entity.get('model')[1:])]
        local = tuple(f32(f32(point[k]) - origin[k]) for k in range(3))
        if hull0(bsp, model.headnode[0], local) != EMPTY:
            return WATER
    return EMPTY


def lightmap_size(bsp, face):
    info = bsp.texinfo[face.texinfo]
    low_flags = info.flags & 65535
    step = 1 if low_flags & 2 else 8 if low_flags & 8 else 16
    faceinfo = struct.unpack('<h', struct.pack('<H', (info.flags >> 16) & 65535))[0]
    if not low_flags & (2 | 8) and faceinfo >= 0:
        records = bsp.extra_lumps.get(1, b'')
        if (faceinfo + 1) * 22 > len(records):
            raise ValueError('Invalid landscape faceinfo reference')
        step = struct.unpack_from('<H', records, faceinfo * 22 + 16)[0]
    if step <= 0:
        raise ValueError('Invalid lightmap resolution')
    points = polygon(bsp, face)
    sizes = []
    for vec in info.vecs:
        values = [sum(p[k] * vec[k] for k in range(3)) + vec[3] for p in points]
        sizes.append(math.ceil(max(values) / step) - math.floor(min(values) / step) + 1)
    styles = sum(style != 255 for style in face.styles)
    return sizes[0] * sizes[1] * styles * 3, step, sizes


def preserved(old, new, before_data, after_data, added):
    result = section()
    before, after = lump_data(before_data), lump_data(after_data)
    immutable = {str(i): before[i] == after[i] for i in (0, 1, 2, 4, 9)}
    for i, equal in immutable.items():
        check(result, equal, 'Immutable entity/plane/texture/PVS/clip data changed', lump=i)
    for i in (3, 6, 8, 12, 13):
        check(result, after[i].startswith(before[i]), 'Original render/light/UV records were overwritten', lump=i)
    check(result, old.extra_lumps == new.extra_lumps, 'Extra lighting/landscape metadata changed')
    check(result, len(old.nodes) == len(new.nodes) and len(old.leafs) == len(new.leafs) and len(old.models) == len(new.models),
          'Bed repair changed collision tree/model inventory')
    for i, (a, b) in enumerate(zip(old.nodes, new.nodes)):
        check(result, (a.planenum, a.children) == (b.planenum, b.children), 'World/model render hull topology changed', node=i)
    for i, (a, b) in enumerate(zip(old.leafs, new.leafs)):
        check(result, (a.contents, a.visofs, a.ambient) == (b.contents, b.visofs, b.ambient), 'Leaf collision/PVS/ambient metadata changed', leaf=i)
    added_set = set(added)
    old_face_ids = [i for i in range(len(new.faces)) if i not in added_set]
    check(result, len(old_face_ids) == len(old.faces), 'Original face count/remapping is inconsistent')
    remap = dict(enumerate(old_face_ids))
    for old_id, new_id in remap.items():
        check(result, before[7][old_id * FACE.size:(old_id + 1) * FACE.size] == after[7][new_id * FACE.size:(new_id + 1) * FACE.size],
              'An existing face record changed during insertion', old_face=old_id, new_face=new_id)
    for i, (a, b) in enumerate(zip(old.models, new.models)):
        check(result, (a.mins, a.maxs, a.origin, a.headnode, a.visleafs) == (b.mins, b.maxs, b.origin, b.headnode, b.visleafs),
              'Existing model bounds/heads/origin changed', model=i)
        expected_count = a.numfaces + len(added) if i == 0 else a.numfaces
        check(result, b.numfaces == expected_count and b.firstface == remap.get(a.firstface, a.firstface), 'Model face range was remapped incorrectly', model=i)
    owner_faces = Counter()
    for i, (a, b) in enumerate(zip(old.nodes, new.nodes)):
        expected_old = [remap[f] for f in range(a.firstface, a.firstface + a.numfaces)]
        candidate_faces = list(range(b.firstface, b.firstface + b.numfaces))
        check(result, [f for f in candidate_faces if f not in added_set] == expected_old, 'Node face references lost/replaced an existing surface', node=i)
        for face in set(candidate_faces) & added_set:
            owner_faces[face] += 1
            check(result, i in OWNERS and new.faces[face].planenum == OWNERS[i][0] and new.faces[face].side == OWNERS[i][1],
                  'A bed face has an unexpected render-node owner', node=i, face=face)
    for face in added:
        check(result, owner_faces[face] == 1, 'A new face must have exactly one original render-node owner', face=face, owners=owner_faces[face])
    marks = Counter()
    for i, (a, b) in enumerate(zip(old.leafs, new.leafs)):
        expected_old = [remap[f] for f in old.marksurfaces[a.firstmarksurface:a.firstmarksurface + a.nummarksurfaces]]
        actual = new.marksurfaces[b.firstmarksurface:b.firstmarksurface + b.nummarksurfaces]
        check(result, [f for f in actual if f not in added_set] == expected_old, 'Leaf lost/replaced an original face mark', leaf=i)
        for face in actual:
            if face in added_set:
                marks[face] += 1
                check(result, i == 4517 and b.contents == EMPTY or i in (1, 3541) and b.contents == -6,
                      'New bed face uses an unexpected local/common visibility holder', face=face, leaf=i)
    for face in added:
        check(result, marks[face] > 0, 'New bed face has no leaf marksurface references', face=face)
        holder = new.leafs[4517]
        check(result, face in new.marksurfaces[holder.firstmarksurface:holder.firstmarksurface + holder.nummarksurfaces],
              'Bed face has no actual EMPTY leaf4517 reference', face=face)
    result.update({'immutable_lumps_identical': immutable, 'entities_preserved': len(old.entities),
                   'models_headnodes_preserved': len(old.models), 'collision_nodes_preserved': len(old.nodes),
                   'leaf_contents_preserved': len(old.leafs), 'old_faces_preserved_and_remapped': len(old.faces),
                   'added_faces': len(added), 'new_face_mark_references': sum(marks.values())})
    return finish(result), remap


def geometry(old, new, added):
    result = section()
    lightmaps = section()
    checks = 0
    total_area = 0.0
    max_overlap = 0.0
    intervals = []
    old_surfaces = SurfaceIndex(old).surfaces
    additions = []
    for index in added:
        face = new.faces[index]
        plane = new.planes[face.planenum]
        normal = tuple(v * (-1 if face.side else 1) for v in plane.normal)
        points = polygon(new, face)
        xy = [(p[0], p[1]) for p in points]
        signed_area = area(xy)
        expected_owner = next((n for n, (p, side, _) in OWNERS.items() if (p, side) == (face.planenum, face.side)), None)
        check(result, expected_owner is not None and normal[2] > .2 and len(points) >= 3, 'New bed face is not a diagnosed upward floor', face=index)
        check(result, signed_area < -.01, 'Bed winding disagrees with clockwise upward stock rendering', face=index, area=signed_area)
        check(result, max(abs(sum(p[k] * plane.normal[k] for k in range(3)) - plane.dist) for p in points) < .002,
              'Bed vertices do not lie on the original collision plane', face=index)
        material = new.textures[new.texinfo[face.texinfo].miptex].name
        check(result, material in GROUND, 'Bed uses an unexpected material', face=index, texture=material)
        source_face = old.faces[13410 if face.planenum == 4420 else 13412]
        check(result, face.texinfo == source_face.texinfo, 'Bed UV mapping differs from the original terrain cell', face=index)
        bounds = (min(p[0] for p in points), min(p[1] for p in points), max(p[0] for p in points), max(p[1] for p in points))
        for surface in old_surfaces:
            if bounds[2] < surface.bounds[0] or bounds[0] > surface.bounds[2] or bounds[3] < surface.bounds[1] or bounds[1] > surface.bounds[3]:
                continue
            if max(abs(sum(p[k] * plane.normal[k] for k in range(3)) - plane.dist) for p in surface.points) > .002:
                continue
            overlap = overlap_polygon(xy, [(p[0], p[1]) for p in surface.points])
            amount = abs(area(overlap)) if len(overlap) >= 3 else 0
            max_overlap = max(max_overlap, amount)
            check(result, amount <= 1, 'Bed overlaps an existing coplanar rendered surface', face=index, old_face=surface.face, overlap_area=amount)
        for prior in additions:
            if prior['plane'] != face.planenum:
                continue
            overlap = overlap_polygon(xy, prior['xy'])
            amount = abs(area(overlap)) if len(overlap) >= 3 else 0
            max_overlap = max(max_overlap, amount)
            check(result, amount <= 1, 'New bed polygons overlap each other', face=index, other=prior['face'], overlap_area=amount)
        additions.append({'face': index, 'plane': face.planenum, 'xy': xy})
        total_area += abs(signed_area)
        for a, b in zip(points[1:-1], points[2:]):
            for weights in ((.2, .2, .6), (.2, .6, .2), (.6, .2, .2), (1/3, 1/3, 1/3)):
                p = tuple(sum(weights[j] * (points[0], a, b)[j][k] for j in range(3)) for k in range(3))
                above = (p[0], p[1], p[2] + .002)
                below = (p[0], p[1], p[2] - .002)
                check(result, world(old, above) == EMPTY and world(old, below) == SOLID,
                      'New face does not cover the original EMPTY/SOLID floor interface', face=index, point=p)
                checks += 1
        size, step, dimensions = lightmap_size(new, face)
        check(lightmaps, step == 64 and face.styles == [0, 255, 255, 255], 'Bed lightmap does not use original landscape resolution/style', face=index, step=step)
        check(lightmaps, size > 0 and face.lightofs >= len(old.lighting) and face.lightofs + size <= len(new.lighting),
              'Bed lightmap storage is invalid', face=index, dimensions=dimensions, offset=face.lightofs, bytes=size)
        intervals.append((face.lightofs, face.lightofs + size))
    at = len(old.lighting)
    for lo, hi in sorted(intervals):
        check(lightmaps, lo == at, 'Bed lightmaps overlap or leave unreported append gaps', offset=lo, expected=at)
        at = hi
    check(lightmaps, at == len(new.lighting), 'Unexpected appended light bytes outside bed repair')
    ownership = {}
    x, y = 1786.05, 14360
    for plane_id in (4474, 4420):
        p = old.planes[plane_id]
        z = (p.dist - p.normal[0] * x - p.normal[1] * y) / p.normal[2]
        ownership[str(plane_id)] = {'z': z, 'above': world(old, (x, y, z + .002)),
                                    'below': world(old, (x, y, z - .002))}
    check(result, ownership['4474']['above'] == EMPTY and ownership['4474']['below'] == SOLID,
          'Near-coincident test does not identify actual floor4474', ownership=ownership)
    check(result, ownership['4420']['above'] == EMPTY and ownership['4420']['below'] == EMPTY,
          'Near-coincident plane4420 was incorrectly treated as a missing floor', ownership=ownership)
    result.update({'added_faces': len(added), 'upward_interface_probes': checks,
                   'total_xy_area': total_area, 'max_coplanar_overlap_area': max_overlap,
                   'ownership_offset': .002, 'near_coincident_plane_ownership': ownership})
    lightmaps.update({'verified_faces': len(added), 'sample_step': 64, 'appended_rgb_bytes': len(new.lighting) - len(old.lighting)})
    return finish(result), finish(lightmaps)


def coverage(old, new):
    result = section()
    before, after = SurfaceIndex(old), SurfaceIndex(new)
    counts = Counter()
    wet_points = []
    for x in range(-11000, 11001, 128):
        wx = x + 1650.05
        for y in range(13496, 16537, 32):
            counts['broad_grid_points'] += 1
            if before.at(wx, y, GROUND) is not None:
                continue
            counts['original_ground_filter_misses'] += 1
            surface = before.at(wx, y, max_z=2936)
            if surface is not None:
                counts['existing_' + surface['texture']] += 1
                continue
            if fluid(old, (wx, y, 2935.99)) != WATER:
                counts['dry_world_or_outside_fluid'] += 1
                continue
            wet_points.append([wx, y])
            surface = after.at(wx, y, max_z=2936)
            check(result, surface is not None and surface['texture'] in GROUND,
                  'Diagnosed wet broad-grid bed hole remains unrendered', world_xy=[wx, y])
            if surface is not None:
                check(result, world(old, (wx, y, surface['z'] + .002)) == EMPTY and world(old, (wx, y, surface['z'] - .002)) == SOLID,
                      'Restored broad-grid bed does not match the original solid floor', world_xy=[wx, y])
    check(result, counts['original_ground_filter_misses'] == 313 and len(wet_points) == 13,
          'Independent broad-grid diagnosis does not match the frozen input', misses=counts['original_ground_filter_misses'], wet=len(wet_points))
    fine = []
    for x in range(-288, 289, 32):
        for y in range(1104, 2497, 32):
            wx, wy = x + 1650.05, y + 13216
            if before.at(wx, wy, GROUND) is None:
                fine.append([wx, wy])
                surface = after.at(wx, wy, GROUND, max_z=2936)
                check(result, surface is not None, 'Original fine bridge bed hole remains unrendered', world_xy=[wx, wy])
    check(result, len(fine) == 49, 'Fine bridge-hole diagnosis changed', missing=len(fine))
    dense_count = old_missing = remaining_missing = 0
    max_error = 0.0
    for x in range(1352, 1953, 8):
        for y in range(14320, 14641, 8):
            upper, lower = 2932., 2808.
            if world(old, (x, y, upper)) != EMPTY or world(old, (x, y, lower)) != SOLID:
                continue
            for _ in range(32):
                midpoint = f32((upper + lower) / 2)
                if midpoint <= lower or midpoint >= upper:
                    break
                if world(old, (x, y, midpoint)) == SOLID:
                    lower = midpoint
                else:
                    upper = midpoint
            floor = (lower + upper) / 2
            dense_count += 1
            if before.at(x, y, max_z=2936) is None:
                old_missing += 1
            surface = after.at(x, y, max_z=2936)
            if surface is None:
                remaining_missing += 1
                check(result, False, 'Dense eight-unit bed hole remains unrendered', world_xy=[x, y])
            else:
                difference = abs(surface['z'] - floor)
                max_error = max(max_error, difference)
                check(result, difference <= .01, 'Dense restored/rendered floor differs from original hull', world_xy=[x, y], error=difference)
    check(result, dense_count == 3116 and old_missing == 753 and remaining_missing == 0,
          'Independent dense-window coverage differs from the frozen diagnosis', samples=dense_count, old_missing=old_missing, remaining=remaining_missing)
    result.update({'broad_grid_counts': dict(counts), 'wet_missing_bed_points': wet_points,
                   'wet_missing_bed_count': len(wet_points), 'fine_bridge_missing_bed_points': fine,
                   'fine_bridge_missing_bed_count': len(fine), 'dense_floor_samples': dense_count,
                   'original_dense_missing': old_missing, 'remaining_dense_missing': remaining_missing,
                   'maximum_dense_floor_error': max_error})
    return finish(result)


def actual_c(candidate, bsp):
    from test_meadow_join_caps import actual_c as road_trace
    from test_meadow_creek import actual_c as bridge_trace
    index = SurfaceIndex(bsp)
    probes = []
    for x in (-288, 0, 288):
        for y in range(700, 2901, 50):
            wx, wy = x + 1650.05, y + 13216
            floor = index.at(wx, wy)
            if floor is None:
                return {'status': 'failed', 'pass': False, 'reason': 'Missing bridge approach floor'}
            probes.append({'world_xy': [wx, wy], 'rendered_floor_z': floor['z'], 'label': f'bridge-x{x}-y{y}'})
    road, bridge = road_trace(candidate), bridge_trace(candidate, probes)
    passed = road.get('pass') is True and bridge.get('pass') is True
    return {'status': 'ran' if passed else 'failed', 'pass': passed, 'road': road, 'bridge': bridge,
            'standing_road_sweeps': road.get('standing_road_sweeps', 0),
            'world_bridge_floor_traces': bridge.get('world_bridge_floor_traces', 0),
            'engine_pm_trace_sha256': sha(REPO / 'Engine-Source/Xash3D/engine/common/pm_trace.c')}


def verify(base, candidate, build_report, expected, run_c):
    inputs = {'base': base, 'bsp': candidate, 'report_source': build_report}
    hashes = {k: sha(p) for k, p in inputs.items()}
    metadata = section()
    source = json.loads(build_report.read_text())
    check(metadata, hashes['base'] == BASE_SHA and hashes['bsp'] == expected, 'Wrong frozen base/candidate')
    check(metadata, source.get('base_sha256') == hashes['base'] and source.get('output_sha256') == hashes['bsp'], 'Bed build receipt identifies another map')
    builder = REPO / 'Design-Source/Daragoth-Meadow/build_creek_bed.py'
    builder_sha = sha(builder)
    check(metadata, source.get('builder_sha256') == builder_sha, 'Bed builder source hash changed')
    old, new = BSP.load(base), BSP.load(candidate)
    added = [i for i, f in enumerate(new.faces) if f.firstedge >= len(old.surfedges)]
    check(metadata, bool(added) and len(new.faces) == len(old.faces) + len(added), 'New face inventory is inconsistent')
    preservation, _ = preserved(old, new, base.read_bytes(), candidate.read_bytes(), added)
    new_geometry, lightmaps = geometry(old, new, added)
    grid = coverage(old, new)
    c_result = actual_c(candidate, new) if run_c else {'status': 'not_requested', 'pass': None}
    unchanged = all(sha(p) == hashes[k] for k, p in inputs.items()) and sha(builder) == builder_sha
    report = {'input_sha256': hashes, 'checker_source_sha256': sha(Path(__file__)),
              'builder_source_sha256': builder_sha, 'metadata': finish(metadata), 'preservation': preservation,
              'geometry': new_geometry, 'lightmaps': lightmaps, 'coverage': grid,
              'actual_c_requested': run_c, 'actual_c': c_result,
              'inputs_unchanged_during_verification': unchanged, 'native_visual_acceptance': None}
    report['static_pass'] = unchanged and all(report[k]['pass'] for k in ('metadata', 'preservation', 'geometry', 'lightmaps', 'coverage'))
    report['pass'] = report['static_pass'] and (not run_c or c_result.get('pass') is True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('base', 'bsp', 'build-report', 'report'):
        parser.add_argument('--' + flag, type=Path, required=True)
    parser.add_argument('--expected-bsp-sha', required=True)
    parser.add_argument('--actual-c', action='store_true')
    args = parser.parse_args()
    if len(args.expected_bsp_sha) != 64 or any(c not in '0123456789abcdef' for c in args.expected_bsp_sha):
        parser.error('Supply the independently frozen lowercase SHA256')
    if args.report.exists() or args.report.resolve() in {p.resolve() for p in (args.base, args.bsp, args.build_report)}:
        raise ValueError('Only a new independent QA receipt may be written')
    sys.setrecursionlimit(20000)
    result = verify(args.base, args.bsp, args.build_report, args.expected_bsp_sha, args.actual_c)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('pass', 'static_pass', 'input_sha256', 'checker_source_sha256')}, indent=2))
    sys.exit(0 if result['pass'] else 1)
