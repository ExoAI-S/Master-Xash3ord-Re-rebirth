"""Original greener meadow art pass for the private continuous Daragoth map.

Retains the audited join, original spawn pool, bridge and riding stable.
Grass remains independently generated from a numeric palette reference. The
road and orchard reuse the user's installed assets in private generated output.
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
from rock_texture import rock_texture
from path_texture import entry_road_width,installed_path_texture,split_road_triangle
from natural_boundary import boundary_height,boundary_row_x,integration_notes
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
    if y<=-9400:z=384
    elif y<-8200:
        weight=scope['smoothstep']((y+9400)/1200)
        z=scope['mix'](384,z,weight)
    return round(boundary_height(x,y,round(z/4)*4)/4)*4


def boundary_triangle(triangle):
    """Only the intended ridge strips may exceed the playable slope limit."""
    return any(abs(x)>=8400 or y>=7040 or y<=-8200 for x,y,_ in triangle)


def meadow_scenery(scope,entities,world,triangles,spawns):
    """Clustered groves/groundcover, with dense grass patches outside the road."""
    rng=random.Random(20260930);placed=[];trees=[]
    village=add_village(scope,entities,world)
    models={'oak':('plains_oak.mdl',277,480),'birch':('plains_birch.mdl',112,430),
        'pine':('plains_pine.mdl',169,520),'bush':('plains_bush.mdl',56,64),
        'rocks':('plains_rocks.mdl',57,54),'grass':('meadow_grass_patch.mdl',170,42)}
    tree_kinds=('oak','birch','pine','apple')
    ground=lambda x,y:scope['ground_at'](x,y,triangles)
    def allowed(x,y,radius,kind):
        if not(-11350+radius<x<11350-radius and -9340+radius<y<9340-radius):return False
        lane=1050 if kind in tree_kinds else scope['road_width'](y)+120+radius
        if abs(x-scope['road_x'](y))<lane:return False
        if abs(y-scope['RIVER_Y'])<550+radius:return False
        stable_clear=1100 if kind in tree_kinds else 780
        if max(abs(x-scope['STABLE'][0]),abs(y-scope['STABLE'][1]))<stable_clear+radius:return False
        if max(abs(x-scope['RUINS'][0]),abs(y-scope['RUINS'][1]))<1020+radius:return False
        if -5550-radius<x<-2600+radius and -9070-radius<y<-5630+radius:return False
        if math.hypot(x+4600,y-5000)<390+radius:return False
        if any(max(abs(x-cx),abs(y-cy))<490+radius for cx,cy in [(-3500,-7700),(-3500,-6800)]):return False
        if any(math.hypot(x-s['origin'][0],y-s['origin'][1])<240+radius for s in spawns):return False
        if ground(x,y)<240:return False
        dx=(ground(x+64,y)-ground(x-64,y))/128
        dy=(ground(x,y+64)-ground(x,y-64))/128
        if math.hypot(dx,dy)>.6:return False
        spacing=.42 if kind=='grass' else .65
        return all(math.hypot(x-p['origin'][0],y-p['origin'][1])>(radius+p['radius'])*spacing
            for p in placed if (p['kind']==kind or kind in tree_kinds and p['kind'] in tree_kinds))
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
                    (120,120),(-120,120),(120,-120),(-120,-120)])
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
        if kind in tree_kinds:
            trees.append((x,y));trunk=5 if kind=='apple' else 12 if kind=='birch' else 16
            world.append(scope['box']((x-trunk,y-trunk,gz-11),(x+trunk,y+trunk,gz+(150 if kind=='apple' else 207)),'CLIP'))
        if kind=='apple':
            # Preserve the original tree/apple alignment while rotating each grove tree.
            for ax,ay,az in [(37,-38,102),(-45,-43,116),(-1,-74,152),(38,38,105),(-52,50,120)]:
                angle=math.radians(yaw)
                px=x+ax*math.cos(angle)-ay*math.sin(angle)
                py=y+ax*math.sin(angle)+ay*math.cos(angle)
                entities.append(scope['entity']({'classname':'env_model','origin':scope['origin'](px,py,gz-embed+az),
                    'angles':f'0 {yaw} 0','model':'models/misc/p_misc.mdl','sequence':'0','framerate':'1',
                    'dmg':'0','rendermode':'4','renderamt':'255','scale':'1','skin':'0','body':'2'}))
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
    for kind,goal,spread in [('bush',165,700),('rocks',65,1100),('grass',760,1150)]:
        made=0
        for _ in range(goal*60):
            if made>=goal:break
            if kind=='grass' and rng.random()<.60:
                y=rng.uniform(-9200,9200)
                x=scope['road_x'](y)+rng.choice((-1,1))*rng.uniform(720,2400)
            elif trees and rng.random()<.75:
                cx,cy=rng.choice(trees);angle=rng.random()*math.tau;dist=rng.uniform(160,spread)
                x=cx+math.cos(angle)*dist;y=cy+math.sin(angle)*dist
            else:x=rng.uniform(-11000,11000);y=rng.uniform(-9200,9200)
            made+=int(place(kind,x,y))
        if made!=goal:raise RuntimeError(f'Groundcover budget not fulfilled: {kind} {made}/{goal}')
    # Add orchards after the frozen meadow pass so existing scenery never shifts.
    models['apple']=('edana_apple_tree.mdl',100,257)
    rng=random.Random(20261001)
    for cx,cy in [(-6100,-8000),(-6000,-6200),(-2600,-5100)]:
        made=0
        for _ in range(500):
            if made==4:break
            made+=int(place('apple',cx+rng.gauss(0,320),cy+rng.gauss(0,320)))
        if made!=4:raise RuntimeError('Could not place the requested orchard safely')
    stablemaster=[-2150,-8100,432]
    entities.append(scope['entity']({'classname':'ms_stablemaster','origin':scope['origin'](*stablemaster),
        'angles':'0 90 0','targetname':'plains_stablemaster'}))
    counts={kind:sum(p['kind']==kind for p in placed) for kind in models}
    if len(placed)>1220:raise RuntimeError('Meadow scenery exceeds the preview entity budget')
    return {'counts':counts,'entities':len(placed),'tree_collision_trunks':len(trees),
        'road_clear_radius_trees':1050,'road_clear_radius_groundcover':'road half-width +120 + prop radius',
        'spawn_clear_radius':240,'models_original':False,'original_authored_models_except':['apple'],
        'apple_tree_source':'installed Edana trunk *151 and its associated crown from *152',
        'apple_fruit_decorative_only':True,'apple_fruit_entities':60,'stablemaster':stablemaster,'grass_clumps_per_patch':36,
        'grass_minimum_patch_separation_units':142.8,'grass_triangles_per_patch':288,
        'grass_patch_slope_aligned':True,'grass_patch_max_surface_deviation':8,
        'wind_idle_framerate':1,'ground_sampling':'barycentric emitted-triangle surface', 'placements':placed,'village':village}


def variant(maps,original):
    source=REPO/'Design-Source/Daragoth-Plains/build_daragoth_plains.py'
    scope={'__file__':str(source),'__name__':'daragoth_meadow_variant'}
    code=source.read_text(encoding='utf8').replace('WIDTH, LENGTH = 24000, 20000','WIDTH, LENGTH = 24000, 21280')
    pinned_rows=[-10000,-9600,-9400,-9000,-8200,700,1100,1400,1800,2200,2500,2900,7040,9560,10000,10640]
    code=code.replace('+[700,1100,1400,1800,2200,2500,2900]',f'+{pinned_rows}')
    code=code.replace('for value in (700,1100,1400,1800,2200,2500,2900):',f'for value in {pinned_rows}:')
    # Recolor our own procedural palette; retain independently generated pixels.
    code=code.replace('"grass":((83,105,43),(123,115,62))','"grass":((19,62,0),(104,87,8))')
    code=code.replace('"rock":((111,117,114),(128,121,107))','"rock":((57,58,35),(100,91,57))')
    code=code.replace("'_light':'255 236 209 170','_diffuse_light':'145 176 206 85'",
        "'_light':'255 255 128 50'")
    code=code.replace("'angles':'0 125 0'","'angles':'210 60 0'").replace("'pitch':'-55',",'')
    code=code.replace('for cx,cy in ((-3500,-7700),(-3500,-6800)):', 'for cx,cy in ():')
    code=code.replace('p=[x,-7450,464]','p=[x,-7450,height(x,-7450)+48]')
    code=code.replace('top=\'DPDIRT\' if road else \'DPGRASS\'',
        "main_road=road\n            road=road or (-4400<(x1+x2+X1+X2)/4<-3360 and -8360<(ys[j]+ys[j+1])/2<-6320) or (-3360<(x1+x2+X1+X2)/4<-650 and -7700<(ys[j]+ys[j+1])/2<-7150)\n            top='DPDIRT' if road else 'DPGRASS'")
    code=code.replace('"DPLEAF":"leaf","SKY":"sky"','"DPLEAF":"leaf","DPWINDOW":"window","DPPATH":"path","SKY":"sky"')
    code=code.replace("'textures_original':True", "'textures_original':False")
    code=code.replace('sheet_w,sheet_h=1280,512','sheet_w,sheet_h=1280,768')
    code=code.replace('world.append(prism(*t,top=top));triangles.append(t)',
        "world.append(prism(*t,top='DPROCK' if boundary_triangle(t) and triangle_slope(t)>40 else top,road_path=main_road));triangles.append(t)")
    code=code.replace('if maxslope>30 or bad_spawns:',
        'interior_slopes=[s for t,s in zip(triangles,slopes) if not boundary_triangle(t)]\n    if maxslope>80 or max(interior_slopes)>30 or bad_spawns:')
    code=code.replace("'max_terrain_slope_degrees':round(maxslope,3),",
        "'max_terrain_slope_degrees':round(maxslope,3),'max_playable_interior_slope_degrees':round(max(interior_slopes),3),'intentional_steep_boundary_triangles':sum(s>30 for t,s in zip(triangles,slopes) if boundary_triangle(t)),")
    code=code.replace("'bounds':{'mins':[-12000,-10000,BOTTOM],'maxs':[12000,10000,SKY_TOP]}",
        "'bounds':{'mins':[-12000,-10640,BOTTOM],'maxs':[12000,10640,SKY_TOP]}")
    if "'_light':'255 255 128 50'" not in code or '"grass":((19,62,0),(104,87,8))' not in code:
        raise ValueError('Base generator layout changed; explicit palette/light adaptation requires review')
    exec(compile(code,str(source),'exec'),scope)
    scope['boundary_triangle']=boundary_triangle
    original_row_x=scope['row_x']
    scope['row_x']=lambda x,y,inner=600:boundary_row_x(x,y,original_row_x(x,y,inner),inner)
    original_texture=scope['texture_data']
    road_texture,road_provenance=installed_path_texture(join.BSP.load(original))
    scope['texture_data']=lambda name,kind:window_texture() if kind=='window' else road_texture if kind=='path' else grass_texture() if kind=='grass' else rock_texture() if kind=='rock' else original_texture(name,kind)
    # Fine, irregular grain avoids the former large repeating diagonal bands.
    original_prism=scope['prism']
    def meadow_prism(a,b,c,bottom=scope['BOTTOM'],texture='DPROCK',top='DPGRASS',road_path=False):
        if road_path:
            center,outer,axes=split_road_triangle((a,b,c),scope['road_x'],lambda y:entry_road_width(y,0))
            sx,sy,shift=axes;brushes=[]
            for triangle in center:
                lines=original_prism(*triangle,bottom,texture,'DPPATH').splitlines(keepends=True)
                coordinates=lines[1].split('DPPATH')[0]
                # After the merge's y translation this is the original [0 -1 0 200].
                lines[1]=f'{coordinates}DPPATH [ {sx:.9f} {sy:.9f} 0 {shift:.9f} ] [ 0 -1 0 -13016 ] 0 1 1\n'
                brushes.append(''.join(lines))
            brushes.extend(meadow_prism(*triangle,bottom,texture,'DPGRASS') for triangle in outer)
            return ''.join(brushes)
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
        'natural_boundary_module_sha256':join.sha(ROOT/'natural_boundary.py'),'natural_boundaries':integration_notes(),
        'original_bitmap_pixels_copied':True,'meadow_grass_palette_endpoints':[[19,62,0],[104,87,8]],
        'entry_path':{'original_exit_world_x':[1400,1656],'width_at_join':256,
            'width_throughout':256,'material':'DPPATH','grass_fringes':True,
            'authored_pixels':False,'installed_asset_private_use':True,
            'original_texture':road_provenance,'final_world_v_axis':[0,-1,0,200]},
        'environment_matches_original':{'angles':'210 60 0','_light':'255 255 128 50'}}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original',type=Path,required=True);parser.add_argument('--ent',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--tools',type=Path,required=True)
    parser.add_argument('--reuse-compiled',action='store_true');args=parser.parse_args()
    if args.out.resolve().is_relative_to(Path('C:/MSR').resolve()):parser.error('Use a private scratch output')
    join.build(args.original.resolve(),args.ent.resolve(),args.out.resolve(),args.tools.resolve(),args.reuse_compiled,
        caps=True,sky_close=True,stone_facing=True,variant_builder=lambda maps:variant(maps,args.original.resolve()),output_suffix='_meadow',omit_legacy_skyline=True)
    preserve_road_mips(args.original.resolve(),args.out.resolve())


def preserve_road_mips(original,out):
    # The procedural WAD writer regenerates lower mips. Restore all four of the
    # installed source material's mip levels, changing only its internal name.
    path=out/'daragoth_expanded_meadow.bsp'
    bsp=join.BSP.load(path)
    source=next(t for t in join.BSP.load(original).textures if t.name.lower()=='deraliaroad_2_0')
    target=next(t for t in bsp.textures if t.name.lower()=='dppath')
    target.raw=b'DPPATH'.ljust(16,b'\0')+source.raw[16:]
    bsp.save(path,bsp30ext=True)
    assert next(t for t in join.BSP.load(path).textures if t.name.lower()=='dppath').raw[16:]==source.raw[16:]
    report_path=out/'continuous-join-meadow-report.json'
    report=json.loads(report_path.read_text())
    report['complete_road_miptex_preserved']=True
    report['complete_road_miptex_sha256']=join.hashlib.sha256(source.raw[16:]).hexdigest()
    report['final_map_sha256']=join.sha(path)
    report['output'].update({'sha256':join.sha(path),'crc32':join.zlib.crc32(path.read_bytes())&0xffffffff,
        'bytes':path.stat().st_size})
    report_path.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
