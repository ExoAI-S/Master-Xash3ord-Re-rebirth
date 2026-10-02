"""Independent preservation and rendered-boundary QA for the final meadow.

Verify the diagnosed original Y3088 gap, low SKY/EMPTY seam, existing join
coverage, projected original rock and valid lightmaps. All entity records,
collision planes/hulls, PVS and baked animated water must remain unchanged.
Actual-C road sweeps are optional; visual acceptance requires fresh game views.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import struct
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / 'Packaging-Work/BigWorld/tools')]
from bsp30 import BSP, hull_point_contents
from test_meadow_creek import (contents, creek, fail, finish, hull0_contents,
                               section, sha)
from test_meadow_join_caps import (CapIndex, actual_c, cap_record, contains_bounds,
                                   inside, interface, polygon, raw_lump)

BASE_SHA = '22288e02f3b9b83a2f6bcb4bcebd05fefba3bb86460469ce11ec67525c6ea0f3'
CANDIDATE_SHA = '676afa30a2e050a7dca9d56dfc82e1b40048e11c694d838d8e8b8abbd3224d05'
CHANGED = {3, 5, 6, 7, 8, 10, 11, 12, 13, 14}
LOW_SKY = {32, 92, 93, 94, 95, 116, 117, 118, 119, 120}
PREVIOUS_CAPS = set(range(18138, 18228))
RETEXTURED = LOW_SKY | PREVIOUS_CAPS
FIRST = 119
SECOND = 18229
ADDED = {FIRST, SECOND, SECOND + 1, SECOND + 2}


def map_face(index):
    return index if index < FIRST else index + 1 if index < SECOND - 1 else index + 4


def preservation(args, old, new):
    result = section()
    a, b = args.base.read_bytes(), args.bsp.read_bytes()
    result['immutable_lumps_identical'] = {}
    for i in range(15):
        if i in CHANGED:
            continue
        same = raw_lump(a, i) == raw_lump(b, i)
        result['immutable_lumps_identical'][str(i)] = same
        if not same:
            fail(result, 'Immutable entity/collision/PVS/texture lump changed', lump=i)
    prefix = bytearray(b[:len(a)])
    for i in CHANGED:
        prefix[4 + 8 * i:12 + 8 * i] = a[4 + 8 * i:12 + 8 * i]
    if prefix != a:
        fail(result, 'Original file prefix or extra header changed outside render descriptors')
    for i in (3, 6, 8, 12, 13):
        if not raw_lump(b, i).startswith(raw_lump(a, i)):
            fail(result, 'Original render data prefix changed', lump=i)
    if len(new.faces) != len(old.faces) + 4 or len(new.texinfo) != len(old.texinfo) + 1:
        fail(result, 'Unexpected face/texinfo additions')
    if len(new.nodes) != len(old.nodes) or len(new.leafs) != len(old.leafs) or len(new.models) != len(old.models):
        fail(result, 'Collision topology record counts changed')
    changed_faces = set()
    for i, before in enumerate(old.faces):
        after = new.faces[map_face(i)]
        if (before.planenum, before.side, before.firstedge, before.numedges) != (
                after.planenum, after.side, after.firstedge, after.numedges):
            fail(result, 'An old face changed geometry or winding', source=i)
        if i not in RETEXTURED:
            if after != before:
                fail(result, 'Unrelated face material/lightmap changed', source=i)
        elif after.texinfo == before.texinfo or after.lightofs == before.lightofs:
            fail(result, 'A required boundary face was not retextured and relit', source=i)
        else:
            changed_faces.add(i)
    if changed_faces != RETEXTURED:
        fail(result, 'The material change inventory differs from diagnosed boundary', count=len(changed_faces))
    holders = set()
    refs = Counter()
    for i, (before, after) in enumerate(zip(old.leafs, new.leafs)):
        if (before.contents, before.visofs, before.ambient) != (after.contents, after.visofs, after.ambient):
            fail(result, 'Leaf contents, PVS offset or ambient changed', leaf=i)
        marks = new.marksurfaces[after.firstmarksurface:after.firstmarksurface + after.nummarksurfaces]
        kept = [v for v in marks if v not in ADDED]
        expected = [map_face(v) for v in old.marksurfaces[
            before.firstmarksurface:before.firstmarksurface + before.nummarksurfaces]]
        if kept != expected:
            fail(result, 'Old leaf marks changed or were incorrectly remapped', leaf=i)
        extra = [v for v in marks if v in ADDED]
        if len(extra) != len(set(extra)):
            fail(result, 'Duplicate new face mark in a leaf', leaf=i)
        if extra:
            holders.add(i)
            refs.update(extra)
        if (before.mins, before.maxs) != (after.mins, after.maxs) and not extra:
            fail(result, 'Unrelated leaf render bounds changed', leaf=i)
        if not contains_bounds(after.mins, after.maxs, before.mins, before.maxs):
            fail(result, 'Leaf render bounds shrank', leaf=i)
        for fi in extra:
            for p in polygon(new, new.faces[fi]):
                if any(p[k] < after.mins[k] - .001 or p[k] > after.maxs[k] + .001 for k in range(3)):
                    fail(result, 'Added face lies outside its holder bounds', leaf=i, face=fi)
    parents = defaultdict(list)
    for i, n in enumerate(old.nodes):
        for child in n.children:
            parents[child].append(i)
    allowed = set()
    pending = [-i - 1 for i in holders]
    while pending:
        for p in parents.get(pending.pop(), ()):
            if p not in allowed:
                allowed.add(p)
                pending.append(p)
    enlarged = 0
    for i, (before, after) in enumerate(zip(old.nodes, new.nodes)):
        if (before.planenum, before.children) != (after.planenum, after.children):
            fail(result, 'Render collision plane or child topology changed', node=i)
        wanted_first = map_face(before.firstface) if before.numfaces else before.firstface
        wanted_count = before.numfaces + (1 if i == 78 else 3 if i == 0 else 0)
        if after.firstface != wanted_first or after.numfaces != wanted_count:
            fail(result, 'Node face range is incorrectly remapped', node=i)
        if (before.mins, before.maxs) != (after.mins, after.maxs):
            enlarged += 1
            if i not in allowed:
                fail(result, 'Unrelated render node bounds changed', node=i)
        if not contains_bounds(after.mins, after.maxs, before.mins, before.maxs):
            fail(result, 'Render node bounds shrank', node=i)
    for i, (before, after) in enumerate(zip(old.models, new.models)):
        if (before.mins, before.maxs, before.origin, before.headnode, before.visleafs) != (
                after.mins, after.maxs, after.origin, after.headnode, after.visleafs):
            fail(result, 'Model geometry bounds, origin or collision headnodes changed', model=i)
        wanted_first = map_face(before.firstface) if before.numfaces else before.firstface
        if after.firstface != wanted_first or after.numfaces != before.numfaces + (4 if i == 0 else 0):
            fail(result, 'Model face range is incorrectly remapped', model=i)
    for fi in ADDED:
        if refs[fi] < 1:
            fail(result, 'New boundary face has no leaf marks', face=fi)
    for li in (1, 3541):
        l = new.leafs[li]
        if not ADDED <= set(new.marksurfaces[l.firstmarksurface:l.firstmarksurface + l.nummarksurfaces]):
            fail(result, 'Common visibility anchor lacks an added face', leaf=li)
    result.update({'entities_preserved': len(new.entities), 'models_headnodes_preserved': len(new.models),
                   'collision_nodes_preserved': len(new.nodes), 'leaf_contents_preserved': len(new.leafs),
                   'old_faces_preserved_and_remapped': len(old.faces), 'retextured_face_count': len(changed_faces),
                   'added_faces': len(ADDED), 'added_face_mark_references': sum(refs.values()),
                   'added_face_holder_leaves': sorted(holders), 'enlarged_render_nodes': enlarged,
                   'original_file_prefix_preserved_except_descriptors': prefix == a})
    return finish(result)


def geometry(old, new):
    result = section()
    targets = {map_face(i) for i in RETEXTURED} | ADDED
    intervals = []
    winding = Counter()
    for i in sorted(targets):
        f = new.faces[i]
        p = polygon(new, f)
        pl = new.planes[f.planenum]
        normal = tuple(v * (-1 if f.side else 1) for v in pl.normal)
        if new.textures[new.texinfo[f.texinfo].miptex].name != 'rock01a_ewok':
            fail(result, 'Boundary face does not use original embedded rock', face=i)
        if f.styles != [0, 255, 255, 255] or f.lightofs < len(old.lighting):
            fail(result, 'Boundary face lacks newly baked ordinary style0 light', face=i)
        for v in p:
            if abs(sum(v[k] * pl.normal[k] for k in range(3)) - pl.dist) > .002:
                fail(result, 'Face vertex left its compiled plane', face=i)
        projected = [(v[1], v[2]) if abs(normal[0]) > .999 else (v[0], v[2]) for v in p]
        area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(projected, projected[1:] + projected[:1])) / 2
        if i in ADDED and area <= .04:
            fail(result, 'New +Y face winding disagrees with stock front-culling contract', face=i, area=area)
        winding[str(normal)] += 1
        values = []
        for axis in new.texinfo[f.texinfo].vecs:
            if abs(sum(axis[k] * pl.normal[k] for k in range(3))) > .001:
                fail(result, 'Texture axis is not projected along its boundary plane', face=i)
            values.append([sum(v[k] * axis[k] for k in range(3)) + axis[3] for v in p])
        extents = [math.ceil(max(v) / 16) - math.floor(min(v) / 16) + 1 for v in values]
        if min(extents) <= 1:
            fail(result, 'Boundary texture/lightmap projection collapsed', face=i)
        end = f.lightofs + 3 * extents[0] * extents[1]
        if end > len(new.lighting):
            fail(result, 'Boundary lightmap exceeds lighting lump', face=i)
        intervals.append((f.lightofs, end, i))
    intervals.sort()
    if intervals and intervals[0][0] != len(old.lighting):
        fail(result, 'Appended lighting does not begin at original prefix end')
    for a, b in zip(intervals, intervals[1:]):
        if a[1] != b[0]:
            fail(result, 'Boundary lightmaps overlap or leave unexplained appended bytes', faces=[a[2], b[2]])
    if intervals and intervals[-1][1] != len(new.lighting):
        fail(result, 'Appended lighting includes unaccounted bytes')
    rectangle = new.faces[FIRST]
    pts = polygon(new, rectangle)
    expected = {(1936., 3088., 3072.), (2320., 3088., 3072.),
                (2320., 3088., 3336.), (1936., 3088., 3336.)}
    if rectangle.planenum != 24 or rectangle.side != 0 or set(pts) != expected:
        fail(result, 'Missing original boundary rectangle differs from diagnosed physical wall')
    rect_count = 0
    rect_cap = cap_record(new, FIRST)
    for x in range(1944, 2320, 16):
        for z in range(3080, 3336, 16):
            n = hull0_contents(old, old.models[0].headnode[0], (x, 3088.125, z))
            s = hull0_contents(old, old.models[0].headnode[0], (x, 3087.875, z))
            if n != -1 or s != -2 or not inside(rect_cap, x, z):
                fail(result, 'New rectangle fails independently sampled EMPTY/SOLID boundary', point=[x, z], north=n, south=s)
            rect_count += 1
    seam_caps = [cap_record(new, i) for i in range(SECOND, SECOND + 3)]
    seam_index = CapIndex(seam_caps)
    root = old.nodes[old.models[0].headnode[0]]
    seam_count = 0
    for ix in range(2432, 2440):
        for iz in range(3072, 3584):
            x, z = ix + .5, iz + .5
            north = hull0_contents(old, root.children[0], (x, 3216., z))
            south = hull0_contents(old, root.children[1], (x, 3216., z))
            if north == -1 and south == -6:
                seam_count += 1
                if not seam_index.at(x, z, 0):
                    fail(result, 'Low SKY/EMPTY cut remains visually open', point=[x, z])
    for c in seam_caps:
        x = sum(p[0] for p in c['points']) / len(c['points'])
        z = sum(p[1] for p in c['points']) / len(c['points'])
        for sx, sz in [(x, z), *[(x * .7 + p[0] * .3, z * .7 + p[1] * .3) for p in c['points']]]:
            n = hull0_contents(old, root.children[0], (sx, 3216., sz))
            s = hull0_contents(old, root.children[1], (sx, 3216., sz))
            if n != -1 or s != -6:
                fail(result, 'New seam cap covers a wrong contents interface', face=c['face'], point=[sx, sz], north=n, south=s)
    hull_proofs = []
    for z in (3183.53, 3500.):
        south = hull_point_contents(new, new.models[0].headnode[1], (2436., 3215.875, z), True)
        north = hull_point_contents(new, new.models[0].headnode[1], (2436., 3216.125, z), True)
        if south != -2 or north != -1:
            fail(result, 'Low sky seam does not agree with existing player collision barrier', z=z, south=south, north=north)
        hull_proofs.append({'x': 2436., 'z': z, 'south_hull1': south, 'north_hull1': north})
    all_caps = []
    world = new.models[0]
    for i in range(world.firstface, world.firstface + world.numfaces):
        points = polygon(new, new.faces[i])
        pl = new.planes[new.faces[i].planenum]
        if abs(pl.normal[1]) > .999 and points and all(abs(p[1] - 3216.) < .002 for p in points):
            all_caps.append(cap_record(new, i))
    coverage = CapIndex(all_caps)
    surveys = []
    for label, xmin, xmax, zmin, zmax, step in [
            ('portal', -256, 2816, 2816, 5504, 16),
            ('whole_interface', old.models[0].mins[0], old.models[0].maxs[0],
             old.models[0].mins[2], old.models[0].maxs[2], 64)]:
        counts = Counter()
        misses = []
        for ix in range(math.floor(xmin / step), math.ceil(xmax / step)):
            x = (ix + .5) * step
            if not xmin <= x <= xmax:
                continue
            for iz in range(math.floor(zmin / step), math.ceil(zmax / step)):
                z = (iz + .5) * step
                if not zmin <= z <= zmax:
                    continue
                counts['grid_points'] += 1
                side, n, s = interface(old, x, z)
                if side is None:
                    continue
                counts['exposed_solid_interfaces'] += 1
                if not coverage.at(x, z, side):
                    counts['uncovered'] += 1
                    if len(misses) < 10:
                        misses.append([x, z, side])
        if counts['uncovered']:
            fail(result, 'Previously closed solid interface reopened', survey=label,
                 count=counts['uncovered'], examples=misses)
        surveys.append({'survey': label, 'spacing': step, 'counts': dict(counts)})
    for x, z, side in [(768, 3440, 1), (64, 3504, 1), (128, 3136, 1), (1920, 3120, 0)]:
        if not coverage.at(x, z, side):
            fail(result, 'Existing known-gap regression reopened', point=[x, z])
    for x in (1432, 1528, 1624):
        for z in (3096, 3120, 3152, 3200):
            if any(inside(c, x, z) for c in seam_caps):
                fail(result, 'New seam closure blocks the road aperture', point=[x, z])
    result.update({'boundary_faces_lit': len(targets), 'added_faces': len(ADDED),
                   'winding_normal_counts': dict(winding), 'rectangle_coverage_probes': rect_count,
                   'low_sky_seam_spacing': 1, 'low_sky_seam_covered_probes': seam_count,
                   'existing_join_coverage_surveys': surveys, 'low_seam_hull1_barrier_proofs': hull_proofs,
                   'material': 'rock01a_ewok', 'scope': 'Rendered boundary and finite compiled coverage grids; full-map traversal and native visual acceptance are not claimed.'})
    return finish(result)


def water_preservation(old, new):
    result = section()
    a = [e for e in old.entities if creek(e)]
    b = [e for e in new.entities if creek(e)]
    probes = 0
    for x in (-2000., -700., 0., 700., 2000.):
        for y in range(13480, 16560, 16):
            for z in (2808., 2816., 2890., 2935.99, 2936., 2936.01, 3208.):
                p = (1650.05 + x, float(y), z)
                before, after = contents(old, a, p), contents(new, b, p)
                probes += 1
                if before != after:
                    fail(result, 'Baked creek fluid overlay changed', point=p, before=before, after=after)
    m = new.models[164]
    top_faces = [i for i in range(m.firstface, m.firstface + m.numfaces)
                 if new.planes[new.faces[i].planenum].normal == (0., 0., 1.)
                 and new.planes[new.faces[i].planenum].dist == 2936. and new.faces[i].side == 0]
    if len(a) != 4 or [e.pairs for e in a] != [e.pairs for e in b] or len(top_faces) != 2:
        fail(result, 'Four baked animated-water instances or top surface inventory changed')
    if m.mins[2] + 1 >= 2936.:
        fail(result, 'Animated water top no longer passes stock renderer selection')
    result.update({'equivalent_float32_overlay_probes': probes, 'water_instances': len(b),
                   'baked_water_model': 164, 'admitted_upward_top_faces': top_faces,
                   'animated_texture_preserved': True, 'world_water_top_z': 2936.})
    return finish(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('base', 'bsp', 'report-source', 'report'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--actual-c', action='store_true')
    args = parser.parse_args()
    sys.setrecursionlimit(20000)
    inputs = {'base': args.base, 'bsp': args.bsp, 'report_source': args.report_source}
    if args.report.resolve() in {p.resolve() for p in inputs.values()}:
        parser.error('Report cannot overwrite a reviewed input')
    hashes = {k: sha(p) for k, p in inputs.items()}
    source = json.loads(args.report_source.read_text())
    metadata = section()
    if hashes['base'] != BASE_SHA or hashes['bsp'] != CANDIDATE_SHA:
        fail(metadata, 'Input differs from the frozen boundary review')
    if source.get('base_sha256') != hashes['base'] or source.get('output_sha256') != hashes['bsp']:
        fail(metadata, 'Builder report does not describe these inputs')
    old, new = BSP.load(args.base), BSP.load(args.bsp)
    report = {'input_sha256': hashes, 'metadata': finish(metadata),
              'actual_c_requested': args.actual_c, 'checker_source_sha256': sha(Path(__file__))}
    print('Checking immutable collision/entities and old face/material remapping', flush=True)
    report['preservation'] = preservation(args, old, new)
    print('Checking projected rock, lightmaps, missing wall and both join directions', flush=True)
    report['geometry'] = geometry(old, new)
    report['water_preservation'] = water_preservation(old, new)
    report['actual_c'] = actual_c(args.bsp) if args.actual_c else {
        'status': 'not_requested', 'pass': None, 'reason': 'No C road sweep requested'}
    report['inputs_unchanged_during_verification'] = hashes == {k: sha(p) for k, p in inputs.items()}
    report['static_pass'] = report['inputs_unchanged_during_verification'] and all(
        report[k]['pass'] for k in ('metadata', 'preservation', 'geometry', 'water_preservation'))
    report['pass'] = report['static_pass'] and (not args.actual_c or report['actual_c']['pass'] is True)
    report['native_visual_acceptance'] = None
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'pass': report['pass'], 'static_pass': report['static_pass'],
                      'bsp_sha256': hashes['bsp'], 'report_sha256': sha(args.report),
                      'report': str(args.report), 'actual_c': report['actual_c']['status']}, indent=2))
    return 0 if report['pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
