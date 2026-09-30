"""Actual C audit of original Daragoth and a continuous expanded candidate.

Run in the Visual Studio x86 developer environment used by the engine tests.
No game, source BSP, or generated candidate is modified. Collision hulls are
remapped in preorder like the BSP30ext engine loader before the actual C tracer
is invoked. --offset translates the original section into the candidate.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import re
import struct
import subprocess
import sys
import tempfile
import zlib

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'Development-Tests'))
import test_engine_hull_trace as actual
import test_step_path_replay as walk_replay

class MapCollision:
    def __init__(self,path:Path):
        self.path=path
        self.data=path.read_bytes()
        self.version=struct.unpack_from('<I',self.data)[0]
        if self.version not in (30,actual.QBSP2):
            raise ValueError(f'Unsupported BSP version {self.version}')
        self.lumps=[struct.unpack_from('<ii',self.data,4+8*i) for i in range(15)]
        self.extended=self.data[124:128]==b'XASH'
        def lump(index):
            at,size=self.lumps[index]
            return self.data[at:at+size]
        self.planes=list(struct.iter_unpack('<4fi',lump(1)))
        if self.version==actual.QBSP2:
            self.nodes=list(struct.iter_unpack('<iii6fii',lump(5)))
            leafstride=44
        else:
            self.nodes=list(struct.iter_unpack('<i2h6h2H',lump(5)))
            leafstride=28
        raw=lump(10)
        self.leaves=[struct.unpack_from('<i',raw,i)[0] for i in range(0,len(raw),leafstride)]
        raw=lump(9)
        self.disk_clip_bits=32 if self.version==actual.QBSP2 or (self.extended and (len(raw)%8 or len(raw)//12>=32767)) else 16
        self.clips=list(struct.iter_unpack('<iii' if self.disk_clip_bits==32 else '<ihh',raw))
        self.models=list(struct.iter_unpack('<9f4i3i',lump(14)))
        self.world=self.models[0]
        self.entities=[dict(re.findall(r'"([^"]*)"\s+"([^"]*)"',block)) for block in re.findall(r'\{([^{}]*)\}',lump(0).decode('latin1'))]
        self.hulls=[]
        self.hull_metadata=[]
        renderclips=[]
        for node in self.nodes:
            children=[v if v>=0 else self.leaves[-1-v] for v in node[1:3]]
            renderclips.append((node[0],*children))
        for hull_index in range(4):
            source=renderclips if hull_index==0 else self.clips
            head=self.world[9+hull_index]
            remapped=[]
            active=set()
            def copy(node):
                if node<0:return node
                if node>=len(source):raise ValueError(f'Hull {hull_index} child index {node} out of range')
                if node in active:raise ValueError(f'Hull {hull_index} is cyclic')
                active.add(node)
                index=len(remapped)
                remapped.append(None)
                plane,front,back=source[node]
                remapped[index]=(plane,copy(front),copy(back))
                active.remove(node)
                return index
            remapped_head=copy(head)
            if self.version==30 and len(remapped)>32767:
                raise ValueError(f'Hull {hull_index} exceeds native 16-bit per-model limit: {len(remapped)}')
            self.hulls.append((remapped_head,remapped))
            meta={'hull':hull_index,'source_head':head,'remapped_nodes':len(remapped),'runtime_clip_bits':32 if self.version==actual.QBSP2 else 16}
            if hull_index==0 and head>=0:
                reachable=set()
                todo=[head]
                while todo:
                    n=todo.pop()
                    if n<0 or n in reachable:continue
                    reachable.add(n)
                    todo.extend(renderclips[n][1:3])
                meta['native_render_index_range_valid']=min(reachable)>=head and max(reachable)<head+len(remapped)
                meta['reachable_original_index_range']=[min(reachable),max(reachable)]
            self.hull_metadata.append(meta)
        self.sha256=hashlib.sha256(self.data).hexdigest()
    def point(self,hull,p):
        head,clips=self.hulls[hull]
        return actual.point(self.planes,clips,head,p)
    def traces(self,exe,folder,hull,cases,baseline=False):
        head,clips=self.hulls[hull]
        return actual.batch(exe,folder,self.planes,clips,head,cases,baseline=baseline,version=self.version)
    def summary(self):
        return {'path':str(self.path),'bytes':len(self.data),'sha256':self.sha256,'crc32':zlib.crc32(self.data)&0xffffffff,'version':self.version,'extended':self.extended,'disk_clip_bits':self.disk_clip_bits,'world_bounds':[list(self.world[:3]),list(self.world[3:6])],'entities':len(self.entities),'hulls':self.hull_metadata}


def sample_floors(m:MapCollision,seam:float):
    rng=random.Random(42972)
    lo,hi=m.world[:3],m.world[3:6]
    samples=[]
    for e in m.entities:
        if e.get('classname') in ('ms_player_begin','ms_player_spawn','ms_player_spec') and e.get('origin'):
            x,y,z=map(float,e['origin'].split())
            for dx,dy in ((0,0),(-64,0),(64,0),(0,-64),(0,64)):
                samples.append((e.get('classname')+':'+e.get('message',''),x+dx,y+dy,z+32,z-320))
    for x in range(math.ceil(lo[0]+64),math.floor(hi[0]-64),256):
        for y in range(math.ceil(lo[1]+64),math.floor(min(hi[1]-64,seam-256)),256):
            samples.append(('grid',x,y,hi[2]-64,lo[2]+32))
    for _ in range(1024):
        x=rng.uniform(lo[0]+64,hi[0]-64)
        y=rng.uniform(lo[1]+64,min(hi[1]-64,seam-256))
        samples.append(('random',x,y,hi[2]-64,lo[2]+32))
    # The legacy map has solid mountain/ceiling regions at the world-top
    # height. Sample lower clear pockets too, including the Nash valley and
    # caves, rather than treating only a ray from the top as terrain coverage.
    spatial=[s for s in samples if s[0] in ('grid','random')]
    for name,x,y,top,bottom in spatial:
        for z in range(math.floor(top)-256,math.ceil(bottom)+127,-256):
            samples.append((name+':height'+str(z),x,y,z,max(bottom,z-512)))
    return samples


def point_clear_segment(m,hull,a,b):
    return all(m.point(hull,tuple(a[i]+(b[i]-a[i])*k/32 for i in range(3)))==-1 for k in range(33))


def audit_north_corridor(m,exe,folder,seam):
    results=[]
    for hull,height in enumerate((0,36,32,18)):
        cases=[((x,seam-64,3072+height+.125),(x,seam+96,3072+height+.125)) for x in (1450,1488,1528,1568,1606)]
        old=m.traces(exe,folder,hull,cases,True)
        new=m.traces(exe,folder,hull,cases)
        results.append({'hull':hull,'cases':[{'start':c[0],'end':c[1],'baseline':o,'interval':n}for c,o,n in zip(cases,old,new)]})
    return results


def replay_seam_walk(candidate,exe,folder,seam,offset):
    # The actual PM_WalkMove body receives the actual C world-hull result as
    # its trace fixture. Acceleration is supplied at steady walk/gallop speed;
    # a clear first trace must return without invoking either stair/slide path.
    def f32(v):return struct.unpack('<f',struct.pack('<f',v))[0]
    positions=[]
    groundcases=[]
    for lane in (-64,-32,0,32,64):
        for y in (seam-64,seam-16,seam-2,seam,seam+2,seam+16,seam+64):
            x=1528+offset[0]+lane
            groundcases.append(((x,y,3200+offset[2]),(x,y,3072+offset[2])))
            positions.append((lane,y))
    grounds=candidate.traces(exe,folder,1,groundcases)
    move_cases=[];settings=[]
    for position,ground in zip(positions,grounds):
        assert ground['fraction']<1 and not ground['startsolid'] and ground['normal'][2]>=.7,position
        p=ground['end']
        for speed in (320,520):
            for dt in (1/120,1/60,.02,.03,.05,.1):
                for direction in (-1,1):
                    signed=speed*direction
                    end=(p[0],f32(p[1]+f32(signed*f32(dt))),p[2])
                    move_cases.append((p,end))
                    settings.append((signed,dt,position))
    moves=candidate.traces(exe,folder,1,move_cases)
    def scalar(v):
        s=format(v,'.9g')
        return s+'f' if '.'in s or 'e'in s else s+'.0f'
    def vector(p):return 'Vector('+','.join(scalar(v)for v in p)+')'
    lines=['int main(){']
    for (p,end),(speed,dt,label),trace in zip(move_cases,settings,moves):
        assert trace['fraction']==1 and not trace['startsolid'] and not trace['allsolid'],(label,speed,dt,trace)
        lines.append(f'Reset();state.origin={vector(p)};state.cmd.forwardmove={speed}.0f;state.maxspeed={abs(speed)}.0f;state.frametime={scalar(dt)};traces={{T(1,{vector(trace["end"])})}};PM_WalkMove();assert(traceIndex==1 && flyIndex==0);assert(std::fabs(state.origin[1]-{scalar(trace["end"][1])})<.001f && std::fabs(state.origin[2]-{scalar(trace["end"][2])})<.001f);')
    lines.append(f'std::puts("{len(moves)} actual PM_WalkMove seam frames passed");return 0;}}')
    body=walk_replay.function_body(walk_replay.SOURCE.read_text())
    cpp=folder/'seam-walk.cpp';binary=folder/'seam-walk.exe'
    cpp.write_text(walk_replay.PRELUDE+'\n'+body+'\n'+'\n'.join(lines))
    build=subprocess.run(['cl.exe','/nologo','/std:c++17','/EHsc','/Od','/Zi','/RTC1','/UNDEBUG',str(cpp),'/Fe:'+str(binary)],cwd=folder,text=True,capture_output=True)
    assert build.returncode==0,build.stdout+build.stderr
    run=subprocess.run([str(binary)],cwd=folder,text=True,capture_output=True)
    assert run.returncode==0,run.stdout+run.stderr
    return {'pass':True,'hull':1,'frames':len(moves),'speeds':[320,520],'directions':[-1,1],'frame_times':[1/120,1/60,.02,.03,.05,.1],'output':run.stdout.strip(),'source':str(walk_replay.SOURCE),'scope':'Actual PM_WalkMove with actual C map-hull trace fixtures and steady-speed acceleration; dynamic entity collision and native frame scheduling require gameplay testing.'}


def audit_original(m,exe,folder,seam):
    floors=sample_floors(m,seam)
    report={'map':m.summary(),'floor_samples_per_hull':len(floors),'hulls':[],'north_corridor':audit_north_corridor(m,exe,folder,seam)}
    allcases=[]
    for hull in range(4):
        cases=[((x,y,top),(x,y,bottom)) for _,x,y,top,bottom in floors]
        old=m.traces(exe,folder,hull,cases,True)
        new=m.traces(exe,folder,hull,cases)
        differences=[]
        horizontal=[]
        names=[]
        for sample,a,b,o,n in zip(floors,[c[0]for c in cases],[c[1]for c in cases],old,new):
            if o['fraction']<1 and n['fraction']<1 and not o['startsolid'] and not n['startsolid']:
                distance=max(abs(o['end'][i]-n['end'][i]) for i in range(3))
                if distance>.0625 and len(differences)<20:differences.append({'sample':sample,'endpoint_difference':distance,'baseline':o,'interval':n})
            if n['fraction']<1 and not n['startsolid'] and not n['allsolid'] and n['normal'][2]>=.7:
                p=n['end']
                for dx,dy in ((8.6666667,0),(-8.6666667,0),(0,8.6666667),(0,-8.6666667)):
                    horizontal.append((p,(p[0]+dx,p[1]+dy,p[2])))
                    names.append(sample[0])
        oldwalk=m.traces(exe,folder,hull,horizontal,True)
        newwalk=m.traces(exe,folder,hull,horizontal)
        for difference in differences:
            oldend=difference['baseline']['end']
            newend=difference['interval']['end']
            probes=[oldend,(oldend[0],oldend[1],oldend[2]-.125),tuple((a+b)*.5 for a,b in zip(oldend,newend)),newend,(newend[0],newend[1],newend[2]-16)]
            oldpoints=m.traces(exe,folder,hull,[(p,p)for p in probes],True)
            newpoints=m.traces(exe,folder,hull,[(p,p)for p in probes])
            difference['zero_length_native_point_comparisons']=[{'point':p,'baseline':o,'interval':n}for p,o,n in zip(probes,oldpoints,newpoints)]
            difference['interpretation']='Boundary precision differences require evaluating the physical segment interval, not assuming the earlier baseline contact is valid. Here both implementations retain a solid hit; native float32 point classification may disagree with unbiased double interval classification at a stored diagonal-plane boundary.'
        bogus={'baseline':[],'interval':[]}
        for name,case,o,n in zip(names,horizontal,oldwalk,newwalk):
            for label,t in [('baseline',o),('interval',n)]:
                if t['fraction']<1 and t['normal'][2]<-.7 and point_clear_segment(m,hull,*case):
                    if len(bogus[label])<20:bogus[label].append({'sample':name,'case':case,'trace':t})
        report['hulls'].append({'hull':hull,'valid_walkable_floors':len(horizontal)//4,'horizontal_sweeps':len(horizontal),'floor_profile':{'baseline':actual.summarize(old),'interval':actual.summarize(new)},'horizontal_profile':{'baseline':actual.summarize(oldwalk),'interval':actual.summarize(newwalk)},'floor_contact_differences_over_0_0625_examples':differences,'false_ceiling_examples':bogus})
        allcases.append((floors,cases,new,horizontal,newwalk))
    return report,allcases


def audit_candidate(original,candidate,exe,folder,seam,offset,original_cases):
    report={'map':candidate.summary(),'offset':offset,'seam_y':seam,'preserved_geometry':[],'seam':[],'failures':[]}
    def translated(p):return tuple(p[i]+offset[i] for i in range(3))
    rng=random.Random(11385)
    points=[]
    lo,hi=original.world[:3],original.world[3:6]
    for _ in range(6000):
        points.append((rng.uniform(lo[0]-32,hi[0]+32),rng.uniform(lo[1]-32,min(hi[1]+32,seam-offset[1]-256)),rng.uniform(lo[2]-32,hi[2]+32)))
    for hull in range(4):
        mismatches=[]
        for p in points:
            oldcontent=original.point(hull,p)
            newcontent=candidate.point(hull,translated(p))
            if oldcontent!=newcontent and len(mismatches)<20:mismatches.append({'point':p,'original':oldcontent,'candidate':newcontent})
        floors,cases,reference,_,_=original_cases[hull]
        chosen=[(c,t,s) for c,t,s in zip(cases,reference,floors) if c[0][1]+offset[1]<seam-256 and c[1][1]+offset[1]<seam-256]
        results=candidate.traces(exe,folder,hull,[(translated(a),translated(b))for (a,b),_,_ in chosen])
        contact_mismatches=[]
        for (case,o,sample),n in zip(chosen,results):
            flags=all(o[k]==n[k]for k in ('allsolid','startsolid','inopen','inwater'))
            fraction=abs(o['fraction']-n['fraction'])<=.001
            endpoint=max(abs(o['end'][i]+offset[i]-n['end'][i])for i in range(3))<=.0625
            if not(flags and fraction and endpoint)and len(contact_mismatches)<20:contact_mismatches.append({'sample':sample,'original':o,'candidate':n})
        preserve={'hull':hull,'point_checks':len(points),'point_mismatch_examples':mismatches,'contact_checks':len(chosen),'contact_mismatch_examples':contact_mismatches}
        report['preserved_geometry'].append(preserve)
        if mismatches or contact_mismatches:report['failures'].append({'changed_original_geometry':preserve})
        if hull==0 and not candidate.hull_metadata[0].get('native_render_index_range_valid',True):report['failures'].append({'invalid_native_render_indices':candidate.hull_metadata[0]})
    # Every hull is traced through the exact shared-space seam in both
    # directions, then standing hull ground continuity is sampled finely.
    halfheight=(0,36,32,18)
    for hull in range(4):
        groundcases=[];locations=[]
        for lane in (-64,-32,0,32,64):
            for y in range(math.floor(seam-128),math.ceil(seam+257),2):
                x=1528+offset[0]+lane
                level=3072+offset[2]+halfheight[hull]
                groundcases.append(((x,y,level+128),(x,y,level-64)))
                locations.append((lane,y))
        ground=candidate.traces(exe,folder,hull,groundcases)
        vertical_failures=[];discontinuities=[];previous={};walking=[];walklabels=[]
        for (lane,y),t in zip(locations,ground):
            if t['fraction']==1 or t['startsolid'] or t['allsolid'] or t['normal'][2]<.7:
                if len(vertical_failures)<20:vertical_failures.append({'lane':lane,'y':y,'trace':t})
                continue
            if lane in previous and abs(t['end'][2]-previous[lane][1])>1.0:
                if len(discontinuities)<20:discontinuities.append({'lane':lane,'previous':previous[lane],'current':[y,t['end'][2]]})
            previous[lane]=(y,t['end'][2])
            p=t['end']
            for direction in (-1,1):
                for length in (5.2,8.6666667,32):
                    end=(p[0],p[1]+direction*length,p[2])
                    walking.append((p,end));walklabels.append((lane,y,direction,length))
        moves=candidate.traces(exe,folder,hull,walking)
        movement_failures=[]
        for label,case,t in zip(walklabels,walking,moves):
            if t['fraction']<1 or t['startsolid'] or t['allsolid']:
                # The entry apron is intended flat. Any obstruction here is
                # material, including a leftover legacy expanded clip barrier.
                if len(movement_failures)<20:movement_failures.append({'lane_y_direction_length':label,'case':case,'trace':t})
        seam_result={'hull':hull,'ground_checks':len(groundcases),'movement_checks':len(walking),'floor_failures':vertical_failures,'floor_discontinuities_over_one_unit':discontinuities,'movement_failures':movement_failures}
        report['seam'].append(seam_result)
        if vertical_failures or discontinuities or movement_failures:report['failures'].append({'seam_hull_failure':seam_result})
    report['pass']=not report['failures']
    if report['pass']:report['actual_walk_move_replay']=replay_seam_walk(candidate,exe,folder,seam,offset)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original',type=Path,default=Path('C:/MSR/Portable-Package/game/msr/maps/daragoth.bsp'))
    parser.add_argument('--bsp',type=Path)
    parser.add_argument('--offset',type=float,nargs=3,default=(0,0,0))
    parser.add_argument('--seam',type=float,default=3216)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    sys.setrecursionlimit(12000)
    original=MapCollision(args.original)
    with tempfile.TemporaryDirectory(prefix='msr-daragoth-audit-')as td:
        folder=Path(td);exe=actual.build(folder)
        report,cases=audit_original(original,exe,folder,args.seam)
        if args.bsp:report['candidate']=audit_candidate(original,MapCollision(args.bsp),exe,folder,args.seam,args.offset,cases)
    report['scope']='Actual frozen C interval tracer. World hulls only; dynamic entities, transition triggers, renderer/PVS and FN state require native gameplay checks.'
    report['engine_source_sha256']=hashlib.sha256((ROOT/'Engine-Source/Xash3D/engine/common/pm_trace.c').read_bytes()).hexdigest()
    report['debug_compile']='MSVC x86 /TC /std:c11 /Od /Zi /RTC1 /UNDEBUG /fp:precise; PM_WalkMove replay MSVC x86 /std:c++17 /Od /Zi /RTC1 /UNDEBUG'
    args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'original':report['map'],'floor_samples_per_hull':report['floor_samples_per_hull'],'hull_walk_samples':[h['horizontal_sweeps']for h in report['hulls']],'candidate_pass':report.get('candidate',{}).get('pass'),'report':str(args.report)},indent=2))
    if args.bsp and not report['candidate']['pass']:raise SystemExit(1)

if __name__=='__main__':main()
