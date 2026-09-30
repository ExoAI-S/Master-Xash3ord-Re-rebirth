"""Read-only actual C collision/render/placement audit of a frozen meadow BSP."""
from __future__ import annotations
import argparse,hashlib,importlib.util,json,math,runpy,struct,sys,tempfile
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'Development-Tests'))
sys.path.insert(0,str(REPO/'Packaging-Work/BigWorld/tools'))
import test_daragoth_expanded_collision as qa
import test_daragoth_cap_visibility as visual
import test_daragoth_natural_boundary as boundary


def scope_and_height():
    scope=runpy.run_path(str(REPO/'Design-Source/Daragoth-Plains/build_daragoth_plains.py'))
    sys.path.insert(0,str(REPO/'Design-Source/Daragoth-Meadow'))
    spec=importlib.util.spec_from_file_location('meadow_audit_source',REPO/'Design-Source/Daragoth-Meadow/build_meadow.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return scope,lambda x,y:module.meadow_height(scope,x,y)


def model_node_budgets(m):
    memo={};active=set()
    def count(n):
        if n<0:return 0
        if n in memo:return memo[n]
        if n in active:raise ValueError('Cyclic per-model collision hull')
        active.add(n);_,a,b=m.clips[n]
        result=1+count(a)+count(b);active.remove(n);memo[n]=result;return result
    permodel=[]
    for i,model in enumerate(m.models):
        counts=[count(model[9+h])for h in (1,2,3)]
        permodel.append({'model':i,'hull_node_counts':counts})
    largest=max(v for model in permodel for v in model['hull_node_counts'])
    return {'pass':largest<=32767,'disk_clipnodes':len(m.clips),'models':len(m.models),'largest_native_16bit_hull':largest,'per_model':permodel}


def outdoor(x,y,scope):
    sx,sy=scope['STABLE'];rx,ry=scope['RUINS']
    if abs(x-sx)<1000 and abs(y-sy)<750:return False
    if abs(x-rx)<1100 and abs(y-ry)<1100:return False
    if math.hypot(x+4600,y-5000)<450:return False
    if any(abs(x+3500)<500 and abs(y-cy)<500 for cy in(-7700,-6800)):return False
    if abs(x)<650 and 600<y<3000:return False
    return True


def field_sweeps(m,exe,folder,offset,scope,height):
    locations=[]
    for x in(-7500,-5000,-1700,3000,6500,9000):
        for y in range(-9000,9501,16):
            if outdoor(x,y,scope):locations.append((x,y,'north-field'))
    for x in range(-10500,10501,400):
        for y in range(-9000,9001,400):
            if outdoor(x,y,scope):locations.append((x,y,'field-grid'))
    floors=[]
    for x,y,_ in locations:
        z=height(x,y)+36+offset[2]
        floors.append(((x+offset[0],y+offset[1],z+160),(x+offset[0],y+offset[1],z-160)))
    ground=m.traces(exe,folder,1,floors)
    cases=[];labels=[];excluded=[];uphill=[]
    for location,t in zip(locations,ground):
        x,y,name=location
        if t['startsolid']or t['allsolid']or t['fraction']==1 or t['normal'][2]<.7:
            if len(excluded)<20:excluded.append({'local_xy':[x,y],'trace':t})
            continue
        p=t['end']
        for dx,dy in((0,5.3333333),(0,8.6666667),(0,-8.6666667),(8.6666667,0),(-8.6666667,0)):
            cases.append((p,(p[0]+dx,p[1]+dy,p[2])));labels.append((name,x,y,'horizontal'))
        cases.append((p,(p[0],p[1],p[2]+18)));labels.append((name,x,y,'up18'))
    traces=m.traces(exe,folder,1,cases)
    false=[];ceiling_hits=0;clear=0;actual_hits=0;blocked_up=[]
    for label,case,t in zip(labels,cases,traces):
        if t['fraction']==1 and not t['startsolid']:clear+=1;continue
        actual_hits+=1
        if t['normal'][2]<-.7:
            ceiling_hits+=1
            if qa.point_clear_segment(m,1,*case):
                false.append({'label':label,'case':case,'trace':t})
        if label[3]=='up18' and len(blocked_up)<20:blocked_up.append({'label':label,'case':case,'trace':t})
        if label[3]=='horizontal'and t['normal'][2]>=.7 and not t['startsolid']:
            uphill.append((label,case,t))
    # For real uphill contacts, prove the actual C 18-unit raised path remains
    # clear and settles onto a genuine walkable floor (or a clear drop).
    raised=[]
    for _,(a,b),_ in uphill:
        up=(a[0],a[1],a[2]+18);end=(b[0],b[1],b[2]+18)
        raised.extend([(a,up),(up,end),(end,b)])
    steps=m.traces(exe,folder,1,raised);step_fail=[];valid_steps=0
    for i,(label,case,t)in enumerate(uphill):
        up,across,down=steps[3*i:3*i+3]
        passed=up['fraction']==1 and across['fraction']==1 and not any(v['startsolid']or v['allsolid']for v in(up,across,down))and(down['fraction']==1 or down['normal'][2]>=.7)
        if passed:valid_steps+=1
        elif len(step_fail)<20:step_fail.append({'label':label,'case':case,'traces':[up,across,down]})
    return {'pass':not false,'floor_probes':len(floors),'valid_floors':len(cases)//6,'movement_and_up_probes':len(cases),'clear':clear,'physical_hits':actual_hits,'ceiling_hits':ceiling_hits,'false_ceiling_count':len(false),'false_ceiling_examples':false[:20],'excluded_ground_examples':excluded,'up18_obstruction_examples':blocked_up,'real_uphill_contacts':len(uphill),'raised_step_probes':len(raised),'valid_raised_steps':valid_steps,'step_obstruction_examples':step_fail,'scope':'Actual frozen C world hull1. Real terrain uphill/CLIP-tree hits are retained; only an empty-segment false ceiling fails this diagnostic. Dynamic entities are tested natively.'}


def grass_roots(model):
    d=model.read_bytes();nb,bo=struct.unpack_from('<ii',d,140)
    assert nb==1 and struct.unpack_from('<6f',d,bo+64)==(0,0,0,0,0,0),'Grass neutral bone transform changed'
    bp,bpo=struct.unpack_from('<ii',d,204);points=set()
    for i in range(bp):
        _,nmods,_,mo=struct.unpack_from('<64s3i',d,bpo+76*i)
        for j in range(nmods):
            mdl=struct.unpack_from('<64sif10i',d,mo+112*j);nv,vo=mdl[5],mdl[7]
            for k in range(nv):
                p=struct.unpack_from('<3f',d,vo+12*k)
                if abs(p[2])<.0001:points.add(p)
    return sorted(points)


def placement_checks(m,exe,folder,offset,scope,source,grassmdl):
    placements=source['scenery']['placements'];failed=[];clearances=[];floorcases=[]
    for p in placements:
        x,y,z=p['origin'];r=p['radius'];kind=p['kind']
        required=1050 if kind in('oak','birch','pine')else scope['road_width'](y)+120+r
        road=abs(x-scope['road_x'](y))
        stable=(1100 if kind in('oak','birch','pine')else 780)+r
        if road<required-.1 or abs(y-scope['RIVER_Y'])<550+r-.1 or max(abs(x-scope['STABLE'][0]),abs(y-scope['STABLE'][1]))<stable-.1:
            failed.append({'clearance':p})
        clearances.append(road-required)
        gz=p['terrain_ground_z']+offset[2]
        floorcases.append(((x+offset[0],y+offset[1],gz+96),(x+offset[0],y+offset[1],gz-96)))
    floors=m.traces(exe,folder,0,floorcases)
    residuals=[]
    for p,t in zip(placements,floors):
        expected=p['terrain_ground_z']+offset[2]
        residual=t['end'][2]-expected;residuals.append(residual)
        if t['fraction']==1 or t['startsolid']or t['allsolid']or abs(residual)>.25:failed.append({'prop_ground':p,'trace':t,'ground_error':residual})
    roots=grass_roots(grassmdl);rootcases=[];rootinfo=[]
    for p in placements:
        if p['kind']!='grass':continue
        # MSR enables only large coordinates, so engine StudioSetUpTransform
        # negates entity pitch before Matrix3x4_CreateFromEntity. Roll stays.
        pitch=math.radians(-p['pitch']);roll=math.radians(p['roll']);cp=math.cos(pitch);sp=math.sin(pitch);cr=math.cos(roll);sr=math.sin(roll)
        for x,y,z in roots:
            world=(p['origin'][0]+cp*x+sr*sp*y+offset[0],p['origin'][1]+cr*y+offset[1],p['origin'][2]-sp*x+sr*cp*y+offset[2])
            rootcases.append(((world[0],world[1],world[2]+32),(world[0],world[1],world[2]-32)));rootinfo.append((p['origin'],world))
    contacts=m.traces(exe,folder,0,rootcases);errors=[];root_fail=[]
    for info,t in zip(rootinfo,contacts):
        residual=info[1][2]-t['end'][2];errors.append(residual)
        if t['fraction']==1 or t['startsolid']or t['allsolid']or residual>6.3 or residual<-10.3:
            if len(root_fail)<20:root_fail.append({'patch_origin':info[0],'world_root':info[1],'height_above_surface':residual,'trace':t})
    return {'pass':not failed and not root_fail,'props':len(placements),'counts':source['scenery']['counts'],'minimum_road_clearance_above_required':min(clearances),'center_ground_errors':[min(residuals),max(residuals)],'grass_model_sha256':hashlib.sha256(grassmdl.read_bytes()).hexdigest(),'unique_grass_base_vertices':len(roots),'transformed_grass_root_probes':len(rootcases),'grass_root_height_above_ground_range':[min(errors),max(errors)],'grass_root_max_plane_deviation_plus_embed':[-10.3,6.3],'failure_examples':failed[:20],'grass_failure_examples':root_fail,'renderer_pitch_contract':'MSR SV_CheckFeatures enables only large coordinates; stock studio renderer negates entity pitch, preserving the intended terrain plane.'}


def landmark_checks(m,exe,folder,offset,scope,height):
    cases=[];labels=[]
    for lane in(-128,0,128):
        for y in range(-9850,9901,25):
            x=scope['road_x'](y)+lane;z=height(x,y)+36+offset[2]
            cases.append(((x+offset[0],y+offset[1],z+500),(x+offset[0],y+offset[1],z-256)));labels.append(('road',lane,x,y))
    for x in(-256,0,256):
        for y in range(700,2901,10):
            cases.append(((x+offset[0],y+offset[1],offset[2]+800),(x+offset[0],y+offset[1],offset[2]+380)));labels.append(('bridge',0,x,y))
    sx,sy=scope['STABLE']
    for y in range(sy-64,sy+650,8):
        cases.append(((sx+offset[0],y+offset[1],offset[2]+650),(sx+offset[0],y+offset[1],offset[2]+400)));labels.append(('stable-exit',0,sx,y))
    ground=m.traces(exe,folder,1,cases);failure=[];steps=[];steplabels=[]
    for label,t in zip(labels,ground):
        if t['fraction']==1 or t['startsolid']or t['allsolid']or t['normal'][2]<.7:
            if len(failure)<20:failure.append({'label':label,'floor':t})
            continue
        p=t['end'];up=(p[0],p[1],p[2]+18)
        for dy in(-8.6666667,8.6666667):
            end=(p[0],p[1]+dy,p[2]+18)
            steps.extend([(p,up),(up,end),(end,(end[0],end[1],p[2]))]);steplabels.append(label+(dy,))
    contacts=m.traces(exe,folder,1,steps)
    for i,label in enumerate(steplabels):
        up,across,down=contacts[3*i:3*i+3]
        if up['fraction']!=1 or across['fraction']!=1 or any(t['startsolid']or t['allsolid']for t in(up,across,down))or(down['fraction']<1 and down['normal'][2]<.7):
            if len(failure)<20:failure.append({'label':label,'step_traces':[up,across,down]})
    return {'pass':not failure,'floor_checks':len(cases),'two_direction_step_paths':len(steplabels),'actual_C_step_traces':len(steps),'failure_examples':failure}


def village_checks(m,exe,folder,offset,village):
    cases=[];labels=[];routes=[]
    for building in village['buildings']:
        cx,cy=building['center'];hx,hy=building['half_size']
        front=cx+hx if building['door_facing']=='east'else cx-hx
        for lateral in(-64,0,64):
            for x in range(int(front)-128,int(front)+129,8):
                z=building['floor_z']+36+offset[2]
                cases.append(((x+offset[0],cy+lateral+offset[1],z+60),(x+offset[0],cy+lateral+offset[1],z-80)))
                labels.append(('door',building['role'],cx,cy,lateral,x))
        z=building['floor_z']+36+offset[2]
        cases.append(((cx+offset[0],cy+offset[1],z+60),(cx+offset[0],cy+offset[1],z-80)))
        labels.append(('interior',building['role'],cx,cy))
    for actor in village['residents']:
        points=actor['route']
        for i,a in enumerate(points):
            b=points[(i+1)%len(points)]
            length=math.hypot(b[0]-a[0],b[1]-a[1]);n=math.ceil(length/8)
            for j in range(n+1):
                f=j/n;x=a[0]+(b[0]-a[0])*f;y=a[1]+(b[1]-a[1])*f
                z=a[2]+36+offset[2]
                cases.append(((x+offset[0],y+offset[1],z+60),(x+offset[0],y+offset[1],z-80)))
                labels.append(('walker',actor['role'],i,j,x,y))
                if j<n:routes.append((len(cases)-1,(b[0]-a[0])/n,(b[1]-a[1])/n))
    ground=m.traces(exe,folder,1,cases);failed=[];stepcases=[];steplabels=[];heads=[]
    for label,t in zip(labels,ground):
        if t['fraction']==1 or t['startsolid']or t['allsolid']or t['normal'][2]<.7:
            if len(failed)<30:failed.append({'label':label,'floor':t})
            continue
        p=t['end'];heads.append((p,(p[0],p[1],p[2]+32)))
        if label[0]=='door':
            for dx in(-8,8):
                up=(p[0],p[1],p[2]+18);end=(p[0]+dx,p[1],p[2]+18)
                stepcases.extend([(p,up),(up,end),(end,(end[0],end[1],p[2]))]);steplabels.append(label+(dx,))
    for idx,dx,dy in routes:
        t=ground[idx]
        if t['fraction']==1 or t['startsolid']or t['allsolid']:continue
        p=t['end'];up=(p[0],p[1],p[2]+18);end=(p[0]+dx,p[1]+dy,p[2]+18)
        stepcases.extend([(p,up),(up,end),(end,(end[0],end[1],p[2]))]);steplabels.append(labels[idx])
    headresults=m.traces(exe,folder,1,heads)
    for case,t in zip(heads,headresults):
        if t['fraction']!=1 or t['startsolid']or t['allsolid']:
            if len(failed)<30:failed.append({'headroom':case,'trace':t})
    steps=m.traces(exe,folder,1,stepcases)
    for i,label in enumerate(steplabels):
        up,across,down=steps[3*i:3*i+3]
        if up['fraction']!=1 or across['fraction']!=1 or any(t['startsolid']or t['allsolid']for t in(up,across,down))or(down['fraction']<1 and down['normal'][2]<.7):
            if len(failed)<30:failed.append({'label':label,'step':[up,across,down]})
    return {'pass':not failed,'name':village['name'],'enterable_buildings':len(village['buildings']),'residents':len(village['residents']),'floor_probes':len(cases),'headroom_probes':len(heads),'actual_C_step_traces':len(stepcases),'route_segments':sum(len(a['route'])for a in village['residents']),'failure_examples':failed,'scope':'Standing hull1 doors in both directions, interiors, all closed resident route segments at <=8-unit spacing, and additional 32-unit headroom. Actual NPC script behavior is covered by native testing.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bsp',type=Path,required=True);parser.add_argument('--expected-sha',required=True);parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--previous-bsp',type=Path,required=True)
    parser.add_argument('--original',type=Path,required=True)
    parser.add_argument('--source-report',type=Path,required=True)
    parser.add_argument('--merge-report',type=Path,required=True)
    parser.add_argument('--grass-model',type=Path,required=True)
    args=parser.parse_args();sys.setrecursionlimit(20000)
    m=qa.MapCollision(args.bsp);assert m.sha256==args.expected_sha,'Candidate changed since freeze'
    prior=visual.BSP.load(args.previous_bsp)
    source=json.loads(args.source_report.read_text())
    merge=json.loads(args.merge_report.read_text());offset=merge['plains_offset']
    scope,height=scope_and_height()
    report={'map':m.summary(),'engine_source_sha256':hashlib.sha256((REPO/'Engine-Source/Xash3D/engine/common/pm_trace.c').read_bytes()).hexdigest(),'node_budgets':model_node_budgets(m),'render':visual.render_audit(visual.BSP.load(args.bsp),prior,True)}
    original=qa.MapCollision(args.original)
    with tempfile.TemporaryDirectory(prefix='msr-meadow-qa-')as td:
        folder=Path(td);exe=qa.actual.build(folder)
        print('Actual C harness built; checking original map',flush=True)
        old,cases=qa.audit_original(original,exe,folder,3216);report['original']=old
        print('Checking original preservation and all four seam hulls',flush=True)
        report['original_preservation_and_seam']=qa.audit_candidate(original,m,exe,folder,3216,(0,0,0),cases)
        print('Checking meadow field contacts',flush=True)
        report['field']=field_sweeps(m,exe,folder,offset,scope,height)
        print('Checking model placement and actual compiled grass roots',flush=True)
        report['placements']=placement_checks(m,exe,folder,offset,scope,source,args.grass_model)
        print('Checking road, stable and bridge',flush=True)
        report['landmarks']=landmark_checks(m,exe,folder,offset,scope,height)
        print('Checking village doors and resident routes',flush=True)
        report['village']=village_checks(m,exe,folder,offset,source['scenery']['village'])
        print('Checking compiled natural boundary foothills and steep barriers',flush=True)
        report['natural_boundaries']=boundary.audit(m,exe,folder,offset,source)
    sections=('node_budgets','render','original_preservation_and_seam','field','placements','landmarks','village','natural_boundaries')
    report['pass']=all(report[k]['pass']for k in sections)
    report['scope']='Read-only frozen private meadow map; actual x86 Debug C hull probes, full original preservation and seam replay, render topology/PVS, emitted scenery and compiled MDL roots. Renderer frame rate, dynamic entity interaction and FN state require native tests.'
    assert m.sha256==hashlib.sha256(args.bsp.read_bytes()).hexdigest(),'Candidate changed during QA'
    args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'pass':report['pass'],'map':m.summary(),'section_verdicts':{k:report[k]['pass']for k in sections},'report':str(args.report)},indent=2))
    if not report['pass']:raise SystemExit(1)


if __name__=='__main__':main()
