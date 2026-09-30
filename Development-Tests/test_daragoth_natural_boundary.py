"""Read-only compiled-hull audit of Daragoth's natural boundary terrain.

Run in the Visual Studio x86 developer environment. The public audit() accepts
an already-loaded MapCollision and actual C tracer. Source data only identifies
scenery exclusions; acceptance uses the frozen BSP's actual C collision results.
An additional x86 executable links unchanged production PM_WalkMove,
PM_FlyMove, PM_ClipVelocity and PM_Accelerate to that same C hull tracer.
This is bounded world movement evidence, not a full PM_PlayerMove/gameplay test.
"""
from __future__ import annotations
import argparse, hashlib, json, math, struct, subprocess, sys, tempfile
from pathlib import Path
from collections import deque

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'Development-Tests'))
import test_daragoth_expanded_collision as qa

WALK_NORMAL = .7
SKY_TOP = 4096


def _world(p, offset):
    return tuple(p[i] + offset[i] for i in range(3))


def _floor_ok(t):
    return t['fraction'] < 1 and not t['startsolid'] and not t['allsolid'] and not t['inwater'] and t['normal'][2] > .05


def _transects():
    lines = []
    for side in (-1, 1):
        for y in (-6500, -2500, 4500, 7500):
            lines.append({'name': ('west' if side < 0 else 'east') + '-y' + str(y),
                          'zone': 'west' if side < 0 else 'east', 'direction': (side, 0),
                          'points': [(side * x, y) for x in range(8400, 11921, 40)],
                          'progress': [(x - 8400) / 3600 for x in range(8400, 11921, 40)]})
    for x in (-8000, -5000, 3500, 6500, 9000):
        ys = list(range(7040, 10561, 40))
        lines.append({'name': 'north-x' + str(x), 'zone': 'north', 'direction': (0, 1),
                      'points': [(x, y) for y in ys], 'progress': [(y - 7040) / 3600 for y in ys]})
    for x in (-8000, -6500, 3000, 6000, 9000):
        ys = list(range(-8200, -10001, -20))
        lines.append({'name': 'entrance-bank-x' + str(x), 'zone': 'entrance-bank', 'direction': (0, -1),
                      'points': [(x, y) for y in ys], 'progress': [(-8200 - y) / 1800 for y in ys]})
    return lines


def _step_cases(p, direction, distance=8.6666667):
    q = (p[0] + direction[0] * distance, p[1] + direction[1] * distance, p[2])
    up = (p[0], p[1], p[2] + 18)
    above = (q[0], q[1], q[2] + 18)
    return [(p, q), (p, up), (up, above), (above, q)]


def _step_clear(traces):
    direct, up, across, down = traces
    if any(t['startsolid'] or t['allsolid'] for t in traces):
        return False
    if direct['fraction'] == 1:
        return True
    return up['fraction'] == 1 and across['fraction'] == 1 and (down['fraction'] == 1 or down['normal'][2] >= WALK_NORMAL)


def _consecutive_barrier_runs(contacts):
    """Measure physical bands, rather than a percentage/count of a long line.

    A band must have genuine steep floors in BOTH world hull0 and standing
    hull1, plus rejected actual 18-unit step routes at consecutive samples.
    The required 256-unit sampled span is eight standing-hull widths. The
    maximum 40-unit spacing and retained movement/connectivity checks make
    scattered steep contacts insufficient. This remains sampled walking
    evidence, not a claim about jumping or the full native physics solver.
    """
    runs=[];current=[]
    for contact in sorted(contacts,key=lambda c:c['sample_index']):
        if current:
            previous=current[-1]
            distance=math.dist(previous['sample']['local_xy'],contact['sample']['local_xy'])
            if contact['sample_index']!=previous['sample_index']+1 or not 0<distance<=40.0001:
                runs.append(current);current=[]
        current.append(contact)
    if current:runs.append(current)
    result=[]
    for contacts in runs:
        a,b=contacts[0],contacts[-1]
        spacing=[math.dist(c['sample']['local_xy'],d['sample']['local_xy'])for c,d in zip(contacts,contacts[1:])]
        span=math.dist(a['sample']['local_xy'],b['sample']['local_xy'])
        result.append({'samples':len(contacts),'sampled_span_units':span,
                       'local_xy_endpoints':[a['sample']['local_xy'],b['sample']['local_xy']],
                       'maximum_sample_spacing':max(spacing,default=0),
                       'hull0_normal_z_range':[min(c['floor_hull0']['normal'][2]for c in contacts),max(c['floor_hull0']['normal'][2]for c in contacts)],
                       'hull1_normal_z_range':[min(c['floor']['normal'][2]for c in contacts),max(c['floor']['normal'][2]for c in contacts)],
                       'hull0_elevation_rise':b['floor_hull0']['end'][2]-a['floor_hull0']['end'][2],
                       'hull1_elevation_rise':b['floor']['end'][2]-a['floor']['end'][2],
                       'meets_physical_span':span>=256})
    return result


def _scenery_near(x, y, source):
    # Collision trunks are a valid physical obstruction but do not establish a
    # terrain barrier. Exclude their immediate footprint from foothill checks.
    for p in source.get('scenery', {}).get('placements', []):
        if p.get('kind') not in ('oak', 'birch', 'pine'):
            continue
        px, py, _ = p['origin']
        if math.hypot(x - px, y - py) < float(p.get('radius', 100)) + 64:
            return True
    return False


def _write_world(m, path):
    head, clips = m.hulls[1]
    with path.open('wb') as f:
        f.write(struct.pack('<8s8I', b'MSRTRACE', len(m.planes), len(clips), head & 0xffffffff,
                            (len(clips) - 1) & 0xffffffff, m.version, 0, 0, 0))
        for p in m.planes:
            f.write(struct.pack('<4f4B', *p[:4], p[4], 0, 0, 0))
        for c in clips:
            f.write(struct.pack('<iii', *c))


def compiled_connectivity(m, exe, folder, offset):
    """Bounded contact raster, using native floor normals and edge midpoints.

    This deliberately supplements rather than replaces exact surface topology
    and native play. A 400-unit raster can miss a narrow path, so it must not be
    represented as a proof of global navigation/exploit resistance.
    """
    xs=sorted(set([-11936,11936]+list(range(-11600,11601,400))))
    ys=sorted(set([-9984,10608]+list(range(-9600,10401,400))))
    points=[(x,y)for x in xs for y in ys]
    cases=[(_world((x,y,3800),offset),_world((x,y,64),offset))for x,y in points]
    traces=m.traces(exe,folder,1,cases)
    floor={xy:t for xy,t in zip(points,traces)if _floor_ok(t)and t['normal'][2]>=WALK_NORMAL}
    edges=[];midcases=[]
    gradient=math.sqrt(1/(WALK_NORMAL*WALK_NORMAL)-1)
    for ix,x in enumerate(xs):
        for iy,y in enumerate(ys):
            p=(x,y)
            if p not in floor:continue
            for q in ((xs[ix+1],y)if ix+1<len(xs)else None,(x,ys[iy+1])if iy+1<len(ys)else None):
                if q not in floor:continue
                if abs(floor[p]['end'][2]-floor[q]['end'][2])>gradient*math.dist(p,q)+.125:continue
                middle=((p[0]+q[0])/2,(p[1]+q[1])/2)
                edges.append((p,q));midcases.append((_world((*middle,3800),offset),_world((*middle,64),offset)))
    mid=m.traces(exe,folder,1,midcases)
    adjacent={p:[]for p in floor};accepted=0
    for (a,b),t in zip(edges,mid):
        if not _floor_ok(t)or t['normal'][2]<WALK_NORMAL:continue
        half=math.dist(a,b)/2
        if max(abs(floor[a]['end'][2]-t['end'][2]),abs(floor[b]['end'][2]-t['end'][2]))>gradient*half+.125:continue
        adjacent[a].append(b);adjacent[b].append(a);accepted+=1
    seeds={p for p in floor if abs(p[0])<8200 and -8000<p[1]<6800}
    visited=set(seeds);todo=deque(seeds)
    while todo:
        for q in adjacent[todo.popleft()]:
            if q not in visited:visited.add(q);todo.append(q)
    outer={p for p in floor if abs(p[0])>=11900 or (p[1]>=10550 and abs(p[0])>1950)}
    reachable=sorted(outer&visited)
    exits=[p for p in visited if p[1]>=10550 and abs(p[0])<=1950]
    return {'pass':not reachable,'floor_probes':len(cases),'edge_midpoint_probes':len(midcases),
            'walkable_sample_nodes':len(floor),'accepted_edges':accepted,'interior_seed_nodes':len(seeds),
            'reachable_nodes':len(visited),'walkable_outer_ridge_nodes':len(outer),
            'reachable_outer_ridge_nodes':len(reachable),'reachable_outer_ridge_examples':reachable[:20],
            'reachable_far_exit_nodes':len(exits),'raster_spacing_units':400,
            'scope':'Actual C hull1 floor-contact and edge-midpoint normal raster. Samples show whether coarse walkable ridge routes connect to the field; this does not prove the absence of narrow paths, jumping or gameplay exploits.'}


NATIVE_WRAPPER = r'''
static hull_t boundary_hull;
int Boundary_Init(const char *path) {
 FILE *in=fopen(path,"rb");char magic[8];uint32_t h[8];
 if(!in)return 0;
 if(fread(magic,1,8,in)!=8 || memcmp(magic,"MSRTRACE",8) || fread(h,4,8,in)!=8)return 0;
 mplane_t *p=calloc(h[0],sizeof(*p));mclipnode32_t *c32=calloc(h[1],sizeof(*c32));
 mclipnode16_t *c16=calloc(h[1],sizeof(*c16));
 if(!p || !c32 || !c16)return 0;
 if(fread(p,sizeof(*p),h[0],in)!=h[0] || fread(c32,sizeof(*c32),h[1],in)!=h[1])return 0;
 fclose(in);
 for(uint32_t i=0;i<h[1];i++){c16[i].planenum=c32[i].planenum;c16[i].children[0]=(int16_t)c32[i].children[0];c16[i].children[1]=(int16_t)c32[i].children[1];}
 world.version=h[4];boundary_hull.planes=p;boundary_hull.firstclipnode=(int)h[2];boundary_hull.lastclipnode=(int)h[3];
 if(world.version==QBSP2_VERSION)boundary_hull.clipnodes32=c32;else boundary_hull.clipnodes16=c16;
 return 1;
}
void Boundary_Trace(float *a,float *b,float *out) {
 pmtrace_t t={0};t.allsolid=true;t.fraction=1;VectorCopy(b,t.endpos);
 PM_RecursiveHullCheck(&boundary_hull,boundary_hull.firstclipnode,0,1,a,b,&t);
 out[0]=t.fraction;out[1]=(float)t.startsolid;out[2]=(float)t.allsolid;out[3]=(float)t.inwater;
 for(int i=0;i<3;i++){out[4+i]=t.endpos[i];out[7+i]=t.plane.normal[i];}
}
'''


def movement_replay(m, folder, selections):
    """Compile actual walk/slide functions against live, actual C map tracing."""
    folder = Path(folder)
    text = (REPO / 'Engine-Source/Xash3D/engine/common/pm_trace.c').read_text()
    point = qa.actual.function(text, 'int GAME_EXPORT PM_HullPointContents(')
    a = text.index('// Split the physical segment without an epsilon bias.')
    b = text.index('pmtrace_t PM_PlayerTraceExt(', a)
    prelude = (REPO / 'Development-Tests/Fixtures/trace_harness_prelude.c').read_text(encoding='utf-8-sig')
    cfile = folder / 'boundary-live-trace.c'
    cfile.write_text(prelude + '\n' + point + '\n' + text[a:b] + '\n' + NATIVE_WRAPPER)
    obj = folder / 'boundary-live-trace.obj'
    build = subprocess.run(['cl.exe', '/nologo', '/TC', '/std:c11', '/c', '/Od', '/Zi', '/RTC1',
                            '/UNDEBUG', '/fp:precise', str(cfile), '/Fo:' + str(obj)],
                           cwd=folder, text=True, capture_output=True)
    assert build.returncode == 0, build.stdout + build.stderr
    movement = qa.walk_replay.SOURCE.read_text()
    prefix = qa.walk_replay.PRELUDE
    prefix = prefix.replace('#include <cassert>', '#include <cassert>\n#include <algorithm>')
    prefix = prefix.replace('float accelerate=10,stepsize=18;', 'float accelerate=10,stepsize=18,bounce=1;')
    prefix = prefix.replace('int onground=0,waterlevel=0;', 'int onground=0,waterlevel=0,movetype=3,dead=0;float friction=1;')
    prefix = prefix.replace('int PM_FlyMove(){assert(flyIndex<fly.size());pmove->origin=fly[flyIndex++];return 0;}', 'int PM_FlyMove(void);')
    prefix = prefix.replace('void PM_Accelerate(Vector wish,float speed,float){VectorScale(wish,speed,pmove->velocity);}', 'void PM_Accelerate(Vector,float,float);')
    prefix += r'''
extern "C" int Boundary_Init(const char*);
extern "C" void Boundary_Trace(float*,float*,float*);
constexpr int MAX_CLIP_PLANES=5,MOVETYPE_WALK=3;
constexpr float STOP_EPSILON=.1f,DIST_EPSILON=1.f/32.f;
const Vector vec3_origin;
float DotProduct(const Vector&a,const Vector&b){return a[0]*b[0]+a[1]*b[1]+a[2]*b[2];}
Vector CrossProduct(const Vector&a,const Vector&b){return Vector(a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]);}
float V_min(float a,float b){return std::min(a,b);}
void PM_AddToTouched(pmtrace_t,Vector){}
int liveCalls=0,steepCalls=0;
pmtrace_t MapTrace(Vector a,Vector b,int,int){float r[10];Boundary_Trace(a.v,b.v,r);++liveCalls;if(r[0]<1&&r[9]<.7f)++steepCalls;return{r[0],r[1]!=0,r[2]!=0,Vector(r[4],r[5],r[6]),{Vector(r[7],r[8],r[9])}};}
'''
    functions = '\n'.join(qa.actual.function(movement, name) for name in
                          ('int PM_ClipVelocity(', 'int PM_FlyMove(void)', 'void PM_Accelerate(', 'void PM_WalkMove()'))
    def scalar(v):
        s = format(v, '.9g')
        return s + 'f' if '.' in s or 'e' in s else s + '.0f'
    def vector(p):
        return 'Vector(' + ','.join(scalar(v) for v in p) + ')'
    lines = ['int main(int argc,char**argv){assert(argc==2&&Boundary_Init(argv[1]));']
    settings = []
    for index, sample in enumerate(selections):
        for speed in (320, 520):
            for dt in (1/60, .02, .05):
                lines.append('{Reset();state.PM_PlayerTrace=MapTrace;state.origin=' + vector(sample['start']) +
                             ';state.forward=' + vector((*sample['direction'], 0)) +
                             ';state.cmd.forwardmove=' + scalar(speed) + ';state.maxspeed=' + scalar(speed) +
                             ';state.frametime=' + scalar(dt) + ';VectorScale(state.forward,' + scalar(speed) +
                             ',state.velocity);liveCalls=steepCalls=0;PM_WalkMove();' +
                             'auto t=MapTrace(state.origin,Vector(state.origin[0],state.origin[1],state.origin[2]-64),0,0);' +
                             'std::printf("%d %.9g %.9g %.9g %.9g %.9g %d %d\\n",' + str(len(settings)) +
                             ',state.origin[0],state.origin[1],state.origin[2],t.fraction,t.plane.normal[2],liveCalls,steepCalls);}')
                settings.append({'sample': index, 'speed': speed, 'dt': dt})
    lines.append('return 0;}')
    cpp = folder / 'boundary-live-walk.cpp'; binary = folder / 'boundary-live-walk.exe'
    cpp.write_text(prefix + '\n' + functions + '\n' + '\n'.join(lines))
    build = subprocess.run(['cl.exe', '/nologo', '/std:c++17', '/EHsc', '/Od', '/Zi', '/RTC1', '/UNDEBUG',
                            '/fp:precise', str(cpp), str(obj), '/Fe:' + str(binary)],
                           cwd=folder, text=True, capture_output=True)
    assert build.returncode == 0, build.stdout + build.stderr
    world = folder / 'boundary-live-world.bin'; _write_world(m, world)
    run = subprocess.run([str(binary), str(world)], cwd=folder, text=True, capture_output=True, timeout=30)
    assert run.returncode == 0, run.stdout + run.stderr
    results = []; failed = []
    for line in run.stdout.splitlines():
        cols = line.split(); index = int(cols[0]); setting = settings[index]; sample = selections[setting['sample']]
        end = list(map(float, cols[1:4])); displacement = math.hypot(end[0]-sample['start'][0], end[1]-sample['start'][1])
        record = dict(setting, zone=sample['zone'], kind=sample['kind'], local_xy=sample['local_xy'], start=sample['start'],
                      end=end, horizontal_distance=displacement, expected_unobstructed_distance=setting['speed']*setting['dt'],
                      end_ground_fraction=float(cols[4]), end_ground_normal_z=float(cols[5]),
                      actual_c_trace_calls=int(cols[6]), actual_steep_contacts=int(cols[7]))
        results.append(record)
        if sample['kind']=='lower-walkable' and (displacement < .85*setting['speed']*setting['dt'] or
                                                (record['end_ground_fraction']<1 and record['end_ground_normal_z']<WALK_NORMAL)):
            failed.append(record)
        if sample['kind']=='upper-steep' and (record['actual_steep_contacts']==0 or
                                             record['end_ground_fraction']==1 or
                                             record['end_ground_normal_z']>=WALK_NORMAL or
                                             displacement>.65*record['expected_unobstructed_distance']):
            failed.append(record)
    assert len(results)==len(settings), (len(results),len(settings))
    return {'pass': not failed, 'frames': len(results), 'actual_c_trace_calls': sum(r['actual_c_trace_calls']for r in results),
            'failures': failed[:20], 'results': results,
            'scope': 'Actual unchanged PM_WalkMove/PM_FlyMove/PM_ClipVelocity/PM_Accelerate linked to actual frozen C hull1, steady starting velocity, world collision only. Ground categorization, gravity, dynamic entities, multi-frame riding and player input require native gameplay acceptance.'}


def audit(m, exe, folder, offset, source):
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    if isinstance(source, (str, Path)):
        source = json.loads(Path(source).read_text())
    lines = _transects(); flat = []
    for line in lines:
        for (x,y), progress in zip(line['points'], line['progress']):
            flat.append({'line': line['name'], 'zone': line['zone'], 'local_xy': [x,y],
                         'progress': progress, 'direction': line['direction']})
    report = {'pass': True, 'map': m.summary(), 'plains_offset': list(offset), 'walkable_normal_z': WALK_NORMAL,
              'floor_samples_per_hull': len(flat), 'transects': [], 'failures': [],
              'scope': 'Focused compiled-world boundary audit; no runtime, assets, servers, source BSP or generator is modified.'}
    report['production_sources']={str(path.relative_to(REPO)).replace('\\','/'):
                                  hashlib.sha256(path.read_bytes()).hexdigest()for path in
                                  (REPO/'Engine-Source/Xash3D/engine/common/pm_trace.c',qa.walk_replay.SOURCE,Path(__file__))}
    floors = {}
    for hull in (0,1):
        cases = [(_world((s['local_xy'][0],s['local_xy'][1],3800), offset),
                  _world((s['local_xy'][0],s['local_xy'][1],64), offset)) for s in flat]
        floors[hull] = m.traces(exe,folder,hull,cases)
        for sample,t in zip(flat,floors[hull]):
            if not _floor_ok(t):report['failures'].append({'invalid_dry_boundary_floor':sample,'hull':hull,'trace':t})
    steps = []; step_meta = []; lower = []; selections = []
    for index, (sample, ground) in enumerate(zip(flat,floors[1])):
        if not _floor_ok(ground):continue
        p = ground['end']; x,y = sample['local_xy']
        if .18 <= sample['progress'] <= .52 and not _scenery_near(x,y,source):
            lower.append((index,sample,ground))
            if ground['normal'][2] < WALK_NORMAL:
                report['failures'].append({'unwalkable_lower_foothill': sample,'trace':ground})
            for direction in (sample['direction'],tuple(-v for v in sample['direction'])):
                steps.extend(_step_cases(p,direction)); step_meta.append((index,'lower',direction))
        if ground['normal'][2] < WALK_NORMAL and .65 <= sample['progress'] <= .95:
            steps.extend(_step_cases(p,sample['direction'])); step_meta.append((index,'upper',sample['direction']))
    step_results = m.traces(exe,folder,1,steps)
    lower_fail = []; barriers = {}; lower_pass = 0; native_starts = {}
    for i,(index,kind,direction) in enumerate(step_meta):
        ts = step_results[4*i:4*i+4]; sample = flat[index]; ground = floors[1][index]
        if kind=='lower':
            if _step_clear(ts): lower_pass += 1
            else: lower_fail.append({'sample':sample,'direction':direction,'traces':ts})
        else:
            # This is an actual blocked steep-floor step: the direct trace hits
            # terrain, and the raised route also hits or settles on an unwalkable
            # plane. A slope from the source height formula alone cannot pass.
            direct,up,across,down=ts
            real_steep=any(t['fraction']<1 and not t['startsolid'] and t['normal'][2]<WALK_NORMAL for t in (direct,across,down))
            point_ground=floors[0][index]
            both_floors_steep=_floor_ok(point_ground)and point_ground['normal'][2]<WALK_NORMAL and ground['normal'][2]<WALK_NORMAL
            if direct['fraction']<1 and real_steep and both_floors_steep and not _step_clear(ts):
                barriers.setdefault(sample['line'],[]).append({'sample_index':index,'sample':sample,'floor':ground,'floor_hull0':point_ground,'traces':ts})
    for line in lines:
        ids = [i for i,s in enumerate(flat) if s['line']==line['name']]
        valid0 = [floors[0][i]for i in ids if _floor_ok(floors[0][i])]
        valid1 = [floors[1][i]for i in ids if _floor_ok(floors[1][i])]
        blocked = barriers.get(line['name'],[])
        runs=_consecutive_barrier_runs(blocked)
        record={'name':line['name'],'zone':line['zone'],'samples':len(ids),'valid_hull0_floors':len(valid0),
                'valid_hull1_floors':len(valid1),'minimum_hull0_normal_z':min((t['normal'][2]for t in valid0),default=1),
                'minimum_hull1_normal_z':min((t['normal'][2]for t in valid1),default=1),
                'compiled_unwalkable_hull0_samples':sum(t['normal'][2]<WALK_NORMAL for t in valid0),
                'compiled_unwalkable_hull1_samples':sum(t['normal'][2]<WALK_NORMAL for t in valid1),
                'actual_blocked_18unit_steps':len(blocked),'consecutive_physical_barrier_runs':runs,
                'minimum_required_barrier_span_units':256,'maximum_allowed_sample_spacing_units':40,
                'barrier_examples':blocked[:2]}
        report['transects'].append(record)
        if not blocked: report['failures'].append({'missing_compiled_terrain_barrier':record})
        if not any(run['meets_physical_span']for run in runs):
            report['failures'].append({'insufficient_continuous_physical_terrain_barrier':record})
        candidates=[(i,s,t)for i,s,t in lower if s['line']==line['name'] and t['normal'][2]>=WALK_NORMAL]
        if candidates:
            i,s,t=candidates[len(candidates)//2]
            selections.append(dict(s,start=t['end'],kind='lower-walkable'))
        if blocked:
            b=blocked[len(blocked)//2]; selections.append(dict(b['sample'],start=b['floor']['end'],kind='upper-steep'))
            native_starts.setdefault(line['zone'],{'lower':selections[-2]if candidates else None,'steep':selections[-1]})
    report['lower_foothills']={'samples':len(lower),'steps':sum(k=='lower'for _,k,_ in step_meta),
                              'accepted_steps':lower_pass,'failed_steps':len(lower_fail),'failure_examples':lower_fail[:20]}
    report['failures'].extend({'blocked_lower_foothill':v}for v in lower_fail[:20])
    # Re-check the exact full-width entrance aperture in all four world hulls.
    aperture=[]
    for hull,halfheight in enumerate((0,36,32,18)):
        samples=[(x,y)for x in(1104+40,1280,1528,1800,2200,2432-40)for y in(3216,3220,3256,3336,3456,3696)]
        cases=[((x,y,3072+halfheight+128),(x,y,3072+halfheight-64))for x,y in samples]
        traces=m.traces(exe,folder,hull,cases); bad=[]
        for xy,t in zip(samples,traces):
            if not _floor_ok(t) or t['normal'][2]<.999 or abs(t['end'][2]-(3072+halfheight))>.125:
                bad.append({'world_xy':xy,'trace':t})
        aperture.append({'hull':hull,'floor_probes':len(cases),'pass':not bad,'failures':bad[:10]})
        report['failures'].extend({'entrance_aperture':v}for v in bad[:10])
    report['entry_aperture']=aperture
    report['movement']=movement_replay(m,folder,selections)
    if not report['movement']['pass']:report['failures'].append({'actual_pm_movement_failures':report['movement']['failures']})
    report['compiled_contact_connectivity']=compiled_connectivity(m,exe,folder,offset)
    if not report['compiled_contact_connectivity']['pass']:
        report['failures'].append({'coarse_compiled_ridge_route':report['compiled_contact_connectivity']})
    report['native_test_starts']=native_starts
    report['barrier_acceptance_scope']='Each transect requires a consecutive sampled band >=256 units (eight standing-hull widths), spacing <=40, with actual C hull0 AND hull1 steep floors and rejected actual18-unit steps. Fixed total counts or scattered contacts do not establish a band. Actual production movement, compiled-contact connectivity and native gameplay acceptance remain separate gates.'
    report['pass']=not report['failures']
    report['limitations']=['Transects and contact rasters demonstrate sampled steep barriers, not complete global navigation connectivity or resistance to jumping/exploits.',
                           'The source triangle connectivity test supplements the bounded compiled contact raster; narrow unsampled paths require native exploration.',
                           'Full native walking and horse riding still determine final gameplay acceptance.']
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bsp',type=Path,required=True);p.add_argument('--source',type=Path,required=True)
    p.add_argument('--offset',type=float,nargs=3,required=True);p.add_argument('--expected-sha256')
    p.add_argument('--report',type=Path,required=True);args=p.parse_args()
    m=qa.MapCollision(args.bsp)
    if args.expected_sha256:assert m.sha256==args.expected_sha256,(m.sha256,args.expected_sha256)
    with tempfile.TemporaryDirectory(prefix='msr-natural-boundary-')as td:
        folder=Path(td);exe=qa.actual.build(folder)
        report=audit(m,exe,folder,args.offset,args.source)
    args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'pass':report['pass'],'sha256':m.sha256,'crc32':m.summary()['crc32'],
                      'transects':len(report['transects']),'movement_frames':report['movement']['frames'],
                      'failures':len(report['failures']),'report':str(args.report)}))
    return 0 if report['pass']else 1


if __name__=='__main__':raise SystemExit(main())
