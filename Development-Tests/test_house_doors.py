"""Independent compiled six-house hinged-door QA on frozen meadow8388.

Checks preserve all original records/world hulls/PVS, independently verifies
the new leaf and four analytic collision hulls, and uses the actual engine C
tracer for closed/open standing-player entrance paths. No builder imports,
game launches, live-runtime access, or input writes. Native use/pusher/visual
acceptance is still required separately.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import itertools
import json
import math
from pathlib import Path
import re
import shutil
import struct
import sys
import tempfile

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / 'Packaging-Work/BigWorld/tools'), str(REPO / 'Development-Tests')]
from bsp30 import BSP
import test_engine_hull_trace as actual

BASE_SHA = '8388e76d2653f4acc09abc633b25c8ce94b816a9e99fb10743e8838edb37fdc3'
PIVOTS = {
    'inn': (-2893.9527, 5280., 3174.),
    'workshop': (-2949.9527, 6360., 3174.),
    'cottage_south': (-1563.9527, 4920., 3174.),
    'cottage_north': (-1563.9527, 6820., 3174.),
    'bakery': (-3005.9527, 7160., 3174.),
    'farmhouse': (-3159.9527, 4440., 3174.),
}
LEAF_MIN, LEAF_MAX = (-3., 0., -45.), (3., 72., 45.)
HULL_EXPANSIONS = ((0., 0., 0.), (16., 16., 36.), (32., 32., 32.), (16., 16., 18.))
EMPTY, SOLID = -1, -2


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def section():
    return {'failure_count': 0, 'failures': []}


def check(result, condition, message, **evidence):
    if not condition:
        result['failure_count'] += 1
        if len(result['failures']) < 24:
            result['failures'].append({'message': message, **evidence})


def finish(result):
    result['pass'] = result['failure_count'] == 0
    return result


def f32(value):
    return struct.unpack('<f', struct.pack('<f', value))[0]


def load(path):
    bsp = BSP.load(path)
    data = path.read_bytes()
    bsp.qa_lumps = [data[o:o+n] for o,n in [struct.unpack_from('<ii',data,4+8*i) for i in range(15)]]
    return bsp


def records(bsp):
    return [s for s in re.findall(rb'\{[^{}]*\}', bsp.qa_lumps[0])]


def entities(bsp):
    return [dict(re.findall(r'"([^\"]*)"\s+"([^\"]*)"', row.decode('latin1'))) for row in records(bsp)]


def polygon(bsp, face):
    points = []
    for index in bsp.surfedges[face.firstedge:face.firstedge + face.numedges]:
        edge = bsp.edges[abs(index)]
        points.append(bsp.vertexes[edge[0 if index >= 0 else 1]])
    return points


def model_hull(bsp, model, number):
    source = [(n.planenum, *n.children) for n in (bsp.nodes if number == 0 else bsp.clipnodes)]
    if number == 0:
        source = [(plane, *[child if child >= 0 else bsp.leafs[-child - 1].contents for child in children])
                  for plane, *children in source]
    output, active = [], set()
    def copy(node):
        if node < 0:
            return node
        if node >= len(source) or node in active:
            raise ValueError('Invalid/cyclic compiled model hull')
        active.add(node)
        at = len(output)
        output.append(None)
        plane, a, b = source[node]
        if not 0 <= plane < len(bsp.planes):
            raise ValueError('Invalid model hull plane reference')
        output[at] = (plane, copy(a), copy(b))
        active.remove(node)
        return at
    head = copy(model.headnode[number])
    if len(output) > 32767:
        raise ValueError('Native BSP30 per-model clipnode limit exceeded')
    return head, output


def point(bsp, hull, value):
    node, clips = hull
    p = [f32(v) for v in value]
    while node >= 0:
        plane, a, b = clips[node]
        q = bsp.planes[plane]
        if q.type < 3:
            distance = f32(p[q.type] - q.dist)
        else:
            distance = f32(f32(f32(f32(p[0] * q.normal[0]) + f32(p[1] * q.normal[1])) + f32(p[2] * q.normal[2])) - q.dist)
        node = a if distance >= 0 else b
    return node


def world_point(pivot, value, yaw):
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    x, y, z = value
    return (pivot[0] + c*x - s*y, pivot[1] + s*x + c*y, pivot[2] + z)


def local_point(pivot, value, yaw):
    # Exactly the yaw-only inverse of PM_PlayerTraceExt's entity matrix. Hull
    # clip_mins equals normal-player mins, so the model offset is its origin.
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    x, y, z = [value[i] - pivot[i] for i in range(3)]
    return (c*x + s*y, -s*x + c*y, z)


def preservation(old, new):
    result = section()
    prefixes = {}
    for lump in range(1, 15):
        prefixes[str(lump)] = new.qa_lumps[lump].startswith(old.qa_lumps[lump])
        check(result, prefixes[str(lump)], 'Original non-entity records changed', lump=lump)
    check(result, old.qa_lumps[4] == new.qa_lumps[4], 'Original PVS changed')
    check(result, old.extra_lumps == new.extra_lumps, 'Original XASH extra data changed')
    check(result, len(new.models) == len(old.models) + 1, 'Expected exactly one appended shared brush model')
    oldrows, newrows = records(old), records(new)
    check(result, len(oldrows) == 1047 and newrows[:len(oldrows)] == oldrows and len(newrows) == 1053,
          'Expected six new entities after all1047 exact original ordered records')
    olddoors = [e for e in entities(old) if e.get('classname') in ('func_door', 'func_door_rotating')]
    check(result, len(olddoors) == 8, 'Frozen original eight-door inventory differs')
    result.update({'original_non_entity_prefixes': prefixes, 'original_entities_preserved': len(oldrows),
                   'original_doors_preserved': len(olddoors), 'new_entities': len(newrows)-len(oldrows),
                   'original_models_preserved': len(old.models), 'world_collision_and_pvs_preserved': all(prefixes.values())})
    return finish(result)


def door_entities(old, new):
    result, found = section(), {}
    rows = entities(new)[len(records(old)):]
    for e in rows:
        name = e.get('targetname', '')
        role = name.removeprefix('greenhollow_door_')
        check(result, role in PIVOTS and role not in found, 'Unknown/duplicate new house door target', target=name)
        if role not in PIVOTS:
            continue
        origin = tuple(map(float, e.get('origin', 'nan nan nan').split()))
        check(result, len(origin) == 3 and all(abs(origin[i]-PIVOTS[role][i]) < .002 for i in range(3)),
              'Door hinge does not match independently surveyed clean72-unit policy', role=role, origin=origin)
        check(result, e.get('classname') == 'func_door_rotating' and e.get('model') == '*165', 'Door is not the new shared hinged brush', role=role)
        check(result, int(e.get('spawnflags', '-1')) == 288 and float(e.get('wait', 'nan')) == 3 and float(e.get('dmg', 'nan')) == 0,
              'Door use/toggle/wait/damage policy differs', role=role)
        check(result, tuple(map(float, e.get('angles', '0 0 0').split())) == (0.,0.,0.) and
              float(e.get('distance', 'nan')) == 90 and float(e.get('speed', 'nan')) > 0,
              'Door closed-angle/90-degree/speed policy differs', role=role)
        check(result, 'master' not in e and 'health' not in e and 'target' not in e, 'Unexpected lock/health/target semantics', role=role)
        found[role] = origin
    check(result, set(found) == set(PIVOTS), 'Missing required house door')
    result.update({'doors': {k:list(v) for k,v in found.items()}, 'door_count': len(found),
                   'closed_yaw': 0, 'tested_open_yaws': [-90,90], 'hinge_north_inset_from_original_south_jamb': 4})
    return finish(result), found


def shape_and_hulls(old, new):
    result = section()
    model = new.models[-1]
    check(result, tuple(model.origin) == (0.,0.,0.) and model.numfaces == 6, 'Shared leaf has nonzero model origin or non-box face inventory')
    check(result, model.firstface == len(old.faces) and model.firstface + model.numfaces == len(new.faces), 'Appended model face range differs')
    used = [p for f in new.faces[model.firstface:model.firstface+model.numfaces] for p in polygon(new,f)]
    bounds = ([min(p[k] for p in used) for k in range(3)], [max(p[k] for p in used) for k in range(3)]) if used else ([],[])
    check(result, bounds[0] == list(LEAF_MIN) and bounds[1] == list(LEAF_MAX), 'Actual rendered leaf bounds differ from6x72x90', bounds=bounds)
    check(result, all(model.mins[k] <= LEAF_MIN[k] and model.maxs[k] >= LEAF_MAX[k] and
              LEAF_MIN[k]-model.mins[k] <= 1.001 and model.maxs[k]-LEAF_MAX[k] <= 1.001 for k in range(3)),
          'Model bounding box does not tightly enclose leaf')
    directions, lightmap_bytes = [], 0
    for fi in range(model.firstface, model.firstface+model.numfaces):
        f = new.faces[fi]; pts = polygon(new,f); plane = new.planes[f.planenum]
        normal = [v*(1 if not f.side else -1) for v in plane.normal]
        directions.append(tuple(normal))
        check(result, len(pts) == 4 and len(set(map(tuple,pts))) == 4 and all(abs(sum(plane.normal[k]*p[k] for k in range(3))-plane.dist)<.002 for p in pts),
              'Door face is non-quad/degenerate/off-plane', face=fi)
        cross = [0.,0.,0.]
        for a,b in zip(pts,pts[1:]+pts[:1]):
            for k in range(3): cross[k] += a[(k+1)%3]*b[(k+2)%3]-a[(k+2)%3]*b[(k+1)%3]
        check(result, sum(cross[k]*normal[k] for k in range(3)) < 0, 'Door face winding does not match clockwise front-face convention', face=fi)
        ti = new.texinfo[f.texinfo]
        check(result, new.textures[ti.miptex].name == 'DPWOOD', 'Door material is not preserved village timber', face=fi)
        check(result, ((ti.flags >> 16) & 0xffff) == 0xffff and ti.flags & 0xffff == 0,
              'Door texinfo must use default16-unit lightmap sentinel without inherited64-step faceinfo', face=fi, flags=ti.flags)
        uv = [[sum(axis[k]*p[k] for k in range(3))+axis[3] for p in pts] for axis in ti.vecs]
        sizes = [math.ceil(max(v)/16)-math.floor(min(v)/16)+1 for v in uv]
        amount = 3*sizes[0]*sizes[1]
        check(result, f.styles == [0,255,255,255] and f.lightofs >= len(old.lighting) and f.lightofs+amount <= len(new.lighting),
              'Door style0 lightmap is invalid or aliases original lighting', face=fi, sizes=sizes)
        lightmap_bytes += amount
    check(result, set(directions) == {(1.,0.,0.),(-1.,0.,0.),(0.,1.,0.),(0.,-1.,0.),(0.,0.,1.),(0.,0.,-1.)}, 'Leaf does not have six correctly outward box planes')
    hulls, sample_count = [], 0
    for index, expansion in enumerate(HULL_EXPANSIONS):
        hull = model_hull(new,model,index); hulls.append(hull)
        lo = [LEAF_MIN[k]-expansion[k] for k in range(3)]
        hi = [LEAF_MAX[k]+expansion[k] for k in range(3)]
        axes = [[lo[k]-1,lo[k]-.1,lo[k]+.1,(lo[k]+hi[k])/2,hi[k]-.1,hi[k]+.1,hi[k]+1] for k in range(3)]
        for p in itertools.product(*axes):
            wanted = SOLID if all(lo[k] < p[k] < hi[k] for k in range(3)) else EMPTY
            got = point(new,hull,p); sample_count += 1
            check(result, got == wanted, 'Compiled door hull differs from analytic expanded box', hull=index, point=p, expected=wanted, actual=got)
    result.update({'rendered_bounds': bounds, 'model_bounds': [model.mins,model.maxs], 'face_count': model.numfaces,
                   'collision_hulls_checked': 4, 'analytic_box_samples': sample_count, 'lightmap_bytes_checked': lightmap_bytes,
                   'hull_heads': list(model.headnode), 'runtime_hull_nodes': [len(h[1]) for h in hulls]})
    return finish(result), hulls


def sweep_and_reach(old, pivots):
    result = section(); world = model_hull(old,old.models[0],0)
    count, solids, contacts = 0, [], Counter()
    for role,pivot in pivots.items():
        for yaw in range(-90,91,5):
            for local in itertools.product((-3.,-1.5,0.,1.5,3.), (0.,.5,1.,2.,4.,10.,20.,36.,50.,71.,72.), (-44.,0.,44.)):
                p = world_point(pivot,local,yaw); contents = point(old,world,p); count += 1
                if contents == SOLID:
                    contacts[role] += 1
                    if len(solids) < 12: solids.append({'role':role,'yaw':yaw,'local':local,'world':p})
        # A normal standing player at +/-40 is within64 of the closed leaf's
        # actual bounding box, with eye height below the lintel and clear ray.
        for side in (-1,1):
            player = (pivot[0]+40*side,pivot[1]+36,3128.04+36)
            eye = (player[0],player[1],player[2]+28)
            near = (pivot[0]+3*side,pivot[1]+36,eye[2])
            distance = abs(player[0]-near[0])
            check(result, distance < 64 and eye[2] < pivot[2]+45, 'Normal use approach cannot reach the door below lintel', role=role,side=side)
            for t in (.2,.4,.6,.8):
                p = tuple(eye[k]+(near[k]-eye[k])*t for k in range(3))
                check(result, point(old,world,p) == EMPTY, 'Use approach passes through an original wall/ceiling', role=role,side=side,world=p)
    check(result, not contacts, 'Clean72-unit leaf sweep overlaps original world solid', contacts=dict(contacts), examples=solids)
    result.update({'leaf_world_samples':count,'solid_contacts_by_house':dict(contacts),'solid_examples':solids,
                   'sweep_yaw_step':5,'door_use_search_radius':64,'normal_player_height':72,'entrance_clear_height':92,
                   'original_entrance_width':80,'usable_fully_open_aperture_width':73,
                   'normal_standing_center_corridor_width':41,'tested_center_offsets_from_doorway_center':[-12,0,12],
                   'scope':'Discrete leaf sweep and normal-use approach geometry. Dynamic pusher reversal, real use selection, and appearance require native checks.'})
    return finish(result)


def compiler_mapping(old, new, report):
    result = section()
    paths = {name:Path(report['compiler'][name+'_path']) for name in ('map','wad','bsp')}
    hashes = {name:sha(path) for name,path in paths.items()}
    for name,value in hashes.items():
        check(result, value == report['compiler'][name+'_sha256'], 'Isolated compiled source changed', input=name)
    source = load(paths['bsp']); model = source.models[1]
    maps = {name:{int(a):int(b) for a,b in mapping.items()} for name,mapping in report['record_mappings'].items()}
    collections = {'planes':'planes','vertices':'vertexes','edges':'edges','texinfos':'texinfo',
                   'faces':'faces','nodes':'nodes','leaves':'leafs','clipnodes':'clipnodes'}
    for name,attribute in collections.items():
        check(result, len(set(maps[name].values())) == len(maps[name]) and
              set(maps[name].values()) == set(range(len(getattr(old,attribute)),len(getattr(new,attribute)))),
              'Source mapping is not a bijection onto exactly the appended range', records=name)
    pm,vm,em,tm,fm,nm,lm,cm = [maps[name] for name in ('planes','vertices','edges','texinfos','faces','nodes','leaves','clipnodes')]
    for a,b in pm.items(): check(result, source.planes[a] == new.planes[b], 'Mapped plane differs', source=a,destination=b)
    for a,b in vm.items(): check(result, source.vertexes[a] == new.vertexes[b], 'Mapped vertex differs', source=a,destination=b)
    for a,b in em.items(): check(result, [vm[v] for v in source.edges[a]] == list(new.edges[b]), 'Mapped edge differs', source=a,destination=b)
    for a,b in tm.items():
        s,n = source.texinfo[a],new.texinfo[b]
        check(result, s.vecs == n.vecs and source.textures[s.miptex].raw == new.textures[n.miptex].raw,
              'Mapped texture UV axes/indexed pixels differ', source=a,destination=b)
    for a,b in fm.items():
        s,n = source.faces[a],new.faces[b]
        check(result, (pm[s.planenum],s.side,s.numedges,tm[s.texinfo],s.styles) ==
              (n.planenum,n.side,n.numedges,n.texinfo,n.styles) and polygon(source,s) == polygon(new,n),
              'Mapped render face differs', source=a,destination=b)
        axes = [[sum(v[k]*p[k] for k in range(3))+v[3] for p in polygon(source,s)] for v in source.texinfo[s.texinfo].vecs]
        amount = 3*math.prod(math.ceil(max(v)/16)-math.floor(min(v)/16)+1 for v in axes)
        check(result, source.lighting[s.lightofs:s.lightofs+amount] == new.lighting[n.lightofs:n.lightofs+amount],
              'Mapped compiler lightmap RGB differs', source=a,destination=b)
    for a,b in nm.items():
        s,n = source.nodes[a],new.nodes[b]
        children = [nm[ch] if ch >= 0 else -1-lm[-1-ch] for ch in s.children]
        check(result, (pm[s.planenum],children,s.mins,s.maxs,s.numfaces) == (n.planenum,n.children,n.mins,n.maxs,n.numfaces) and
              (not s.numfaces or fm[s.firstface] == n.firstface), 'Mapped render node differs', source=a,destination=b)
    for a,b in lm.items():
        s,n = source.leafs[a],new.leafs[b]
        sm = source.marksurfaces[s.firstmarksurface:s.firstmarksurface+s.nummarksurfaces]
        nmks = new.marksurfaces[n.firstmarksurface:n.firstmarksurface+n.nummarksurfaces]
        check(result, s.contents == n.contents and n.visofs == -1 and s.mins == n.mins and s.maxs == n.maxs and
              s.ambient == n.ambient and [fm[v] for v in sm] == nmks,
              'Mapped leaf/face references differ or PVS belongs to isolated room', source=a,destination=b)
    for a,b in cm.items():
        s,n = source.clipnodes[a],new.clipnodes[b]
        check(result, pm[s.planenum] == n.planenum and [cm[ch] if ch >= 0 else ch for ch in s.children] == n.children,
              'Mapped clipnode differs', source=a,destination=b)
    heads = [nm[model.headnode[0]], *[cm[h] if h >= 0 else h for h in model.headnode[1:]]]
    check(result, heads == new.models[-1].headnode, 'Shared brush model hull-head mapping differs')
    commands = report['compiler']['compiler_commands']
    check(result, len(commands) == 4 and all(c['returncode'] == 0 and sha(Path(c['tool'])) == c['tool_sha256'] for c in commands),
          'Isolated compiler did not run all four frozen tool passes')
    result.update({'source_input_sha256':hashes,'mapped_record_counts':{k:len(v) for k,v in maps.items()},
                   'compiler_passes':len(commands),'model_hull_heads':heads})
    return finish(result), paths, hashes


def actual_c(new, pivots, hulls):
    result = section(); result['status'] = 'ran'
    if shutil.which('cl.exe') is None:
        return {'status':'skipped','pass':False,'reason':'Requested actual C requires cl.exe in isolated developer environment'}
    planes = [(*p.normal,p.dist,p.type) for p in new.planes]
    world = model_hull(new,new.models[0],1); door = hulls[1]
    records_out = []; total = 0
    with tempfile.TemporaryDirectory(prefix='msr-house-door-qa-') as temp:
        folder = Path(temp); exe = actual.build(folder)
        for role,pivot in pivots.items():
            paths = []
            for y in (24.,36.,48.):
                a,b = ((pivot[0]-80,pivot[1]+y,3164.04),(pivot[0]+80,pivot[1]+y,3164.04))
                paths.extend(((a,b),(b,a)))
            world_traces = actual.batch(exe,folder,planes,world[1],world[0],paths)
            total += len(world_traces)
            for case,t in zip(paths,world_traces):
                check(result, not t['startsolid'] and not t['allsolid'] and t['fraction'] == 1,
                      'Original world standing passage is obstructed',role=role,case=case,trace=t)
            for yaw in (0,-90,90):
                local = [(local_point(pivot,a,yaw),local_point(pivot,b,yaw)) for a,b in paths]
                traces = actual.batch(exe,folder,planes,door[1],door[0],local); total += len(traces)
                for case,t in zip(paths,traces):
                    good = not t['startsolid'] and not t['allsolid'] and (t['fraction'] < 1 if yaw == 0 else t['fraction'] == 1)
                    check(result, good, 'Closed door does not block / open door does not clear standing entrance',role=role,yaw=yaw,case=case,trace=t)
                records_out.append({'role':role,'yaw':yaw,'traces':traces,'world_passage_clear':all(t['fraction']==1 and not t['startsolid'] for t in world_traces)})
    result.update({'trace_count':total,'closed_standing_block_traces':36,'open_standing_clear_traces':72,'world_standing_clear_traces':36,
                   'door_states':records_out,'engine_pm_trace_sha256':sha(REPO/'Engine-Source/Xash3D/engine/common/pm_trace.c'),
                   'scope':'Actual engine recursive hull tracer with independently reproduced yaw-only PM_PlayerTraceExt inverse transform. Normal standing hull1, three safe lanes, both traversal directions. No dynamic/native use or pusher claim.'})
    return finish(result)


def verify(args):
    inputs = {'base':args.base,'bsp':args.bsp,'report_source':args.build_report}
    hashes = {key:sha(path) for key,path in inputs.items()}
    metadata = section(); source = json.loads(args.build_report.read_text())
    builder = REPO/'Design-Source/Daragoth-Meadow/build_house_doors.py'; builder_sha = sha(builder)
    check(metadata, hashes['base'] == BASE_SHA and hashes['bsp'] == args.expected_bsp_sha, 'Frozen base/candidate hash differs')
    check(metadata, source.get('base_sha256') == hashes['base'] and source.get('output_sha256') == hashes['bsp'], 'Builder report identifies a different map')
    check(metadata, source.get('builder_source_sha256') == builder_sha, 'Current door builder differs from frozen report')
    old,new = load(args.base),load(args.bsp)
    preservation_result = preservation(old,new)
    entity_result,pivots = door_entities(old,new)
    geometry,hulls = shape_and_hulls(old,new)
    mapping,source_paths,source_hashes = compiler_mapping(old,new,source)
    sweep = sweep_and_reach(old,pivots)
    c = actual_c(new,pivots,hulls) if args.actual_c else {'status':'not_requested','pass':None}
    shared = REPO/'Design-Source/Daragoth-Meadow/house_doors.py'
    village = REPO/'Design-Source/Daragoth-Meadow/village.py'
    check(metadata, sha(shared) == source.get('shared_source_sha256') and sha(village) == source.get('village_generator_sha256'),
          'Shared leaf/settings or village generator changed')
    unchanged = (all(sha(path)==hashes[key] for key,path in inputs.items()) and sha(builder)==builder_sha and
                 all(sha(path)==source_hashes[key] for key,path in source_paths.items()) and
                 sha(shared)==source.get('shared_source_sha256') and sha(village)==source.get('village_generator_sha256'))
    report = {'input_sha256':hashes,'checker_source_sha256':sha(Path(__file__)),'builder_source_sha256':builder_sha,
              'metadata':finish(metadata),'preservation':preservation_result,'entities':entity_result,'geometry':geometry,
              'compiler_mapping':mapping,'sweep_and_reach':sweep,'actual_c_requested':args.actual_c,'actual_c':c,'inputs_unchanged_during_verification':unchanged,
              'native_acceptance':None}
    report['static_pass'] = unchanged and all(report[key]['pass'] for key in ('metadata','preservation','entities','geometry','compiler_mapping','sweep_and_reach'))
    report['pass'] = report['static_pass'] and (not args.actual_c or c['pass'] is True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('base','bsp','build-report','report'):
        parser.add_argument('--'+flag,type=Path,required=True)
    parser.add_argument('--expected-bsp-sha',required=True)
    parser.add_argument('--actual-c',action='store_true')
    args = parser.parse_args(); sys.setrecursionlimit(20000)
    if not re.fullmatch('[0-9a-f]{64}',args.expected_bsp_sha): parser.error('Supply independent lowercase frozen SHA256')
    if args.report.exists() or args.report.resolve() in {p.resolve() for p in (args.base,args.bsp,args.build_report)}:
        parser.error('Only a new independent QA receipt may be written')
    report = verify(args)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({key:report[key] for key in ('pass','static_pass','input_sha256','checker_source_sha256')},indent=2))
    sys.exit(0 if report['pass'] else 1)
