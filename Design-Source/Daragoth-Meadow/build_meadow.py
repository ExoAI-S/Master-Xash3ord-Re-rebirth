"""Original greener meadow art pass for the private continuous Daragoth map.

Retains the audited join, original spawn pool, bridge and riding stable.
The original Daragoth textures are not copied: only a numeric color reference
informs our own procedural grass palette. The first plains generator and all
previous compiled candidates remain available unchanged.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import math
from pathlib import Path
import random
import sys

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from village import add_village,window_texture,TOWN
from grass_texture import grass_texture
REPO=ROOT.parents[1]
spec=importlib.util.spec_from_file_location('continuous_join',ROOT.parent/'Daragoth-Expanded/build_expanded.py')
join=importlib.util.module_from_spec(spec);spec.loader.exec_module(join)


def meadow_height(scope,x,y):
    """Broad grassy knolls, smooth river banks and a forgiving riding corridor."""
    z=520+190*math.sin(x/2400)*math.cos(y/3600)
    z+=145*math.cos(y/3100+x/4900)+85*math.sin((x+y)/4200)
    for cx,cy,amplitude,radius in [(-6200,-4600,390,2400),(5600,-3100,340,2300),
            (-5900,2500,420,2600),(5400,4700,400,2600),(8800,7900,240,2400)]:
        z+=amplitude*math.exp(-((x-cx)**2+(y-cy)**2)/radius**2)
    river=math.exp(-((y-scope['RIVER_Y'])/2200)**2)
    z=scope['mix'](z,160,river)
    distance=abs(x-scope['road_x'](y))
    road=1-scope['smoothstep']((distance-430)/2200)
    road*=scope['smoothstep']((abs(y-scope['RIVER_Y'])-700)/550)
    z=scope['mix'](z,384+32*math.sin(y/4200),road)
    for cx,cy,level,inner,outer in [(*scope['STABLE'],416,1050,2400),
            (*scope['RUINS'],480,900,2200)]:
        dist=max(abs(x-cx),abs(y-cy))
        z=scope['mix'](z,level,1-scope['smoothstep']((dist-inner)/(outer-inner)))
    village_distance=max(abs(x-TOWN[0]),abs(y-TOWN[1]))
    z=scope['mix'](z,432,1-scope['smoothstep']((village_distance-1700)/600))
    if 650<abs(y-scope['RIVER_Y'])<1550:
        weight=1-scope['smoothstep']((abs(x)-450)/500)
        weight*=scope['smoothstep']((abs(y-scope['RIVER_Y'])-650)/250)
        z=scope['mix'](z,400,weight)
    if y<=-9400:return 384
    if y<-8200:
        weight=scope['smoothstep']((y+9400)/1200)
        z=scope['mix'](384,z,weight)
    return round(z/4)*4


def meadow_scenery(scope,entities,world,triangles,spawns):
    """Clustered groves/groundcover, with dense grass patches outside the road."""
    rng=random.Random(20260930);placed=[];trees=[]
    village=add_village(scope,entities,world)
    models={'oak':('plains_oak.mdl',277,480),'birch':('plains_birch.mdl',112,430),
        'pine':('plains_pine.mdl',169,520),'bush':('plains_bush.mdl',56,64),
        'rocks':('plains_rocks.mdl',57,54),'grass':('meadow_grass_patch.mdl',150,42)}
    ground=lambda x,y:scope['ground_at'](x,y,triangles)
    def allowed(x,y,radius,kind):
        if not(-11350+radius<x<11350-radius and -9340+radius<y<9340-radius):return False
        lane=1050 if kind in ('oak','birch','pine') else scope['road_width'](y)+120+radius
        if abs(x-scope['road_x'](y))<lane:return False
        if abs(y-scope['RIVER_Y'])<550+radius:return False
        stable_clear=1100 if kind in ('oak','birch','pine') else 780
        if max(abs(x-scope['STABLE'][0]),abs(y-scope['STABLE'][1]))<stable_clear+radius:return False
        if max(abs(x-scope['RUINS'][0]),abs(y-scope['RUINS'][1]))<1020+radius:return False
        if -5550-radius<x<-2600+radius and -9070-radius<y<-5630+radius:return False
        if math.hypot(x+4600,y-5000)<390+radius:return False
        if any(max(abs(x-cx),abs(y-cy))<490+radius for cx,cy in [(-3500,-7700),(-3500,-6800)]):return False
        if any(math.hypot(x-s['origin'][0],y-s['origin'][1])<240+radius for s in spawns):return False
        if ground(x,y)<240:return False
        return all(math.hypot(x-p['origin'][0],y-p['origin'][1])>(radius+p['radius'])*.65
            for p in placed if (p['kind']==kind or kind in ('oak','birch','pine') and p['kind'] in ('oak','birch','pine')))
    def place(kind,x,y):
        model,radius,height=models[kind];x=round(x);y=round(y)
        if not allowed(x,y,radius,kind):return False
        gz=ground(x,y);pitch=roll=0;yaw=rng.randrange(360)
        if kind=='grass':
            # The whole patch lies on one local slope plane. Refuse creases
            # that would leave distant clump roots floating off the surface.
            dx=(ground(x+64,y)-ground(x-64,y))/128
            dy=(ground(x,y+64)-ground(x,y-64))/128
            error=max(abs(ground(x+ox,y+oy)-(gz+dx*ox+dy*oy))
                for ox,oy in [(radius,0),(-radius,0),(0,radius),(0,-radius),
                    (106,106),(-106,106),(106,-106),(-106,-106)])
            if error>8:return False
            yaw=0;pitch=math.degrees(math.atan(dx));roll=math.degrees(math.atan(dy*math.cos(math.radians(pitch))))
        embed=2 if kind in ('grass','bush') else 3
        record={'kind':kind,'model':'models/plains/'+model,'origin':[x,y,round(gz-embed,3)],
            'terrain_ground_z':round(gz,3),'base_embed_units':embed,'yaw':yaw,'pitch':round(pitch,5),
            'roll':round(roll,5),'radius':radius,'height':height}
        placed.append(record)
        entities.append(scope['entity']({'classname':'env_model','origin':scope['origin'](x,y,gz-embed),
            'angles':f'{pitch:.5f} {yaw} {roll:.5f}','model':record['model'],'sequence':'0',
            'framerate':'0' if kind in ('rocks','grass') else '1','dmg':'0','rendermode':'0',
            'renderamt':'255','scale':'1','skin':'0','body':'0'}))
        if kind in ('oak','birch','pine'):
            trees.append((x,y));trunk=12 if kind=='birch' else 16
            world.append(scope['box']((x-trunk,y-trunk,gz-11),(x+trunk,y+trunk,gz+207),'CLIP'))
        return True
    anchors=[(-3200,-8650,14),(-4950,-5100,20),(5200,-5300,17),(6650,-2700,15),
        (-5700,300,15),(4500,3100,18),(-7350,6750,17),(7800,8200,14),
        (-5600,5300,12),(-9000,-2400,12),(-3300,-3600,10),(3500,7200,10)]
    for cx,cy,count in anchors:
        made=0
        for _ in range(count*35):
            if made>=count:break
            kind=rng.choices(('oak','birch','pine'),(6,3,1))[0]
            made+=int(place(kind,cx+rng.gauss(0,720),cy+rng.gauss(0,680)))
    for kind,goal,spread in [('bush',165,700),('rocks',65,1100),('grass',340,1600)]:
        made=0
        for _ in range(goal*60):
            if made>=goal:break
            if kind=='grass' and rng.random()<.5:
                y=rng.uniform(-9200,9200)
                x=scope['road_x'](y)+rng.choice((-1,1))*rng.uniform(760,3200)
            elif trees and rng.random()<.75:
                cx,cy=rng.choice(trees);angle=rng.random()*math.tau;dist=rng.uniform(160,spread)
                x=cx+math.cos(angle)*dist;y=cy+math.sin(angle)*dist
            else:x=rng.uniform(-11000,11000);y=rng.uniform(-9200,9200)
            made+=int(place(kind,x,y))
        if made!=goal:raise RuntimeError(f'Groundcover budget not fulfilled: {kind} {made}/{goal}')
    counts={kind:sum(p['kind']==kind for p in placed) for kind in models}
    if len(placed)>770:raise RuntimeError('Meadow scenery exceeds the preview entity budget')
    return {'counts':counts,'entities':len(placed),'tree_collision_trunks':len(trees),
        'road_clear_radius_trees':1050,'road_clear_radius_groundcover':'road half-width +120 + prop radius',
        'spawn_clear_radius':240,'models_original':True,'grass_clumps_per_patch':12,
        'grass_patch_slope_aligned':True,'grass_patch_max_surface_deviation':8,
        'wind_idle_framerate':1,'ground_sampling':'barycentric emitted-triangle surface', 'placements':placed,'village':village}


def variant(maps):
    source=REPO/'Design-Source/Daragoth-Plains/build_daragoth_plains.py'
    scope={'__file__':str(source),'__name__':'daragoth_meadow_variant'}
    code=source.read_text(encoding='utf8').replace('WIDTH, LENGTH = 24000, 20000','WIDTH, LENGTH = 24000, 21280')
    code=code.replace('+[700,1100,1400,1800,2200,2500,2900]',
        '+[-10000,-9400,-8200,700,1100,1400,1800,2200,2500,2900]')
    # Recolor our own procedural palette; retain independently generated pixels.
    code=code.replace('"grass":((83,105,43),(123,115,62))','"grass":((19,62,0),(104,87,8))')
    code=code.replace('"rock":((111,117,114),(128,121,107))','"rock":((57,58,35),(100,91,57))')
    code=code.replace("'_light':'255 236 209 170','_diffuse_light':'145 176 206 85'",
        "'_light':'255 255 128 50'")
    code=code.replace("'angles':'0 125 0'","'angles':'210 60 0'").replace("'pitch':'-55',",'')
    code=code.replace('for cx,cy in ((-3500,-7700),(-3500,-6800)):', 'for cx,cy in ():')
    code=code.replace('p=[x,-7450,464]','p=[x,-7450,height(x,-7450)+48]')
    code=code.replace('top=\'DPDIRT\' if road else \'DPGRASS\'',
        "road=road or (-4400<(x1+x2+X1+X2)/4<-3360 and -8360<(ys[j]+ys[j+1])/2<-6320) or (-3360<(x1+x2+X1+X2)/4<-650 and -7700<(ys[j]+ys[j+1])/2<-7150)\n            top='DPDIRT' if road else 'DPGRASS'")
    code=code.replace('"DPLEAF":"leaf","SKY":"sky"','"DPLEAF":"leaf","DPWINDOW":"window","SKY":"sky"')
    code=code.replace('sheet_w,sheet_h=1280,512','sheet_w,sheet_h=1280,768')
    if "'_light':'255 255 128 50'" not in code or '"grass":((19,62,0),(104,87,8))' not in code:
        raise ValueError('Base generator layout changed; explicit palette/light adaptation requires review')
    exec(compile(code,str(source),'exec'),scope)
    original_texture=scope['texture_data']
    scope['texture_data']=lambda name,kind:window_texture() if kind=='window' else grass_texture() if kind=='grass' else original_texture(name,kind)
    # Fine, irregular grain avoids the former large repeating diagonal bands.
    original_prism=scope['prism']
    def meadow_prism(a,b,c,bottom=scope['BOTTOM'],texture='DPROCK',top='DPGRASS'):
        if top!='DPGRASS':return original_prism(a,b,c,bottom,texture,top)
        vertices=[a,b,c,(a[0],a[1],bottom),(b[0],b[1],bottom),(c[0],c[1],bottom)]
        return scope['brush'](vertices,[(0,1,2),(3,5,4),(0,3,4),(1,4,5),(2,5,3)],texture,top,scale=.5)
    scope['prism']=meadow_prism
    original_box=scope['box']
    def shell(a,b,*args,**kwargs):
        remap={-10064:-10704,-10000:-10640,10000:10640,10064:10704}
        return original_box((a[0],remap.get(a[1],a[1]),a[2]),(b[0],remap.get(b[1],b[1]),b[2]),*args,**kwargs)
    scope['height']=lambda x,y:meadow_height(scope,x,y)
    scope['box']=shell
    scope['add_scenery']=lambda *args:meadow_scenery(scope,*args)
    maps.mkdir(parents=True,exist_ok=True)
    (maps.parent/'liblist.gam').write_text('game "MSR isolated meadow compiler"\n',encoding='ascii')
    scope['build_map'](maps,600)
    y=10000;x=scope['road_x'](y);z=scope['height'](x,y)
    gate=scope['entity']({'classname':'msarea_transition','targetname':'deralia','destmap':'deralia',
        'destname':'The City of Deralia'},[original_box((x-160,y,z),(x+160,y+48,z+160),'AAATRIGGER')])
    with (maps/'daragoth_plains.map').open('a',encoding='ascii',newline='\n')as stream:stream.write(gate)
    return {'frozen_generator_sha256':join.sha(source),'meadow_generator_sha256':join.sha(Path(__file__)),
        'flat_entry_height':384,'flat_entry_y_max':-9400,'blend_y_max':-8200,'shell_south_y':-10640,
        'far_deralia_gate_local':[x,y,z],'terrain_spacing':600,'original_numeric_color_reference':[60.9,73.2,4.0],
        'original_bitmap_pixels_copied':False,'meadow_grass_palette_endpoints':[[19,62,0],[104,87,8]],
        'environment_matches_original':{'angles':'210 60 0','_light':'255 255 128 50'}}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original',type=Path,required=True);parser.add_argument('--ent',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--tools',type=Path,required=True)
    parser.add_argument('--reuse-compiled',action='store_true');args=parser.parse_args()
    if args.out.resolve().is_relative_to(Path('C:/MSR').resolve()):parser.error('Use a private scratch output')
    join.build(args.original.resolve(),args.ent.resolve(),args.out.resolve(),args.tools.resolve(),args.reuse_compiled,
        caps=True,sky_close=True,stone_facing=True,variant_builder=variant,output_suffix='_meadow',omit_legacy_skyline=True)


if __name__=='__main__':main()
