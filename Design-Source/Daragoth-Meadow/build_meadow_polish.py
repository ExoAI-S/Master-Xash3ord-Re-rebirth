"""Whole-map meadow groundcover pass over a frozen compiled Daragoth candidate.

Redistributes grass across fields and original valley without recompiling or
changing any collision, geometry, lighting, road texture, NPC, or riding data.
All outputs are private; the original installed BSP is never written.
"""
from __future__ import annotations
import argparse
import collections
import hashlib
import json
import math
from pathlib import Path
import random
import struct
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO/'Packaging-Work/BigWorld/tools'))
sys.path.insert(0, str(REPO/'Development-Tests'))
from bsp30 import BSP, Entity, format_entities
from meadow_surface import SurfaceIndex, coverage_survey
from test_daragoth_meadow import grass_roots
from test_daragoth_expanded_collision import MapCollision

SOURCE_MODEL = 'models/plains/meadow_grass_patch.mdl'
MODEL = 'models/plains/meadow_low_grass.mdl'
TEXTURES = ('DPGRASS', 'medgrass2_ewoks')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lump_hashes(data):
    return {str(i):hashlib.sha256(data[offset:offset+size]).hexdigest()
            for i in range(15) for offset,size in [struct.unpack_from('<2i',data,4+8*i)]}


def transform_root(root, pitch, roll):
    # The production stock renderer negates pitch and preserves roll.
    cp, sp = math.cos(-pitch), math.sin(-pitch)
    cr, sr = math.cos(roll), math.sin(roll)
    x,y,z = root
    return cp*x + sr*sp*y + cr*sp*z, cr*y - sr*z, -sp*x + sr*cp*y + cr*cp*z


def distance_to_segment(x,y,a,b):
    dx,dy=b[0]-a[0],b[1]-a[1]
    f=max(0,min(1,((x-a[0])*dx+(y-a[1])*dy)/(dx*dx+dy*dy))) if dx or dy else 0
    return math.hypot(x-a[0]-f*dx,y-a[1]-f*dy)


def build(base, source_report, merge_report, model, out, expected_sha,
          field_goal=840, valley_goal=80):
    if sha(base) != expected_sha:
        raise ValueError('Base candidate changed before meadow pass')
    data=base.read_bytes();bsp=BSP.load(base)
    source=json.loads(source_report.read_text());merge=json.loads(merge_report.read_text())
    offset=merge['plains_offset'];index=SurfaceIndex(bsp);collision=MapCollision(base)
    roots=grass_roots(model)
    if not roots:raise ValueError('Grass model has no neutral roots')
    radius=math.ceil(max(math.hypot(p[0],p[1])for p in roots))+2
    kept=[e for e in bsp.entities if not(e.classname=='env_model' and e.get('model') in (SOURCE_MODEL,MODEL))]
    removed=len(bsp.entities)-len(kept)
    if removed!=source['scenery']['counts']['grass']:
        raise ValueError('Grass removal count differs from matching source report')
    budget=1900-len(kept)
    if field_goal+valley_goal>budget:
        raise ValueError(f'Grass goals exceed whole-map entity reserve: {field_goal+valley_goal}>{budget}')
    scenery=source['scenery']['placements'];village=source['scenery']['village']
    stable=source['landmarks']['stable'];ruins=source['landmarks']['ruins']
    river_y=source['landmarks']['river_center_y']
    routes=[]
    for actor in village['residents']:
        route=actor['route']
        routes.extend(zip(route,route[1:]+route[:1]))
    protect=[]
    for e in kept:
        if e.classname.startswith('ms_player') or e.classname in ('ms_npc','ms_stablemaster','ms_horse'):
            value=e.get('origin')
            if value:
                p=list(map(float,value.split()))
                protect.append((p[0],p[1],240 if e.classname.startswith('ms_player') else 100))
    tree_centers=[(p['origin'][0]+offset[0],p['origin'][1]+offset[1],20)
                  for p in scenery if p['kind'] in ('oak','birch','pine','apple')]
    rejected=collections.Counter();placements=[];spatial=collections.defaultdict(list)
    rng=random.Random(202610013)
    def road_x(y):return 250*math.sin(y/3800)
    def fit(x,y,region):
        surface=index.at(x,y,TEXTURES)
        if surface is None:return None,'no_grass'
        if surface['normal'][2]<.88:return None,'steep'
        if any(collision.point(1,(x,y,surface['z']+z))==-2 for z in(56,132)):
            return None,'standing_hull_obstruction'
        if region=='valley' and y>=3216-radius:return None,'join_clearance'
        if region=='fields' and y<=3216+radius:return None,'join_clearance'
        lx,ly=x-offset[0],y-offset[1]
        if region=='fields':
            # Use the displayed128-unit path, not the former broad dirt strip.
            # Sample the whole footprint because the path bends with y.
            if any(abs(lx-road_x(ly+d))<128+radius+48 for d in(-radius,0,radius)):
                return None,'main_road'
            if abs(ly-river_y)<550+radius:return None,'river'
            if max(abs(lx-stable[0]),abs(ly-stable[1]))<800+radius:return None,'stable'
            if max(abs(lx-ruins[0]),abs(ly-ruins[1]))<1050+radius:return None,'ruins'
            if math.hypot(lx+4600,ly-5000)<400+radius:return None,'camp'
            for building in village['buildings']:
                cx,cy=building['center'];hx,hy=building['half_size']
                if abs(lx-cx)<hx+radius+72 and abs(ly-cy)<hy+radius+72:return None,'building'
                if abs(ly-cy)<radius+80 and abs(lx-cx)<hx+radius+200:return None,'door_approach'
            if any(distance_to_segment(lx,ly,a,b)<radius+64 for a,b in routes):
                return None,'resident_route'
            if math.hypot(lx+3900,ly+7300)<radius+150:return None,'well'
            # Keep the two village access paths mown and readable.
            if -4400-radius<lx<-3360+radius and -8360-radius<ly<-6320+radius:
                return None,'village_path'
            if -3360-radius<lx<-650+radius and -7700-radius<ly<-7150+radius:
                return None,'village_path'
        if any(math.hypot(x-cx,y-cy)<radius+clear for cx,cy,clear in protect):return None,'actor_spawn'
        if any(math.hypot(x-cx,y-cy)<radius+clear for cx,cy,clear in tree_centers):return None,'tree_trunk'
        cell=(math.floor(x/256),math.floor(y/256))
        if any(math.hypot(x-p['origin'][0],y-p['origin'][1])<radius*1.2
               for dx in(-1,0,1)for dy in(-1,0,1)for p in spatial.get((cell[0]+dx,cell[1]+dy),())):
            return None,'patch_spacing'
        nx,ny,nz=surface['normal'];pitch=math.atan(-nx/nz);roll=math.atan(-ny/nz*math.cos(pitch))
        residuals=[]
        for root in roots:
            rx,ry,rz=transform_root(root,pitch,roll)
            at=index.at(x+rx,y+ry,TEXTURES)
            top=index.at(x+rx,y+ry,max_z=None if at is None else at['z']+64)
            if at is None or top is None or top['z']>at['z']+.1:return None,'edge_or_overhang'
            if collision.point(0,(x+rx,y+ry,at['z']+32))==-2:
                return None,'root_hull_obstruction'
            if abs(at['z']-surface['z'])>radius*.65:return None,'terrace'
            if any(abs(lx+rx-road_x(ly+ry+d))<128+48 for d in(-8,0,8)) and region=='fields':
                return None,'road_root'
            residuals.append(surface['z']+rz-at['z'])
        embed=max(residuals)+.65
        errors=[r-embed for r in residuals]
        if min(errors)<-10.5:return None,'crease_burial'
        p={'kind':'grass','region':region,'model':MODEL,'origin':[round(x,3),round(y,3),round(surface['z']-embed,4)],
           'radius':radius,'height':24,'terrain_ground_z':surface['z'],'base_embed_units':embed,
           'pitch':round(math.degrees(pitch),6),'yaw':0,'roll':round(math.degrees(roll),6),
           'root_height_range':[min(errors),max(errors)],'surface_face':surface['face']}
        return p,None
    sector_reports=[]
    for region,goal,bounds,sector_size in [('fields',field_goal,(-10200+offset[0],3400,10200+offset[0],22600),1000),
                                          ('valley',valley_goal,(-3900,-3900,3800,3216),640)]:
        xmin,ymin,xmax,ymax=bounds
        sectors=[(x,y)for y in range(math.floor(ymin/sector_size),math.ceil(ymax/sector_size))
                      for x in range(math.floor(xmin/sector_size),math.ceil(xmax/sector_size))]
        rng.shuffle(sectors);made=0;eligible=set();covered=set()
        # Try all sectors before densifying; narrow eligible slivers may be missed.
        for turn in range(12):
            for ix,iy in sectors:
                if made>=goal:break
                for _ in range(24 if turn==0 else 8):
                    x=rng.uniform(max(xmin,ix*sector_size),min(xmax,(ix+1)*sector_size))
                    y=rng.uniform(max(ymin,iy*sector_size),min(ymax,(iy+1)*sector_size))
                    p,reason=fit(x,y,region)
                    if p is None:rejected[region+':'+reason]+=1;continue
                    eligible.add((ix,iy));covered.add((ix,iy))
                    p['sector']=[ix,iy];placements.append(p);spatial[(math.floor(x/256),math.floor(y/256))].append(p)
                    made+=1;break
            if made>=goal:break
        if made!=goal:raise RuntimeError(f'{region} groundcover budget not fulfilled: {made}/{goal}')
        counts=collections.Counter(tuple(p['sector'])for p in placements if p['region']==region)
        sector_reports.append({'region':region,'goal':goal,'made':made,'sector_size':sector_size,
                               'occupied_sectors':len(counts),'counts':[{ 'sector':list(k),'patches':v}for k,v in sorted(counts.items())]})
    for i,p in enumerate(placements):
        kept.append(Entity([['classname','env_model'],['model',MODEL],
                            ['origin',' '.join(f'{v:.4f}'for v in p['origin'])],
                            ['angles',f"{p['pitch']:.6f} 0 {p['roll']:.6f}"],
                            ['sequence','0'],['framerate','0'],['dmg','0'],['rendermode','0'],
                            ['renderamt','255'],['scale','1'],['skin','0'],['body','0'],
                            ['targetname',f'meadow_polish_grass_{i:04d}'],
                            ['msr_region','daragoth' if p['region']=='valley' else 'daragoth_plains']]))
    if len(kept)>1900:raise ValueError('Final map exceeds reserved entity budget')
    # Append a replacement entity lump. All other lump bytes stay untouched.
    output=bytearray(data);output.extend(b'\0'*(-len(output)%4))
    ent_at=len(output);ents=format_entities(kept);output.extend(ents)
    struct.pack_into('<2i',output,4,ent_at,len(ents))
    before=lump_hashes(data);after=lump_hashes(output)
    if any(before[str(i)]!=after[str(i)]for i in range(1,15)):raise ValueError('Non-entity lump changed')
    if sha(base)!=expected_sha:raise ValueError('Base changed during meadow pass')
    target=out/'daragoth_meadow_polish.bsp'
    if target.resolve()==base.resolve() or out.resolve().is_relative_to(Path('C:/MSR').resolve()):
        raise ValueError('Use a private output separate from the base and installed game')
    out.mkdir(parents=True,exist_ok=True);target.write_bytes(output)
    report={'base_path':str(base.resolve()),'base_sha256':expected_sha,'sha256':sha(target),'output':str(target.resolve()),
            'grass_model_path':str(model.resolve()),'grass_model_sha256':sha(model),'model_runtime_path':MODEL,
            'removed_grass':removed,'field_grass':field_goal,'valley_grass':valley_goal,'total_entities':len(kept),
            'network_entity_limit':2047,'nominal_entity_reserve':2047-len(kept),'static_entity_cap':1900,
            'all_non_entity_lumps_identical':True,'non_entity_lump_hashes':{k:v for k,v in before.items()if k!='0'},
            'source_report_sha256':sha(source_report),'merge_report_sha256':sha(merge_report),
            'sectors':sector_reports,'candidate_rejections':dict(rejected),
            'roots_per_patch':len(roots),'root_height_range':[min(p['root_height_range'][0]for p in placements),max(p['root_height_range'][1]for p in placements)],
            'placements':placements,'scope':'Static non-solid grass; all world and submodel geometry, hulls, lighting, PVS, textures and non-grass entities preserved byte-for-byte.'}
    for region,texture in [('fields','DPGRASS'),('valley','medgrass2_ewoks')]:
        report[region+'_coverage']=coverage_survey(index,[p for p in placements if p['region']==region],
                                                 spacing=128,texture_names=(texture,),min_normal_z=.88)
    (out/'whole-map-meadow-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k]for k in('sha256','removed_grass','field_grass','valley_grass','total_entities','nominal_entity_reserve','root_height_range')},indent=2))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',type=Path,required=True);parser.add_argument('--expected-sha',required=True)
    parser.add_argument('--source-report',type=Path,required=True);parser.add_argument('--merge-report',type=Path,required=True)
    parser.add_argument('--model',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--field-grass',type=int,default=840);parser.add_argument('--valley-grass',type=int,default=80)
    args=parser.parse_args()
    build(args.base,args.source_report,args.merge_report,args.model,args.out,args.expected_sha,args.field_grass,args.valley_grass)
