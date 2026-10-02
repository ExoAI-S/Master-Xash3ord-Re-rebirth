"""Independent static verifier for the private whole-map meadow grass pass.

Optionally run actual engine C floor/root traces with --actual-c in an x86
Visual Studio developer environment. No existing map, model, source, game,
server, profile, or identity is modified. Only the requested report is written.
The 16-unit coverage grid is statistical render geometry coverage, not a
complete movement audit or a frame-rate benchmark.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import shutil
import struct
import sys
import tempfile

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'Packaging-Work/BigWorld/tools'))
sys.path.insert(0, str(REPO / 'Design-Source/Daragoth-Meadow'))
from bsp30 import BSP
from meadow_surface import SurfaceIndex, coverage_survey
from test_daragoth_meadow import grass_roots

OLD_MODEL = 'models/plains/meadow_grass_patch.mdl'
NEW_MODEL = 'models/plains/meadow_low_grass.mdl'
TEXTURES = ('DPGRASS', 'medgrass2_ewoks')
SEAM = 3216
ROOT_LIMITS = (-10.6, .1)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def is_grass(entity, model):
    return entity.classname == 'env_model' and entity.get('model') == model


def failure(section, message, **details):
    section['failure_count'] += 1
    if len(section['failures']) < 20:
        section['failures'].append({'message': message, **details})


def section():
    return {'failure_count': 0, 'failures': []}


def preservation(base, candidate, source):
    result = section()
    old, new = base.read_bytes(), candidate.read_bytes()
    result['non_entity_lumps'] = []
    for i in range(1, 15):
        a, n = struct.unpack_from('<2i', old, 4 + i * 8)
        b, m = struct.unpack_from('<2i', new, 4 + i * 8)
        same = n == m and old[a:a+n] == new[b:b+m]
        result['non_entity_lumps'].append({'lump': i, 'identical': same,
                                          'sha256': hashlib.sha256(old[a:a+n]).hexdigest()})
        if not same:
            failure(result, 'Non-entity lump changed', lump=i)
    # The writer appends the new entity lump. This also verifies XASH extra
    # headers/lumps and every original byte outside the entity-lump descriptor.
    result['original_bytes_except_entity_descriptor_preserved'] = (
        len(new) >= len(old) and new[:4] == old[:4] and new[12:len(old)] == old[12:])
    if not result['original_bytes_except_entity_descriptor_preserved']:
        failure(result, 'Bytes outside entity-lump descriptor changed')
    old_bsp, new_bsp = BSP.load(base), BSP.load(candidate)
    removed = [e for e in old_bsp.entities if is_grass(e, OLD_MODEL)]
    expected = [e.pairs for e in old_bsp.entities if not is_grass(e, OLD_MODEL)]
    retained = [e.pairs for e in new_bsp.entities if not is_grass(e, NEW_MODEL)]
    result.update({'old_entities': len(old_bsp.entities), 'candidate_entities': len(new_bsp.entities),
                   'removed_old_grass': len(removed), 'preserved_non_grass_records': len(expected),
                   'ordered_non_grass_key_value_records_identical': expected == retained})
    if expected != retained:
        failure(result, 'Non-grass entity key/value record or order changed')
    if len(removed) != 760 or any(is_grass(e, OLD_MODEL) for e in new_bsp.entities):
        failure(result, 'Expected exactly 760 old patches removed')
    grass = [e for e in new_bsp.entities if is_grass(e, NEW_MODEL)]
    regions = Counter(e.get('msr_region') for e in grass)
    result['new_grass_regions'] = dict(regions)
    if regions != {'daragoth_plains': 840, 'daragoth': 80}:
        failure(result, 'Expected 840 field and 80 valley patches', counts=dict(regions))
    if len(new_bsp.entities) != 1880 or len(new_bsp.entities) > 1900:
        failure(result, 'Expected 1880 total entities below 1900 cap')
    result['nominal_network_reserve'] = 2047 - len(new_bsp.entities)
    required = {'dmg': '0', 'sequence': '0', 'framerate': '0', 'rendermode': '0',
                'renderamt': '255', 'scale': '1', 'skin': '0', 'body': '0'}
    names = set()
    for e in grass:
        bad = {k: e.get(k) for k, value in required.items() if e.get(k) != value}
        if bad:
            failure(result, 'New grass static/nonsolid settings changed', target=e.get('targetname'), settings=bad)
        target = e.get('targetname')
        if not target or target in names:
            failure(result, 'New grass targetname missing or duplicated', target=target)
        names.add(target)
    result['preserved_authored_solid_env_models'] = sum(
        e.classname == 'env_model' and e.get('dmg') not in (None, '0') for e in old_bsp.entities)
    for key, expected_value in [('removed_grass', 760), ('field_grass', 840),
                                ('valley_grass', 80), ('total_entities', 1880)]:
        if source.get(key) != expected_value:
            failure(result, 'Source report count mismatch', key=key, actual=source.get(key))
    result['pass'] = not result['failure_count']
    return result, new_bsp, grass


def model_check(path):
    data = path.read_bytes()
    if data[:4] != b'IDST' or struct.unpack_from('<i', data, 4)[0] != 10:
        raise ValueError('Expected native GoldSrc studio v10 grass model')
    roots = grass_roots(path)  # Asserts one neutral bone, reads compiled vertices.
    if not roots:
        raise ValueError('Compiled model has no neutral base roots')
    bodyparts, body_at = struct.unpack_from('<2i', data, 204)
    result = section()
    result['submodels'] = []
    vertices = []
    for i in range(bodyparts):
        _, nmodels, _, model_at = struct.unpack_from('<64s3i', data, body_at + i*76)
        if nmodels != 1:
            failure(result, 'Grass body must contain one permanently visible submodel', bodypart=i)
        for j in range(nmodels):
            record = struct.unpack_from('<64sif10i', data, model_at + j*112)
            nmeshes, mesh_at, nv, vertex_bones, vertex_at, nn = record[3:9]
            if any(bone != 0 for bone in data[vertex_bones:vertex_bones+nv]):
                failure(result, 'Grass vertex assigned to non-neutral bone', bodypart=i, submodel=j)
            points = [struct.unpack_from('<3f', data, vertex_at+12*k) for k in range(nv)]
            vertices.extend(points)
            submitted = triangles = 0
            for k in range(nmeshes):
                mesh_triangles, command_at, _, _, _ = struct.unpack_from('<5i', data, mesh_at+k*20)
                mesh_count = 0
                while True:
                    if command_at < 0 or command_at+2 > len(data):
                        raise ValueError('Grass triangle command outside compiled model')
                    count = struct.unpack_from('<h', data, command_at)[0]
                    command_at += 2
                    if count == 0:
                        break
                    count = abs(count)
                    if count < 3 or command_at+count*8 > len(data):
                        raise ValueError('Invalid grass strip/fan command')
                    for v, normal, _, _ in struct.iter_unpack('<4h', data[command_at:command_at+count*8]):
                        if not (0 <= v < nv and 0 <= normal < nn):
                            raise ValueError('Grass command vertex/normal index outside submodel')
                    command_at += count*8
                    submitted += count
                    mesh_count += count-2
                triangles += mesh_count
                if mesh_count != mesh_triangles:
                    failure(result, 'Command triangle count differs from mesh metadata', bodypart=i, mesh=k)
            result['submodels'].append({'bodypart': i, 'submodel': j, 'source_vertices': nv,
                                        'submitted_vertices': submitted, 'triangles': triangles})
            if submitted > 16384 or nv > 16384:
                failure(result, 'Grass exceeds stock renderer submodel vertex budget', bodypart=i, submitted=submitted, source=nv)
    result['unique_roots'] = len(roots)
    result['maximum_submodel_submitted_vertices'] = max(r['submitted_vertices'] for r in result['submodels'])
    result['bounds'] = [[min(p[k] for p in vertices) for k in range(3)],
                        [max(p[k] for p in vertices) for k in range(3)]]
    result['neutral_bone_contract_verified'] = True
    result['pass'] = not result['failure_count']
    return result, roots


def rotated(point, angles):
    """Stock entity basis: negate pitch, preserve yaw/roll, then rotate root."""
    pitch, yaw, roll = map(math.radians, angles)
    cp, sp = math.cos(-pitch), math.sin(-pitch)
    cr, sr, cy, sy = math.cos(roll), math.sin(roll), math.cos(yaw), math.sin(yaw)
    x, y, z = point
    forward = cp*x + sr*sp*y + cr*sp*z
    lateral = cr*y - sr*z
    return (cy*forward - sy*lateral, sy*forward + cy*lateral,
            -sp*x + sr*cp*y + cr*cp*z)


def road_center(y):
    return 250 * math.sin(y/3800)


def placement_check(bsp, grass, source, roots, index):
    result = section()
    records = source.get('placements', [])
    if len(records) != len(grass):
        raise ValueError('Source placement count differs from compiled grass entities')
    region = next(e for e in bsp.entities if e.classname == 'info_msr_region' and e.get('region') == 'daragoth_plains')
    offset = tuple(map(float, region.get('offset').split()))
    result['compiled_region_offset'] = offset
    result['offset_rounding_clearance_tolerance'] = .01
    errors = []
    centers = []
    minimum_road = math.inf
    for number, (entity, record) in enumerate(zip(grass, records)):
        origin = tuple(map(float, entity.get('origin').split()))
        angles = tuple(map(float, entity.get('angles').split()))
        name = entity.get('targetname')
        if name != f'meadow_polish_grass_{number:04d}':
            failure(result, 'Placement/entity target order mismatch', target=name, placement=number)
        if any(abs(a-b) > .00011 for a,b in zip(origin, record['origin'])) or any(
                abs(a-b) > .0000011 for a,b in zip(angles, (record['pitch'], record.get('yaw', 0), record['roll']))):
            failure(result, 'Compiled placement differs from source report', target=name)
        fields = entity.get('msr_region') == 'daragoth_plains'
        expected_region = 'fields' if fields else 'valley'
        if record.get('region') != expected_region:
            failure(result, 'Placement region differs from compiled entity', target=name)
        if fields and origin[1] <= SEAM or not fields and origin[1] >= SEAM:
            failure(result, 'Grass entity lies on wrong side of continuous seam', target=name)
        transformed = [rotated(p, angles) for p in roots]
        radius = max(math.hypot(p[0], p[1]) for p in transformed)
        lx, ly = origin[0]-offset[0], origin[1]-offset[1]
        center = index.at(origin[0], origin[1], TEXTURES)
        if center is None:
            failure(result, 'No compiled grass floor under patch center', target=name)
            continue
        centers.append((name, origin, center))
        if fields:
            # Sample the full possible footprint interval at <=4-unit spacing,
            # including bend extrema rather than only three endpoint samples.
            samples = max(1, math.ceil(radius*2/4))
            clearance = min(abs(lx-road_center(ly-radius+2*radius*j/samples))
                            for j in range(samples+1)) - radius - 128 - 48
            minimum_road = min(minimum_road, clearance)
            if clearance < -.01:
                failure(result, 'Grass footprint enters 128-half-width road plus 48 margin', target=name, clearance=clearance)
            for label, cx, cy, clear in [('stable', -1700, -7900, 800), ('ruins', 6500, 6200, 1050)]:
                if max(abs(lx-cx), abs(ly-cy)) < clear+radius-.01:
                    failure(result, 'Grass footprint enters actual protected landmark', target=name, landmark=label, local_center=[lx,ly])
        patch_errors = []
        for root_number, delta in enumerate(transformed):
            point = tuple(origin[k]+delta[k] for k in range(3))
            surface = index.at(point[0], point[1], TEXTURES)
            if surface is None:
                failure(result, 'No compiled grass surface under root', target=name, root=root_number)
                continue
            residual = point[2]-surface['z']
            errors.append(residual)
            patch_errors.append(residual)
            if not ROOT_LIMITS[0] <= residual <= ROOT_LIMITS[1]:
                failure(result, 'Compiled grass root outside burial/contact limits', target=name, root=root_number, residual=residual)
            if fields:
                x, y = point[0]-offset[0], point[1]-offset[1]
                if abs(x-road_center(y)) < 128+48-.01:
                    failure(result, 'Grass root enters road safety margin', target=name, root=root_number)
                for label, cx, cy, clear in [('stable', -1700, -7900, 800), ('ruins', 6500, 6200, 1050)]:
                    if max(abs(x-cx), abs(y-cy)) < clear-.01:
                        failure(result, 'Grass root enters actual protected landmark', target=name, root=root_number, landmark=label)
        if patch_errors and any(abs(a-b) > .02 for a,b in zip((min(patch_errors),max(patch_errors)), record['root_height_range'])):
            failure(result, 'Source root range differs from independent compiled replay', target=name)
    result.update({'patches': len(grass), 'root_probes': len(errors), 'roots_per_patch': len(roots),
                   'root_height_above_ground_range': [min(errors), max(errors)] if errors else None,
                   'root_limits': ROOT_LIMITS, 'minimum_field_road_footprint_clearance': minimum_road,
                   'landmarks_local': {'stable': [-1700,-7900], 'ruins': [6500,6200]},
                   'scope': 'Every compiled neutral root transformed from actual entity angles against rendered world grass surfaces. No collision or movement claim.'})
    result['pass'] = not result['failure_count']
    return result, centers


def actual_c_check(path, grass, roots, index, centers):
    if shutil.which('cl.exe') is None:
        return {'status': 'skipped', 'pass': None, 'reason': '--actual-c requested but cl.exe is unavailable; run in an x86 Visual Studio developer environment'}
    import test_daragoth_expanded_collision as collision
    result = section()
    result.update({'status': 'ran', 'root_traces': 0, 'center_hull1_traces': 0, 'chunk_limit': 5000})
    model = collision.MapCollision(path)
    residuals = []
    center_residuals = []
    with tempfile.TemporaryDirectory(prefix='msr-meadow-polish-qa-') as temp:
        folder = Path(temp)
        exe = collision.actual.build(folder)
        cases, info = [], []
        def flush_roots():
            for (name, point), trace in zip(info, model.traces(exe, folder, 0, cases)):
                residual = point[2]-trace['end'][2]
                residuals.append(residual)
                if trace['fraction'] == 1 or trace['startsolid'] or trace['allsolid'] or trace['normal'][2] < .7 or not ROOT_LIMITS[0] <= residual <= ROOT_LIMITS[1]:
                    failure(result, 'Actual hull0 root contact failed', target=name, residual=residual, trace=trace)
            result['root_traces'] += len(cases)
            cases.clear(); info.clear()
        for entity in grass:
            origin = tuple(map(float, entity.get('origin').split()))
            angles = tuple(map(float, entity.get('angles').split()))
            for root in roots:
                delta = rotated(root, angles)
                point = tuple(origin[k]+delta[k] for k in range(3))
                surface = index.at(point[0], point[1], TEXTURES)
                if surface is None:
                    failure(result, 'Missing rendered floor for actual root probe', target=entity.get('targetname'))
                    continue
                z = surface['z']
                cases.append(((point[0],point[1],z+32), (point[0],point[1],z-32)))
                info.append((entity.get('targetname'), point))
                if len(cases) == 5000:
                    flush_roots()
        if cases:
            flush_roots()
        for start in range(0,len(centers),5000):
            chunk = centers[start:start+5000]
            cases = [((p[0],p[1],s['z']+36+96), (p[0],p[1],s['z']+36-96)) for _,p,s in chunk]
            for (name, _, surface), trace in zip(chunk, model.traces(exe,folder,1,cases)):
                residual = trace['end'][2]-(surface['z']+36)
                center_residuals.append(residual)
                # A standing hull meets slopes above render z+36 because its
                # 16-unit horizontal half-width expands the collision plane.
                # The returned floor height is evidence, not a z+36 equality.
                if trace['fraction'] == 1 or trace['startsolid'] or trace['allsolid'] or trace['normal'][2] < .7:
                    failure(result, 'Actual standing hull1 center floor failed', target=name, floor_residual=residual, trace=trace)
            result['center_hull1_traces'] += len(cases)
    result['root_height_above_ground_range'] = [min(residuals),max(residuals)] if residuals else None
    result['standing_floor_height_above_render_plus36_range'] = [min(center_residuals),max(center_residuals)] if center_residuals else None
    result['engine_pm_trace_sha256'] = sha(REPO/'Engine-Source/Xash3D/engine/common/pm_trace.c')
    result['scope'] = 'Actual engine C static world hull0 root floors and standing hull1 center floors. No full movement path, dynamic entity, native frame-rate, or visibility test.'
    result['pass'] = not result['failure_count']
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('base', 'bsp', 'report-source', 'grass-model', 'report'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--actual-c', action='store_true')
    args = parser.parse_args()
    sys.setrecursionlimit(20000)
    inputs = {'base': args.base, 'bsp': args.bsp, 'source': args.report_source, 'grass_model': args.grass_model}
    if args.report.resolve() in {p.resolve() for p in inputs.values()}:
        parser.error('Report must not overwrite an input')
    hashes = {key:sha(path) for key,path in inputs.items()}
    source = json.loads(args.report_source.read_text())
    report = {'input_sha256': hashes, 'actual_c_requested': args.actual_c}
    metadata = section()
    for name,key in [('base','base_sha256'), ('bsp','sha256'), ('grass_model','grass_model_sha256')]:
        if source.get(key) != hashes[name]:
            failure(metadata, 'Input hash differs from frozen source report', input=name, expected=source.get(key), actual=hashes[name])
    metadata['pass'] = not metadata['failure_count']
    report['metadata'] = metadata
    print('Checking preserved data, entities, and compiled model', flush=True)
    report['preservation'], bsp, grass = preservation(args.base,args.bsp,source)
    report['model'], roots = model_check(args.grass_model)
    index = SurfaceIndex(bsp)
    print('Checking every compiled grass root and road/landmark footprint', flush=True)
    report['placements'], centers = placement_check(bsp,grass,source,roots,index)
    print('Surveying both regions at 16-unit spacing (statistical render coverage)', flush=True)
    report['coverage'] = {}
    for region,texture in [('daragoth_plains','DPGRASS'), ('daragoth','medgrass2_ewoks')]:
        placements = [{'origin':list(map(float,e.get('origin').split())),
                       'radius':max(math.hypot(*rotated(root,tuple(map(float,e.get('angles').split())))[:2]) for root in roots)}
                      for e in grass if e.get('msr_region') == region]
        report['coverage'][region] = coverage_survey(index,placements,spacing=16,texture_names=(texture,),min_normal_z=.88)
    if args.actual_c:
        print('Checking optional actual C static world floors', flush=True)
        report['actual_c'] = actual_c_check(args.bsp,grass,roots,index,centers)
    else:
        report['actual_c'] = {'status':'not_requested','pass':None,'reason':'Static checks only; no C harness compiled or executed'}
    after = {key:sha(path) for key,path in inputs.items()}
    report['inputs_unchanged_during_verification'] = hashes == after
    if hashes != after:
        report['changed_input_sha256'] = after
    report['static_pass'] = hashes == after and all(report[key]['pass'] for key in ('metadata','preservation','model','placements'))
    report['pass'] = report['static_pass'] and (not args.actual_c or report['actual_c']['pass'] is True)
    report['scope'] = 'Independent preservation/count/model/root/clearance checks and 16-unit statistical rendered-surface coverage. Actual C static floor checks only when explicitly run. No complete foot-by-foot movement, dynamic-entity, PVS, native appearance, or performance claim.'
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'pass':report['pass'],'static_pass':report['static_pass'],'bsp_sha256':hashes['bsp'],
                      'section_pass':{key:report[key]['pass'] for key in ('metadata','preservation','model','placements')},
                      'actual_c':report['actual_c']['status'],'report':str(args.report)},indent=2))
    return 0 if report['pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
