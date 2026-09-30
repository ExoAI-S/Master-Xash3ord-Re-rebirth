"""Compile actual x86 Debug engine C hull tracer and replay frozen map/fixtures.
Run from a Visual Studio x86 developer environment. Generated binaries are
confined to a temporary directory. BSP assets are supplied by --bsp.
"""
from pathlib import Path
import argparse,struct,subprocess,tempfile,json,math,hashlib,time,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'Design-Source/Daragoth-Plains'))
import compile_daragoth_plains as collision
RECORD=struct.Struct('<4if3f3ff3Qd')
QBSP2=int.from_bytes(b'BSP2','little')

def function(text,name):
    a=text.index(name);start=text.index('{',a);depth=1;i=start+1
    while depth:
        if text[i]=='{':depth+=1
        elif text[i]=='}':depth-=1
        i+=1
    return text[a:i]

def build(folder):
    text=(ROOT/'Engine-Source/Xash3D/engine/common/pm_trace.c').read_text()
    point=function(text,'int GAME_EXPORT PM_HullPointContents(')
    point=point.replace('{','{\n\tprofile_pointqueries++;',1)
    a=text.index('// Split the physical segment without an epsilon bias.');b=text.index('pmtrace_t PM_PlayerTraceExt(',a)
    actual=text[a:b]
    actual=actual.replace('while( num >= 0 )\n\t{','while( num >= 0 )\n\t{\n\t\tprofile_nodes++;',1)
    actual=actual.replace('int depth )\n{','int depth )\n{\n\tprofile_recursions++;',1)
    baseline=(ROOT/'Development-Tests/Fixtures/pm_trace_baseline.c').read_text()
    baseline=baseline.replace('PM_RecursiveHullCheck(','PM_RecursiveHullCheck_Baseline(').replace('loc0:','loc0:\n\tprofile_nodes++;')
    baseline=baseline.replace('pmtrace_t *trace )\n{','pmtrace_t *trace )\n{\n\tprofile_recursions++;',1)
    fixtures=ROOT/'Development-Tests/Fixtures'
    source=folder/'trace_harness.c';source.write_text((fixtures/'trace_harness_prelude.c').read_text(encoding='utf-8-sig')+'\n'+point+'\n'+baseline+'\n'+actual+'\n'+(fixtures/'trace_harness_main.c').read_text(encoding='utf-8-sig'))
    exe=folder/'trace_harness.exe'
    result=subprocess.run(['cl.exe','/nologo','/TC','/std:c11','/Od','/Zi','/RTC1','/UNDEBUG','/fp:precise',str(source),'/Fe:'+str(exe)],cwd=folder,text=True,capture_output=True)
    assert result.returncode==0,result.stdout+result.stderr
    return exe

def batch(exe,folder,planes,clips,head,cases,baseline=False,version=30,expect_error=False,null_hull=False,null_nodes=False,null_planes=False):
    filename=folder/'batch.bin';output=folder/'results.bin'
    with filename.open('wb') as f:
        f.write(struct.pack('<8s8I',b'MSRTRACE',len(planes),len(clips),head&0xffffffff,(len(clips)-1)&0xffffffff,version,int(baseline),len(cases),int(null_hull)|(int(null_nodes)<<1)|(int(null_planes)<<2)))
        for p in planes:f.write(struct.pack('<4f4B',*p[:4],p[4],0,0,0))
        for node in clips:f.write(struct.pack('<iii',*node))
        for a,b in cases:f.write(struct.pack('<6f',*a,*b))
    run=subprocess.run([str(exe),str(filename),str(output)],capture_output=True,text=True,timeout=30)
    if expect_error:
        assert run.returncode==9,(run.returncode,run.stderr)
        return {'controlled_error':run.stderr.strip()}
    assert run.returncode==0,(run.returncode,run.stdout,run.stderr)
    raw=output.read_bytes();assert len(raw)==len(cases)*RECORD.size
    result=[]
    for r in RECORD.iter_unpack(raw):
        result.append({'allsolid':bool(r[0]),'startsolid':bool(r[1]),'inopen':bool(r[2]),'inwater':bool(r[3]),'fraction':r[4],'end':list(r[5:8]),'normal':list(r[8:11]),'plane_dist':r[11],'node_visits':r[12],'recursive_calls':r[13],'point_queries':r[14],'seconds':r[15]})
    return result

def paths():
    routes=[]
    for x in (-7500,-5000,-1700,3000,6500,9000):
        routes.extend((f'north-x{x}',x,y,0,5.2) for y in range(-8500,-2500,2))
    for lane in (-192,0,192):
        routes.extend((f'road-lane{lane}',collision.source.road_x(y)+lane,y,0,5.2) for y in range(-9000,9001,2) if not 500<=y<=3100)
    for y in (-6500,-4500,4500,8000):
        routes.extend((f'east-y{y}',x,y,5.2,0) for x in range(-10500,10501,2))
    return routes

def point(planes,clips,head,p):
    return collision.contents(planes,clips,head,p)

def summarize(records):
    return {'traces':len(records),'total_seconds':sum(t['seconds'] for t in records),'mean_microseconds':sum(t['seconds'] for t in records)*1e6/max(1,len(records)),'mean_node_visits':sum(t['node_visits'] for t in records)/max(1,len(records)),'max_node_visits':max((t['node_visits'] for t in records),default=0),'mean_recursive_calls':sum(t['recursive_calls'] for t in records)/max(1,len(records)),'max_recursive_calls':max((t['recursive_calls'] for t in records),default=0),'mean_point_queries':sum(t['point_queries'] for t in records)/max(1,len(records))}

def box(mins,maxs):
    planes=[];clips=[]
    for i in range(6):
        axis=i//2;normal=[0.,0.,0.];normal[axis]=1.;planes.append((*normal,maxs[axis] if i%2==0 else mins[axis],axis))
        children=[i+1,i+1];children[0 if i%2==0 else 1]=-1
        if i==5:children[0]=-2
        clips.append((i,*children))
    return planes,clips

def main():
    pa=argparse.ArgumentParser(description=__doc__);pa.add_argument('--bsp',type=Path,required=True);pa.add_argument('--report',type=Path);args=pa.parse_args()
    data,lumps,planes,clips,model,entities,nodes,leaves=collision.load_collision(args.bsp);head=model[10]
    report={'production_source':'Engine-Source/Xash3D/engine/common/pm_trace.c','debug_compile':'MSVCx86 /TC /std:c11 /Od /Zi /RTC1 /UNDEBUG /fp:precise','bsp_sha256':hashlib.sha256(data).hexdigest(),'bsp_crc32':__import__('zlib').crc32(data)&0xffffffff,'sweep_samples':0,'synthetic_fixtures':[]}
    with tempfile.TemporaryDirectory(prefix='msr-c-hull-') as td:
        folder=Path(td);exe=build(folder);route=paths();floors=[]
        for _,x,y,_,_ in route:
            z=collision.source.height(x,y)+36;floors.append(((x,y,z+160),(x,y,z-160)))
        oldfloors=batch(exe,folder,planes,clips,head,floors,True);newfloors=batch(exe,folder,planes,clips,head,floors)
        report['floor_profile']={'baseline':summarize(oldfloors),'interval':summarize(newfloors)}
        cases=[];names=[]
        for route_item,t in zip(route,oldfloors):
            if t['fraction']==1 or t['startsolid'] or t['allsolid']:continue
            name,x,y,dx,dy=route_item;p=t['end'];cases.append((p,(p[0]+dx,p[1]+dy,p[2])));names.append(name)
        old=batch(exe,folder,planes,clips,head,cases,True);new=batch(exe,folder,planes,clips,head,cases)
        report['sweep_samples']=len(route);report['valid_horizontal_sweeps']=len(cases);report['horizontal_profile']={'baseline':summarize(old),'interval':summarize(new)}
        failures={'baseline':[],'interval':[]}
        for name,case,old_trace,new_trace in zip(names,cases,old,new):
            for label,t in [('baseline',old_trace),('interval',new_trace)]:
                if t['fraction']<1 and t['normal'][2]<-.7:
                    a,b=case
                    if all(point(planes,clips,head,tuple(a[i]+(b[i]-a[i])*k/32 for i in range(3)))==-1 for k in range(33)):
                        failures[label].append({'route':name,'start':a,'end':b,'trace':t})
        report['false_ceiling_counts']={k:len(v) for k,v in failures.items()};report['false_ceiling_examples']=failures
        assert failures['baseline'],'Baseline did not reproduce terrain false-ceiling regression'
        assert not failures['interval'],'Replacement still has false-ceiling regressions'
        scenes=[('exact_bad_horizontal',(-1700,-6281.5,388.1609191894531),(-1700,-6276.3,388.1609191894531)),('exact_bad_upward',(-1700,-6281.5,388.1609191894531),(-1700,-6281.5,406.1609191894531)),('solid_outer_wall',(11980,0,700),(12020,0,700)),('stable_real_ceiling',(-1700,-7900,731.96875),(-1700,-7900,740)),('stable_step_wall',(-1700,-8260,452.03125),(-1700,-8180,452.03125)),('stable_step_raise',(-1700,-8260,452.03125),(-1700,-8260,470.03125)),('stable_step_move',(-1700,-8260,470.03125),(-1700,-8180,470.03125)),('stable_step_down',(-1700,-8180,470.03125),(-1700,-8180,452.03125)),('stable_drop',(-1700,-7560,468.03125),(-1700,-7500,468.03125)),('thin_fence',(-1700,-8460,520),(-1700,-8340,520)),('thin_roof',(-1700,-7900,700),(-1700,-7900,860)),('zero_clear',(-1700,-7900,500),(-1700,-7900,500)),('zero_solid',(-1700,-7900,440),(-1700,-7900,440)),('startsolid_exit',(-1700,-7900,440),(-1700,-7900,500)),('allsolid',(-1700,-7900,440),(-1700,-7900,420)),('startsolid_exact_exit',(-1700,-7900,440),(-1700,-7900,468))]
        s_old=batch(exe,folder,planes,clips,head,[(a,b) for _,a,b in scenes],True);s_new=batch(exe,folder,planes,clips,head,[(a,b) for _,a,b in scenes]);report['world_scene_regressions']=[]
        for (name,a,b),o,n in zip(scenes,s_old,s_new):
            if name.startswith('exact_bad'):assert n['fraction']==1 and o['fraction']<1,name
            elif name in ('startsolid_exit','startsolid_exact_exit'):
                assert n['startsolid'] and not n['allsolid'] and n['inopen'],name
                assert n['fraction']==o['fraction'] and n['end']==o['end'],name
            else:
                assert all(o[k]==n[k] for k in ('allsolid','startsolid','inopen','inwater')),(name,o,n)
                assert abs(o['fraction']-n['fraction'])<.001,name
                assert all(abs(o['end'][i]-n['end'][i])<.005 for i in range(3)),name
            report['world_scene_regressions'].append({'name':name,'pass':True,'baseline':o,'interval':n})
        for version in (30,QBSP2):
            bp,bc=box((-.005,-100,-100),(.005,100,100));cs=[((-1,0,0),(1,0,0)),((1,0,0),(-1,0,0)),((-.005,0,0),(1,0,0)),((0,0,0),(1,0,0)),((0,0,0),(0,0,0)),((-.005,0,0),(-1,0,0)),((-1,100,0),(1,100,0))]
            bo=batch(exe,folder,bp,bc,0,cs,True,version);bn=batch(exe,folder,bp,bc,0,cs,False,version)
            for i,(o,n)in enumerate(zip(bo,bn)):
                assert all(o[k]==n[k] for k in ('allsolid','startsolid','inopen','inwater')),('thin',version,i)
                if i<2:
                    assert n['fraction']<1 and not n['startsolid'],('thin-first-entry',version,i)
                else:assert abs(o['fraction']-n['fraction'])<.001,('thin',version,i,o,n)
            assert bn[0]['fraction']<1 and bn[1]['fraction']<1,'Thin wall crossed'
            report['synthetic_fixtures'].append({'name':'0.01unit-thin-wall-boundaries-startsolid','clipnode_bits':32 if version==QBSP2 else 16,'pass':True,'comparisons':[{'baseline':o,'interval':n}for o,n in zip(bo,bn)]})
            wp=[(1.,0.,0.,0.,0),(1.,0.,0.,-1.,0),(1.,0.,0.,-2.,0)];wc=[(0,-3,1),(1,-1,2),(2,-2,-1)];cs=[((1,0,0),(-1.5,0,0)),((1,0,0),(2,0,0)),((-1.5,0,0),(1,0,0)),((-1.5,0,0),(-1.8,0,0))]
            wo=batch(exe,folder,wp,wc,0,cs,True,version);wn=batch(exe,folder,wp,wc,0,cs,False,version)
            for i,(o,n)in enumerate(zip(wo,wn)):
                assert all(o[k]==n[k] for k in ('allsolid','startsolid','inopen','inwater')),('water',version,i)
                assert abs(o['fraction']-n['fraction'])<.001,('water',version,i)
                assert all(abs(o['end'][j]-n['end'][j])<.005 for j in range(3)),('waterend',version,i)
            report['synthetic_fixtures'].append({'name':'water-open-solid-prefix-and-startsolid-exit','clipnode_bits':32 if version==QBSP2 else 16,'pass':True})
            invalid=batch(exe,folder,bp,bc,0,[((float('nan'),0,0),(1,0,0)),((0,0,0),(float('inf'),0,0))],False,version)
            assert all(t['allsolid']and t['startsolid']and t['fraction']==0 for t in invalid)
            report['synthetic_fixtures'].append({'name':'nonfinite-input-bounded-rejection','clipnode_bits':32 if version==QBSP2 else 16,'pass':True})
        for version in (30,QBSP2):
            for leaf in (-1,-2,-3):
                leafcase=[((0,0,0),(1,2,3))]
                lo=batch(exe,folder,[],[],leaf,leafcase,True,version,null_hull=True)[0]
                ln=batch(exe,folder,[],[],leaf,leafcase,False,version,null_hull=True)[0]
                assert all(lo[k]==ln[k] for k in ('allsolid','startsolid','inopen','inwater','fraction','end'))
                report['synthetic_fixtures'].append({'name':'negative-root-leaf-null-hull','contents':leaf,'clipnode_bits':32 if version==QBSP2 else 16,'pass':True,'baseline':lo,'interval':ln})
            ep=[(1.,0.,0.,0.,0)];ec=[(0,-1,-2)];cs=[((-1,0,0),(1,0,0))]
            eo=batch(exe,folder,ep,ec,0,cs,True,version)[0];en=batch(exe,folder,ep,ec,0,cs,False,version)[0]
            assert all(eo[k]==en[k] for k in ('allsolid','startsolid','inopen','inwater','fraction','end'))
            report['synthetic_fixtures'].append({'name':'empty-hull-single-node-native-contract','clipnode_bits':32 if version==QBSP2 else 16,'pass':True})
            no=batch(exe,folder,[],[],0,cs,True,version)[0];nn=batch(exe,folder,[],[],0,cs,False,version)[0]
            assert all(no[k]==nn[k] for k in ('allsolid','startsolid','inopen','inwater','fraction','end'))
            report['synthetic_fixtures'].append({'name':'empty-hull-null-planes-and-nodes-native-contract','clipnode_bits':32 if version==QBSP2 else 16,'pass':True})
            for kind in ('nodes','planes'):
                invalid=batch(exe,folder,bp,bc,0,[((-1,0,0),(1,0,0))],False,version,null_nodes=kind=='nodes',null_planes=kind=='planes')[0]
                assert invalid['allsolid'] and invalid['startsolid'] and invalid['fraction']==0
                report['synthetic_fixtures'].append({'name':'nonempty-null-'+kind+'-bounded-rejection','clipnode_bits':32 if version==QBSP2 else 16,'pass':True})
            rp=[(1.,0.,0.,-1.,0),(1.,0.,0.,-2.,0),(1.,0.,0.,-3.,0),(1.,0.,0.,-4.,0)];rc=[(0,-1,1),(1,-2,2),(2,-1,3),(3,-2,-1)]
            ro=batch(exe,folder,rp,rc,0,[((-1.5,0,0),(-3.5,0,0))],True,version)[0];rn=batch(exe,folder,rp,rc,0,[((-1.5,0,0),(-3.5,0,0))],False,version)[0]
            assert rn['startsolid'] and not rn['allsolid'] and rn['inopen'] and rn['fraction']<1
            assert all(ro[k]==rn[k] for k in ('allsolid','startsolid','inopen','inwater'))
            assert abs(ro['fraction']-rn['fraction'])<.001 and all(abs(ro['end'][i]-rn['end'][i])<.005 for i in range(3))
            report['synthetic_fixtures'].append({'name':'startsolid-exit-then-reenter','clipnode_bits':32 if version==QBSP2 else 16,'pass':True,'baseline':ro,'interval':rn})
        report['caller_contracts']={'player':'PM_PlayerTraceExt clamps fraction to 0 whenever startsolid is true, so the player stays blocked.','walking_npc':'SV_movestep retries/rejects startsolid traces independently of allsolid.','server_fly_toss':'SV_FlyMove/PhysicsToss may now allow non-player entities to leave initial solid volume when the actual segment reaches clear space; old biased traversal could falsely mark entire segment allsolid.','flag_correction':'Stable z440 to 500 and z440 to 468 preserve startsolid/fraction/endpos but correctly set allsolid False and inopen True after finding clear tail.'}
        cycle=batch(exe,folder,[(1.,0.,0.,0.,0)]*2,[(0,0,0),(0,-1,-2)],0,[((1,0,0),(2,0,0))],expect_error=True)
        report['synthetic_fixtures'].append({'name':'cyclic-clipnode-controlled-error','pass':True,**cycle})
    report['pass']=True
    if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('false_ceiling_examples','world_scene_regressions','synthetic_fixtures')},indent=2));print('Actual C world/synthetic regressions PASS')

if __name__=='__main__':main()
