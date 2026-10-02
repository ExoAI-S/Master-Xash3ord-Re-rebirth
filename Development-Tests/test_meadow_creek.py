"""Independently verify an entity-only, swimmable meadow creek candidate.

The immutable compiled water hull is instanced four times. Fluid checks replay
the translated hull and skin setting over world contents; optional actual-C
checks cover world floors only. Native waterlevel and appearance still need a
separate game check. No map, game, existing build, or input is modified.
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

REPO=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(REPO/'Packaging-Work/BigWorld/tools'),str(REPO/'Design-Source/Daragoth-Meadow')]
from bsp30 import BSP
from meadow_surface import SurfaceIndex

BASE_SHA='7db33aa84ff9f032d1267e3d37d2795e959e414c262dcb896c83a3169c1e5570'
PREFIX='plains_creek_water_'
GROUND_TEXTURES=('DPGRASS','DPPATH','DPDIRT')
Y_SHIFTS=(-1140,-380,380,1140)
EMPTY,SOLID,WATER=-1,-2,-3


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def section():
    return {'failure_count':0,'failures':[]}


def fail(result,message,**details):
    result['failure_count']+=1
    if len(result['failures'])<25:result['failures'].append({'message':message,**details})


def finish(result):
    result['pass']=result['failure_count']==0
    return result


def vec(entity,key='origin'):
    values=tuple(map(float,entity.get(key,'0 0 0').split()))
    if len(values)!=3 or not all(math.isfinite(v) for v in values):
        raise ValueError('Expected a finite three-component '+key)
    return values


def creek(entity):
    return entity.classname=='func_water' and entity.get('msr_region')=='daragoth_plains'


def f32(value):
    return struct.unpack('<f',struct.pack('<f',value))[0]


def hull0_contents(bsp,head,point):
    """Production float32 dot products and child0 at zero; no boundary epsilon."""
    point=tuple(map(f32,point));node=head;visited=0
    while node>=0:
        visited+=1
        if visited>len(bsp.nodes) or node>=len(bsp.nodes):raise ValueError('Invalid or cyclic rendered hull')
        record=bsp.nodes[node];plane=bsp.planes[record.planenum]
        if plane.type<3:
            distance=f32(point[plane.type]-plane.dist)
        else:
            dot=f32(f32(f32(point[0]*plane.normal[0])+f32(point[1]*plane.normal[1]))+f32(point[2]*plane.normal[2]))
            distance=f32(dot-plane.dist)
        node=record.children[0 if distance>=0 else 1]
    return bsp.leafs[-1-node].contents


def world_contents(bsp,point):
    return hull0_contents(bsp,bsp.models[0].headnode[0],point)


def brush_contents(bsp,entity,point):
    origin=vec(entity)
    local=tuple(f32(f32(point[k])-f32(origin[k])) for k in range(3))
    model=bsp.models[int(entity.get('model')[1:])]
    return hull0_contents(bsp,model.headnode[0],local)


def contents(bsp,waters,point):
    """SV_WaterLinks/PM_PointContents overlay for these static skin=-3 brushes.

    World solid/sky wins; world water already remains water. The engine treats
    any nonempty translated brush hull as inside and returns entity.skin.
    Skin=-3 makes CBaseDoor spawn this func_water as SOLID_NOT.
    """
    current=world_contents(bsp,point)
    if current!=EMPTY:return current
    for entity in waters:
        if entity.get('skin')=='-3' and brush_contents(bsp,entity,point)!=EMPTY:return WATER
    return current


def solid_floor(bsp,x,y,upper,lower):
    """Locate a world floor beneath a clear point, without inventing a face.

    Some pre-existing terrain render polygons below the bridge are absent.
    Their unchanged solid hull still defines the bed. Record this distinction
    explicitly; the new water surface covers these locations independently.
    """
    if world_contents(bsp,(x,y,upper))!=EMPTY or world_contents(bsp,(x,y,lower))!=SOLID:return None
    for _ in range(32):
        middle=f32((upper+lower)/2)
        if middle<=lower or middle>=upper:break
        if world_contents(bsp,(x,y,middle))==SOLID:lower=middle
        else:upper=middle
    return (lower+upper)/2


def preservation(base_path,path,old,bsp):
    result=section();base=base_path.read_bytes();new=path.read_bytes()
    result['non_entity_lumps_identical']={}
    for i in range(1,15):
        a,n=struct.unpack_from('<2i',base,4+8*i);b,m=struct.unpack_from('<2i',new,4+8*i)
        same=n==m and base[a:a+n]==new[b:b+m]
        result['non_entity_lumps_identical'][str(i)]=same
        if not same:fail(result,'Non-entity lump changed',lump=i)
    if len(new)<len(base) or new[:4]!=base[:4] or new[12:len(base)]!=base[12:]:
        fail(result,'Source prefix changed outside entity descriptor')
    original=[e for e in old.entities if creek(e)]
    waters=[e for e in bsp.entities if creek(e)]
    if len(original)!=1 or len(waters)!=4:
        fail(result,'Expected exactly one original and four candidate creek entities',original=len(original),candidate=len(waters))
    kept_old=[e.pairs for e in old.entities if not creek(e)]
    kept_new=[e.pairs for e in bsp.entities if not creek(e)]
    if kept_old!=kept_new:fail(result,'Ordered non-creek entity records changed')
    if len(kept_old)!=1043 or len(bsp.entities)!=1047:
        fail(result,'Expected 1043 preserved records and1047 final entities',kept=len(kept_old),total=len(bsp.entities))
    result.update({'preserved_non_creek_records':len(kept_old),'creek_entities':len(waters),
                   'total_entities':len(bsp.entities),'nominal_network_reserve':2047-len(bsp.entities)})
    return finish(result),original,waters


def entities_check(original,waters,bsp):
    result=section()
    if len(original)!=1 or len(waters)!=4:return finish(result)
    old=original[0];origin=vec(old);model=old.get('model')
    if model!='*162':fail(result,'Unexpected original creek brush model',model=model)
    record=bsp.models[int(model[1:])]
    if tuple(record.mins)!=(-11980.,1420.,96.) or tuple(record.maxs)!=(11980.,2180.,216.):
        fail(result,'Original shared water bounds differ from audited shape')
    names=Counter(e.get('targetname') for e in waters)
    if names!=Counter(PREFIX+f'{i:02d}' for i in range(4)):fail(result,'Incorrect or duplicate creek targetnames',actual=names)
    by_name={e.get('targetname'):e for e in waters}
    allowed={'origin','skin','targetname','WaveHeight','spawnflags'}
    for i,dy in enumerate(Y_SHIFTS):
        name=PREFIX+f'{i:02d}';e=by_name.get(name)
        if e is None:continue
        expected=(origin[0],origin[1]+dy,origin[2]+32)
        if max(abs(a-b) for a,b in zip(vec(e),expected))>.00011:
            fail(result,'Creek instance origin differs from audited translation',name=name,expected=expected,actual=vec(e))
        for key,value in {'model':model,'skin':'-3','msr_region':'daragoth_plains','rendermode':'2',
                          'renderamt':'120','WaveHeight':'0','spawnflags':'0'}.items():
            if e.get(key)!=value:fail(result,'Creek entity key differs from fixed policy',name=name,key=key,actual=e.get(key))
        for key,value in old.pairs:
            if key not in allowed and e.get(key)!=value:fail(result,'Unrelated water key changed',name=name,key=key)
        if any(key not in {k for k,v in old.pairs}|allowed for key,value in e.pairs):
            fail(result,'Unexpected additional water key',name=name)
        if vec(e,'angles')!=(0.,0.,0.):fail(result,'Water instance is rotated',name=name)
    for e in bsp.entities:
        for key,value in e.pairs:
            if key in ('target','killtarget') and value in names:fail(result,'Static water has a door activation reference',key=key,target=value)
    result.update({'shared_model':model,'model_bounds':[record.mins,record.maxs],
                   'water_origins':{e.get('targetname'):vec(e) for e in waters},
                   'original_skin':old.get('skin'),
                   'fluid_policy':'skin=-3 causes SOLID_NOT; translated nonempty model hull supplies CONTENTS_WATER'})
    return finish(result)


def cross_section(index,y,xmin,xmax):
    """Exact linear face extrema along a shoreline, clipped to water X bounds."""
    ends=[];faces=0
    for s in index.surfaces:
        if s.texture not in GROUND_TEXTURES or not s.bounds[1]<=y<=s.bounds[3]:continue
        xs=[];points=s.points
        for a,b in zip(points,points[1:]+points[:1]):
            if a[1]==b[1]:
                if abs(y-a[1])<1e-5:xs.extend((a[0],b[0]))
            elif min(a[1],b[1])<=y<=max(a[1],b[1]):
                xs.append(a[0]+(b[0]-a[0])*(y-a[1])/(b[1]-a[1]))
        if len(xs)<2:continue
        lo=max(min(xs),xmin);hi=min(max(xs),xmax)
        if lo>hi:continue
        faces+=1
        for x in (lo,hi):ends.append(((s.dist-s.normal[0]*x-s.normal[1]*y)/s.normal[2],x,s.face))
    return {'faces':faces,'minimum':min(ends) if ends else None,'maximum':max(ends) if ends else None}


def geometry_and_contents(bsp,original,waters,index):
    result=section();native=[];floor_probes=[]
    if len(original)!=1 or len(waters)!=4:return finish(result),floor_probes
    old=original[0];ox,oy,oz=vec(old);record=bsp.models[int(old.get('model')[1:])]
    top=oz+32+record.maxs[2];bottom=oz+32+record.mins[2]
    boxes=[]
    for e in sorted(waters,key=lambda e:vec(e)[1]):
        o=vec(e);boxes.append([[o[k]+record.mins[k] for k in range(3)],[o[k]+record.maxs[k] for k in range(3)]])
    for a,b in zip(boxes,boxes[1:]):
        if abs(a[1][1]-b[0][1])>.0001:fail(result,'Water volumes overlap or leave a seam gap')
    south,north=boxes[0][0][1],boxes[-1][1][1]
    shore=[]
    for name,y in [('south',south),('north',north)]:
        s=cross_section(index,y,boxes[0][0][0],boxes[0][1][0]);minimum=s['minimum']
        clearance=minimum[0]-top if minimum else None
        if minimum is None or clearance<24:fail(result,'Outer water edge is exposed above meadow ground',shore=name,clearance=clearance)
        shore.append({'shore':name,'world_y':y,'face_cross_section':s,'minimum_ground_above_water':clearance})
    counts=Counter();depths=[];bed_counts=Counter();missing_beds=[]
    # Independent coverage across the creek; skip world-solid pillars/terrain
    # explicitly rather than interpreting inaccessible brush volume as water.
    for x in range(-11000,11001,128):
        for y in range(math.ceil(south-oy),math.floor(north-oy)+1,32):
            wx,wy=ox+x,oy+y;s=index.at(wx,wy,GROUND_TEXTURES)
            if s is None:counts['missing_meadow_floor']+=1;continue
            if s['z']>=top-4:counts['dry_bank_samples']+=1;continue
            point=(wx,wy,(s['z']+top)/2)
            if world_contents(bsp,point)!=EMPTY:counts['world_obstacle_samples']+=1;continue
            counts['accessible_wet_samples']+=1
            if contents(bsp,waters,point)!=WATER:fail(result,'Accessible creek sample has no translated water contents',point=point)
            if contents(bsp,waters,(wx,wy,top+8))!=EMPTY:fail(result,'Water extends above its rendered surface',point=(wx,wy,top+8))
    if counts['accessible_wet_samples']<1000:fail(result,'Insufficient independently verified wet creek coverage',samples=counts['accessible_wet_samples'])
    # Full bridge opening, excluding the rock support columns at X304/-336.
    for x in range(-288,289,32):
        for y in range(1104,2497,32):
            wx,wy=ox+x,oy+y;s=index.at(wx,wy,GROUND_TEXTURES)
            if s is None:
                bed_counts['pre_existing_rendered_floor_missing']+=1
                if len(missing_beds)<10:missing_beds.append([wx,wy])
                z=solid_floor(bsp,wx,wy,top-4,bottom-8)
                if z is None:fail(result,'Missing solid bridge creek bed',world_xy=[wx,wy]);continue
                bed_counts['collision_floor_fallback']+=1
            else:
                bed_counts['rendered_floor']+=1;z=s['z']
            depth=top-z;depths.append(depth);point=(wx,wy,min(top-4,z+8))
            if depth<12 or bottom>z-16 or world_contents(bsp,point)!=EMPTY or contents(bsp,waters,point)!=WATER:
                fail(result,'Bridge opening does not contain continuous water over its bed',point=point,depth=depth)
            if world_contents(bsp,(wx,wy,z-8))!=SOLID or contents(bsp,waters,(wx,wy,z-8))!=SOLID:
                fail(result,'Water overlay incorrectly replaces solid creek bed',point=(wx,wy,z-8))
    seams=[]
    for y in [a[1][1] for a in boxes[:-1]]:
        summary=Counter()
        for x in (-2000,-700,0,700,2000):
            for delta in (-.01,0,.01):
                point=(ox+x,y+delta,top-8);world=world_contents(bsp,point);actual=contents(bsp,waters,point)
                expected=WATER if world==EMPTY else world
                if actual!=expected:fail(result,'Adjacent water seam has incorrect contents',point=point,expected=expected,actual=actual)
                summary['water' if actual==WATER else 'preserved_world_contents']+=1
        seams.append({'world_y':y,'counts':summary})
    # Water is at least232units below the deck underside and cannot reach
    # bridge standing points or the ramps. Terrain/hulls remain byte-identical.
    bridge_surfaces=[]
    for x in (-288,0,288):
        for y in range(700,2901,50):
            wx,wy=ox+x,oy+y;s=index.at(wx,wy)
            if s is None:fail(result,'Missing bridge or approach rendered floor');continue
            point=(wx,wy,s['z']+8)
            if world_contents(bsp,point)!=EMPTY or contents(bsp,waters,point)!=EMPTY:
                fail(result,'Bridge or approach standing point is not dry and clear',point=point)
            floor_probes.append({'world_xy':[wx,wy],'rendered_floor_z':s['z'],'label':f'bridge-x{x}-y{y}'})
            if 1100<=y<=2500 and x==0:bridge_surfaces.append(s['z'])
    underside=oz+480
    if top>underside-200 or not bridge_surfaces or max(abs(z-(oz+512)) for z in bridge_surfaces)>.01:
        fail(result,'Water/bridge height policy or compiled deck is inconsistent',water_top=top,bridge_underside=underside)
    for x,y in ((0,1200),(0,1800),(0,2300),(-700,1800),(700,1800)):
        s=index.at(ox+x,oy+y,GROUND_TEXTURES);native.append({'world_xy':[ox+x,oy+y],'ground_z':s['z'],'water_top_z':top,'wet_probe_z':min(top-8,s['z']+16)})
    result.update({'water_bounds':boxes,'water_top_world_z':top,'water_bottom_world_z':bottom,
                   'outer_shores':shore,'creek_grid_spacing':[128,32],'creek_grid_counts':counts,
                   'bridge_opening_wet_probes':len(depths),'bridge_opening_water_depth_range':[min(depths),max(depths)] if depths else None,
                   'bridge_bed_probe_types':bed_counts,'pre_existing_missing_rendered_bed_examples':missing_beds,
                   'water_clearance_below_bridge_underside':underside-top,'dry_bridge_and_approach_points':len(floor_probes),
                   'seams':seams,'native_waterlevel_probe_points':native,
                   'scope':'Float32 compiled-hull/entity-skin fluid overlay and static rendered ground/deck checks. Native swimming, model replication, region lifecycle and seam appearance require game evidence.'})
    return finish(result),floor_probes


def actual_c(path,probes):
    if shutil.which('cl.exe') is None:return {'status':'skipped','pass':None,'reason':'--actual-c requested but cl.exe unavailable'}
    import test_daragoth_expanded_collision as collision
    result=section();result.update({'status':'ran','world_bridge_floor_traces':0});model=collision.MapCollision(path)
    with tempfile.TemporaryDirectory(prefix='msr-creek-world-qa-') as temp:
        folder=Path(temp);exe=collision.actual.build(folder)
        for start in range(0,len(probes),5000):
            items=probes[start:start+5000];cases=[((p['world_xy'][0],p['world_xy'][1],p['rendered_floor_z']+132),(p['world_xy'][0],p['world_xy'][1],p['rendered_floor_z']-60)) for p in items]
            for p,t in zip(items,model.traces(exe,folder,1,cases)):
                if t['startsolid'] or t['allsolid'] or t['fraction']==1 or t['normal'][2]<.7:
                    fail(result,'Actual C standing bridge/approach world floor failed',label=p['label'],trace=t)
            result['world_bridge_floor_traces']+=len(cases)
    result['engine_pm_trace_sha256']=sha(REPO/'Engine-Source/Xash3D/engine/common/pm_trace.c')
    result['scope']='Actual engine C hull1 static bridge/approach floors only; this does not execute SV_WaterLinks or PM_PointContents and does not prove native waterlevel.'
    return finish(result)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('base','bsp','report-source','report'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--actual-c',action='store_true');args=parser.parse_args();sys.setrecursionlimit(20000)
    inputs={'base':args.base,'bsp':args.bsp,'report_source':args.report_source}
    if args.report.resolve() in {p.resolve() for p in inputs.values()}:parser.error('Report must not overwrite an input')
    hashes={k:sha(p) for k,p in inputs.items()};source=json.loads(args.report_source.read_text());metadata=section()
    if hashes['base']!=BASE_SHA:fail(metadata,'Unexpected frozen base',expected=BASE_SHA,actual=hashes['base'])
    if source.get('base_sha256')!=hashes['base']:fail(metadata,'Builder report base hash mismatch')
    output_hash=source.get('output_sha256',source.get('sha256',source.get('candidate_sha256')))
    if output_hash!=hashes['bsp']:fail(metadata,'Builder report output hash mismatch',reported=output_hash,actual=hashes['bsp'])
    old=BSP.load(args.base);bsp=BSP.load(args.bsp);index=SurfaceIndex(bsp)
    report={'input_sha256':hashes,'metadata':finish(metadata),'actual_c_requested':args.actual_c}
    report['preservation'],original,waters=preservation(args.base,args.bsp,old,bsp)
    report['entities']=entities_check(original,waters,bsp)
    print('Checking preserved map, four translated liquid brushes, shores, seams and dry bridge',flush=True)
    report['geometry_and_contents'],probes=geometry_and_contents(bsp,original,waters,index)
    report['actual_c']=actual_c(args.bsp,probes) if args.actual_c else {'status':'not_requested','pass':None,'reason':'No C harness requested'}
    report['inputs_unchanged_during_verification']=hashes=={k:sha(p) for k,p in inputs.items()}
    report['static_pass']=report['inputs_unchanged_during_verification'] and all(report[k]['pass'] for k in ('metadata','preservation','entities','geometry_and_contents'))
    report['pass']=report['static_pass'] and (not args.actual_c or report['actual_c']['pass'] is True)
    report['scope']='Independent entity-only preservation and compiled brush fluid-overlay proof. Actual-C world floors only if run; native fluid behavior, appearance and lifecycle are not claimed.'
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'pass':report['pass'],'static_pass':report['static_pass'],'bsp_sha256':hashes['bsp'],
                      'entities':len(bsp.entities),'water_top_world_z':report['geometry_and_contents'].get('water_top_world_z'),
                      'wet_grid_probes':report['geometry_and_contents'].get('creek_grid_counts',{}).get('accessible_wet_samples'),
                      'actual_c':report['actual_c']['status'],'report':str(args.report)},indent=2))
    return 0 if report['pass'] else 1


if __name__=='__main__':raise SystemExit(main())
