"""Generate an original, editable MSR riding-plains prototype and WAD3 textures.

Uses only the Python standard library. Geometry is generated as convex Valve
220 brushes, so every visible terrain triangle has real player collision.
No original BSP is altered or decompiled. All textures are generated here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WIDTH, LENGTH = 24000, 20000
RIVER_Y = 1800
BOTTOM, SKY_TOP = -256, 4096
STABLE = (-1700, -7900)
RUINS = (6500, 6200)


def mix(a, b, weight):
    return a * (1 - weight) + b * weight


def smoothstep(value):
    value = max(0.0, min(1.0, value))
    return value * value * (3 - 2 * value)


def road_x(y):
    return 250 * math.sin(y / 3800)


def road_width(y):
    return 390 + 48 * math.sin(y / 1510) + 22 * math.sin(y / 430)


def row_x(x, y, inner=750):
    # Three near-center columns follow the road instead of painting unrelated
    # checkerboard triangles. Both road edges remain continuous from row to row.
    if x == 0:
        return round(road_x(y))
    if x == -round(inner):
        return round(road_x(y) - road_width(y))
    if x == round(inner):
        return round(road_x(y) + road_width(y))
    return x


def height(x, y):
    """Low-frequency rolling fields, with flattened stable and ruin precincts."""
    z = 384 + 104 * math.sin(x / 3200) * math.cos(y / 4300)
    z += 64 * math.sin((x + y) / 4800) + 40 * math.cos(y / 2100)
    # Broad river valley; grass banks meet a shallow water ribbon below.
    river = math.exp(-((y - RIVER_Y) / 1100) ** 2)
    z = mix(z, 160, river)
    # Roads stay broad and mild, but the river remains below the bridge.
    road = math.exp(-((x - road_x(y)) / 900) ** 4)
    road_z = 384 + 24 * math.sin(y / 4200)
    if abs(y - RIVER_Y) > 1100:
        z = mix(z, road_z, road * .75)
    # Flat paddock and archaeology camp, fading smoothly into the fields.
    for cx, cy, level, inner, outer in (
        (*STABLE, 416, 1050, 2200), (*RUINS, 480, 900, 2000)
    ):
        dist = max(abs(x - cx), abs(y - cy))
        weight = 1 - smoothstep((dist - inner) / (outer - inner))
        z = mix(z, level, weight)
    # Level bridge approaches, with a real open valley beneath the deck.
    if 650 < abs(y - RIVER_Y) < 1550:
        dist = abs(x)
        weight = (1 - smoothstep((dist - 450) / 500))
        weight *= smoothstep((abs(y - RIVER_Y) - 650) / 250)
        z = mix(z, 400, weight)
    return round(z / 8) * 8


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def sub(a, b):
    return tuple(a[i] - b[i] for i in range(3))


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def number(v):
    return str(int(v)) if v == int(v) else f"{v:.6f}".rstrip("0").rstrip(".")


def point(v):
    return "( " + " ".join(number(x) for x in v) + " )"


def face(points, centroid, texture, scale=4):
    """Valve brush winding is clockwise from outside (compiler reverses cross)."""
    a, b, c = points
    normal = cross(sub(b, a), sub(c, a))
    if dot(normal, sub(centroid, a)) < 0:
        b, c = c, b
        normal = tuple(-v for v in normal)
    axis = max(range(3), key=lambda i: abs(normal[i]))
    u, v = ((0, 1, 0), (0, 0, -1)) if axis == 0 else (
        ((1, 0, 0), (0, 0, -1)) if axis == 1 else ((1, 0, 0), (0, -1, 0)))
    return f"{point(a)} {point(b)} {point(c)} {texture} [ {' '.join(map(str,u))} 0 ] [ {' '.join(map(str,v))} 0 ] 0 {scale} {scale}\n"


def brush(vertices, faces, texture, top_texture=None, scale=4):
    centroid = tuple(sum(v[i] for v in vertices)/len(vertices) for i in range(3))
    lines = ["{\n"]
    for i, indices in enumerate(faces):
        tex = top_texture if top_texture and i == 0 else texture
        lines.append(face([vertices[j] for j in indices], centroid, tex, scale))
    return "".join(lines) + "}\n"


def prism(a, b, c, bottom=BOTTOM, texture="DPROCK", top="DPGRASS"):
    vertices = [a,b,c, (a[0],a[1],bottom),(b[0],b[1],bottom),(c[0],c[1],bottom)]
    return brush(vertices, [(0,1,2),(3,5,4),(0,3,4),(1,4,5),(2,5,3)], texture, top, scale=2)


def box(lo, hi, texture, scale=4):
    x,y,z=lo; X,Y,Z=hi
    vertices=[(x,y,z),(X,y,z),(X,Y,z),(x,Y,z),(x,y,Z),(X,y,Z),(X,Y,Z),(x,Y,Z)]
    return brush(vertices,[(4,5,6),(0,2,1),(0,1,5),(1,2,6),(2,3,7),(3,0,4)],texture,scale=scale)


def ramp(x1,x2,y1,y2,z1,z2,texture="DPWOOD"):
    vertices=[(x1,y1,z1-32),(x2,y1,z1-32),(x2,y2,z2-32),(x1,y2,z2-32),
              (x1,y1,z1),(x2,y1,z1),(x2,y2,z2),(x1,y2,z2)]
    return brush(vertices,[(4,5,6),(0,2,1),(0,1,5),(1,2,6),(2,3,7),(3,0,4)],texture,scale=2)


def pyramid(cx,cy,z,radius,h,texture):
    vertices=[(cx-radius,cy-radius,z),(cx+radius,cy-radius,z),
              (cx+radius,cy+radius,z),(cx-radius,cy+radius,z),(cx,cy,z+h)]
    return brush(vertices,[(0,1,4),(1,2,4),(2,3,4),(3,0,4),(0,3,2)],texture)


def entity(values, brushes=()):
    return "{\n"+"".join(f'"{k}" "{v}"\n' for k,v in values.items())+"".join(brushes)+"}\n"


def origin(x,y,z):
    return " ".join(number(v) for v in (x,y,z))


def ground_at(x, y, triangles):
    """Interpolate the actual brush surface; models must not float above hills."""
    for a,b,c in triangles:
        if not (min(a[0],b[0],c[0])-0.01 <= x <= max(a[0],b[0],c[0])+0.01 and
                min(a[1],b[1],c[1])-0.01 <= y <= max(a[1],b[1],c[1])+0.01):
            continue
        det=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
        u=((b[1]-c[1])*(x-c[0])+(c[0]-b[0])*(y-c[1]))/det
        v=((c[1]-a[1])*(x-c[0])+(a[0]-c[0])*(y-c[1]))/det
        if min(u,v,1-u-v) >= -0.00001:
            return u*a[2]+v*b[2]+(1-u-v)*c[2]
    raise ValueError(f'No terrain below decoration at {x}, {y}')


def texture_data(name, kind):
    rng=random.Random(7103+sum(ord(c) for c in name)); w=h=256
    colors={
        "grass":((83,105,43),(123,115,62)), "dirt":((105,79,47),(143,113,73)),
        "rock":((111,117,114),(128,121,107)), "masonry":((103,113,109),(132,125,104)),
        "wood":((102,68,37),(133,104,62)), "thatch":((112,98,51),(164,143,80)),
        "bank":((109,106,67),(105,114,56)), "water":((47,97,103),(60,111,112)),
        "leaf":((38,71,36),(71,89,39)), "sky":((117,158,185),(117,158,185))}
    low,high=colors[kind]
    palette=bytes(max(0,min(255,round(mix(low[c],high[c],hue/15)*(0.55+shade/15*0.77))))
                  for hue in range(16) for shade in range(16) for c in range(3))
    pixels=bytearray()
    for y in range(h):
        for x in range(w):
            # Every term is periodic, including low-frequency color patches,
            # so global terrain UVs meet without cell/triangle color seams.
            xx=x*math.tau/w; yy=y*math.tau/h
            macro=math.sin(xx+math.sin(yy))*math.cos(2*yy-xx)+0.45*math.sin(3*xx+2*yy)
            hue=round(7.5+macro*3.5+rng.uniform(-1.5,1.5))
            light=8+macro*1.2+rng.uniform(-1.8,1.8)
            if kind in ('wood','thatch'):
                grain=math.sin(xx*31+math.sin(yy*3)*2)+0.35*math.sin(xx*71+yy*2)
                light+=grain*1.5
                if kind=='wood' and x%64 < 2:light-=4.5
                if kind=='thatch':light+=math.sin(xx*51+yy*4)
            elif kind=='masonry':
                row=y//64; seam_y=y%64<3; seam_x=(x+(row%2)*64)%128<3
                light-=4.0 if seam_y or seam_x else 0
                light+=0.8*math.sin(xx*7+yy*9)
            elif kind=='water':light+=math.sin(3*xx+5*yy)*1.2
            pixels.append(max(0,min(15,hue))*16+max(0,min(15,round(light))))
    if kind=='grass':
        for _ in range(7200):
            x=rng.randrange(w);y=rng.randrange(h);length=rng.randrange(2,7)
            bend=rng.choice((-1,0,1));shade=rng.choice((-2,2,3))
            for i in range(length):
                index=((y+i)%h)*w+(x+bend*i//3)%w
                old=pixels[index];pixels[index]=(old//16)*16+max(0,min(15,old%16+shade))
    elif kind in ('dirt','rock','masonry'):
        for _ in range(2400):
            x=rng.randrange(w);y=rng.randrange(h);old=pixels[y*w+x]
            pixels[y*w+x]=(old//16)*16+max(0,min(15,old%16+rng.choice((-3,-2,2))))
    return w,h,pixels,palette


def miptex(name, kind):
    w,h,pixels,palette=texture_data(name,kind)
    levels=[bytes(pixels)]; size=w
    for _ in range(3):
        src=levels[-1]; nxt=size//2
        layer=[]
        for y in range(nxt):
            for x in range(nxt):
                group=[src[(2*y+dy)*size+2*x+dx] for dy in (0,1) for dx in (0,1)]
                layer.append(round(sum(p//16 for p in group)/4)*16+round(sum(p%16 for p in group)/4))
        levels.append(bytes(layer))
        size=nxt
    offsets=[];offset=40
    for layer in levels:offsets.append(offset);offset+=len(layer)
    return struct.pack("<16sII4I",name.encode().ljust(16,b"\0"),w,h,*offsets)+b"".join(levels)+struct.pack("<H",256)+palette+b"\0\0"


def write_wad(path):
    textures={"DPGRASS":"grass","DPDIRT":"dirt","DPROCK":"rock","DPWOOD":"wood",
              "DPMASON":"masonry","DPTHATCH":"thatch","DPBANK":"bank",
              "!DPWATER":"water","DPLEAF":"leaf","SKY":"sky","CLIP":"rock"}
    payload=bytearray();directory=bytearray()
    for name,kind in textures.items():
        blob=miptex(name,kind);offset=12+len(payload);payload.extend(blob)
        directory.extend(struct.pack("<iiiBBBB16s",offset,len(blob),len(blob),0x43,0,0,0,name.encode().ljust(16,b"\0")))
    path.write_bytes(struct.pack("<4sii",b"WAD3",len(textures),12+len(payload))+payload+directory)
    # Standalone PNG contact sheet for inspecting the original bitmap material
    # output without running the game. The first row is grass/dirt/rock/wood/stone.
    sheet_w,sheet_h=1280,512;rows=[bytearray(sheet_w*3) for _ in range(sheet_h)]
    for n,(name,kind) in enumerate((pair for pair in textures.items() if pair[0]!='CLIP')):
        w,h,pixels,palette=texture_data(name,kind);ox=(n%5)*w;oy=(n//5)*h
        for y in range(h):
            for x in range(w):
                index=pixels[y*w+x]*3;at=(ox+x)*3
                rows[oy+y][at:at+3]=palette[index:index+3]
    raw=b''.join(b'\0'+row for row in rows)
    def chunk(tag,data):
        return struct.pack('>I',len(data))+tag+data+struct.pack('>I',zlib.crc32(tag+data)&0xffffffff)
    png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',sheet_w,sheet_h,8,2,0,0,0))
    png+=chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b'')
    path.with_name('daragoth_plains-texture-preview.png').write_bytes(png)


def triangle_slope(triangle):
    n=cross(sub(triangle[1],triangle[0]),sub(triangle[2],triangle[0]))
    return math.degrees(math.atan2(math.hypot(n[0],n[1]),abs(n[2])))


def add_scenery(entities, world, triangles, spawns):
    """Sparse copses and ground cover, kept away from riding and arrival lanes."""
    rng=random.Random(40391);placed=[];tree_positions=[]
    # Final radial footprints, including diagonal crown/leaf-card extents.
    models={'oak':('plains_oak.mdl',277,480),'birch':('plains_birch.mdl',112,430),
            'pine':('plains_pine.mdl',169,520),'bush':('plains_bush.mdl',56,64),
            'rocks':('plains_rocks.mdl',57,54),'grass':('plains_grass.mdl',25,30)}
    def allowed(x,y,radius,kind):
        if not (-11400+radius < x < 11400-radius and -9400+radius < y < 9400-radius):return False
        if abs(x-road_x(y)) < (1050 if kind in ('oak','birch','pine') else 620):return False
        if abs(y-RIVER_Y)<500+radius:return False
        stable_clear=1080 if kind in ('oak','birch','pine') else 760
        if max(abs(x-STABLE[0]),abs(y-STABLE[1])) < stable_clear+radius:return False
        if max(abs(x-RUINS[0]),abs(y-RUINS[1])) < 980+radius:return False
        if math.hypot(x+4600,y-5000) < 360+radius:return False
        for cx,cy in ((-3500,-7700),(-3500,-6800)):
            if max(abs(x-cx),abs(y-cy))<460+radius:return False
        if any(math.hypot(x-s['origin'][0],y-s['origin'][1]) < 240+radius for s in spawns):return False
        z=ground_at(x,y,triangles)
        return z>=240 and all(math.hypot(x-p['origin'][0],y-p['origin'][1])>
                             (radius+p['radius'])*0.6 for p in placed if p['kind']==kind)
    def place(kind,x,y):
        model,radius,h=models[kind]
        x=round(x);y=round(y)
        if not allowed(x,y,radius,kind):return False
        ground=ground_at(x,y,triangles)
        embed=1 if kind in ('grass','bush') else 3
        z=ground-embed # bury the base slightly against slope seams
        yaw=rng.randrange(360)
        record={'kind':kind,'model':'models/plains/'+model,'origin':[x,y,round(z,3)],
                'terrain_ground_z':round(ground,3),'base_embed_units':embed,
                'yaw':yaw,'radius':radius,'height':h}
        placed.append(record)
        entities.append(entity({'classname':'env_model','origin':origin(x,y,z),'angles':f'0 {yaw} 0',
                                'model':record['model'],'sequence':'0','framerate':'0' if kind=='rocks' else '1','dmg':'0',
                                'rendermode':'0','renderamt':'255','scale':'1','skin':'0','body':'0'}))
        if kind in ('oak','birch','pine'):
            tree_positions.append((x,y))
            # Narrow collision trunks only. No brush foliage or obstructing
            # crown hulls; grass, shrubs and rock dressing are all non-solid.
            trunk=12 if kind=='birch' else 16
            world.append(box((x-trunk,y-trunk,z-8),(x+trunk,y+trunk,z+210),'CLIP'))
        return True
    anchors=[(-3200,-8650,10),(-4950,-5100,13),(5200,-5300,12),(6650,-2700,9),
             (-5700,300,12),(4500,3100,12),(-7350,6750,12),(7800,8200,9),
             (-5600,5300,8),(-9000,-2400,7)]
    for cx,cy,count in anchors:
        made=0
        for attempt in range(count*24):
            if made>=count:break
            kind=rng.choices(('oak','birch','pine'),(5,3,2))[0]
            x=cx+rng.gauss(0,650);y=cy+rng.gauss(0,550)
            made+=int(place(kind,x,y))
    for kind,goal,offset in (('bush',125,540),('grass',165,850),('rocks',65,850)):
        made=0
        for attempt in range(goal*30):
            if made>=goal:break
            if tree_positions and rng.random()<0.65:
                cx,cy=rng.choice(tree_positions);angle=rng.random()*math.tau
                dist=rng.uniform(120,offset);x=cx+math.cos(angle)*dist;y=cy+math.sin(angle)*dist
            else:
                x=rng.randrange(-11000,11000);y=rng.randrange(-9200,9200)
            made+=int(place(kind,x,y))
    counts={kind:sum(p['kind']==kind for p in placed) for kind in models}
    assert len(placed)<=480
    return {'counts':counts,'entities':len(placed),'tree_collision_trunks':len(tree_positions),
            'road_clear_radius_trees':1050,'road_clear_radius_groundcover':620,
            'spawn_clear_radius':240,'models_original':True,'wind_idle_framerate':1,
            'ground_sampling':'barycentric interpolation of emitted brush triangles','placements':placed}


def build_map(out, spacing):
    nx=math.ceil(WIDTH/spacing);ny=math.ceil(LENGTH/spacing)
    nx+=nx%2 # retain one center and two edge columns at any supported density
    xs=[round(-WIDTH/2+i*WIDTH/nx) for i in range(nx+1)]
    ys=sorted(set([round(-LENGTH/2+i*LENGTH/ny) for i in range(ny+1)]+[700,1100,1400,1800,2200,2500,2900]))
    # Omit nearly coincident rows so tiny brushes cannot appear at the river.
    for value in (700,1100,1400,1800,2200,2500,2900):
        ys=[y for y in ys if y==value or abs(y-value)>=160]
    world=[];triangles=[]
    for j in range(len(ys)-1):
        for i in range(len(xs)-1):
            x1=row_x(xs[i],ys[j],WIDTH/nx);x2=row_x(xs[i+1],ys[j],WIDTH/nx)
            X1=row_x(xs[i],ys[j+1],WIDTH/nx);X2=row_x(xs[i+1],ys[j+1],WIDTH/nx)
            a=(x1,ys[j],height(x1,ys[j]));b=(x2,ys[j],height(x2,ys[j]))
            c=(X2,ys[j+1],height(X2,ys[j+1]));d=(X1,ys[j+1],height(X1,ys[j+1]))
            road=i in (nx//2-1,nx//2)
            top='DPDIRT' if road else 'DPGRASS'
            for t in ((a,b,c),(a,c,d)):
                world.append(prism(*t,top=top));triangles.append(t)
    # Closed sky shell keeps the map sealed. The ground prisms seal the bottom.
    world.extend([
        box((-12064,-10064,BOTTOM),(12064,-10000,SKY_TOP),"SKY"),
        box((-12064,10000,BOTTOM),(12064,10064,SKY_TOP),"SKY"),
        box((-12064,-10000,BOTTOM),(-12000,10000,SKY_TOP),"SKY"),
        box((12000,-10000,BOTTOM),(12064,10000,SKY_TOP),"SKY"),
        box((-12064,-10064,SKY_TOP),(12064,10064,SKY_TOP+64),"SKY"),
        box((-12064,-10064,BOTTOM-64),(12064,10064,BOTTOM),"DPROCK")])
    # Bridge with gentle wooden approach ramps and a 768-unit-wide deck.
    world.extend([ramp(-384,384,700,1100,400,512),box((-384,1100,480),(384,2500,512),"DPWOOD",2),
                  ramp(-384,384,2500,2900,512,400)])
    for x in (-400,384):
        world.append(box((x,1100,512),(x+16,2500,584),"DPWOOD",2))
    for y in (1200,1750,2300):
        for x in (-336,304):
            world.append(box((x,y,160),(x+32,y+48,480),"DPROCK"))
    # Original open timber stable: high canopy, paddock, hitching rail and camp.
    sx,sy=STABLE
    world.append(box((sx-640,sy-320,416),(sx+640,sy+320,432),"DPWOOD",2))
    for x in (sx-608,sx+576):
        for y in (sy-288,sy+256):
            world.append(box((x,y,432),(x+32,y+32,768),"DPWOOD",2))
    world.append(box((sx-704,sy-384,768),(sx+704,sy+384,800),"DPTHATCH",2))
    # Shallow roof fascia adds a finished timber frame without changing the
    # canopy underside, stable floor, horse position or riding clearance.
    for y in (sy-384,sy+368):
        world.append(box((sx-704,y,764),(sx+704,y+16,816),'DPWOOD',1))
    # Fence behind horses; stable opens toward the main road.
    world.append(box((sx-700,sy-500,480),(sx+700,sy-484,544),"DPWOOD",2))
    for x in range(sx-700,sx+701,350):
        world.append(box((x,sy-516,416),(x+24,sy-468,584),"DPWOOD",2))
    for cx,cy in ((-3500,-7700),(-3500,-6800)):
        z=height(cx,cy)
        # Simple stone shelter with an open doorway facing the road.
        world.extend([box((cx-320,cy-256,z),(cx+320,cy-224,z+256),"DPMASON",1),
                      box((cx-320,cy-224,z),(cx-288,cy+256,z+256),"DPMASON",1),
                      box((cx+288,cy-224,z),(cx+320,cy+256,z+256),"DPMASON",1),
                      box((cx-352,cy-288,z+256),(cx+352,cy+288,z+288),"DPWOOD",2)])
    # Ruins: a broken outer enclosure and tall stone piers, visibly new geometry.
    rx,ry=RUINS
    world.append(box((rx-780,ry-620,480),(rx+780,ry+620,496),"DPROCK"))
    for x in (rx-760,rx+720):
        for y in (ry-580,ry-60,ry+480):
            world.append(box((x,y,496),(x+40,y+100,704),"DPROCK"))
    for x in (rx-700,rx+440):
        world.append(box((x,ry-620,496),(x+260,ry-572,656),"DPROCK"))
    world.append(box((rx-760,ry+572,496),(rx+760,ry+620,624),"DPROCK"))
    for x in (rx-320,rx+256):
        world.append(box((x,ry+128,496),(x+64,ry+192,1104),"DPROCK"))
    world.append(box((rx-352,ry+96,1104),(rx+352,ry+224,1168),"DPROCK"))
    # Beacon stone as an easily visible navigation landmark.
    lx,ly=-4600,5000;lz=height(lx,ly)
    world.extend([box((lx-176,ly-176,lz),(lx+176,ly+176,lz+64),"DPROCK"),
                  box((lx-64,ly-64,lz+64),(lx+64,ly+64,lz+704),"DPROCK"),
                  pyramid(lx,ly,lz+704,64,128,"DPROCK")])
    wad=out.parent/'daragoth_plains.wad'
    values={'classname':'worldspawn','mapversion':'220','_generator':'MSR original plains generator 1',
            'wad':str(wad).replace('\\','/'),'skyname':'grnplsnt','MaxRange':'30000',
            'maptitle':'Daragoth Plains - Riding Prototype','mapdesc':'Original expanded plains development map',
            'zhlt_texturestep':'64','zhlt_maxextent':'64'}
    entities=[] # worldspawn is serialized after scenery adds collision trunks
    entities.append(entity({'classname':'light_environment','origin':'0 0 3000','angles':'0 125 0',
                            'pitch':'-55','_light':'255 236 209 170','_diffuse_light':'145 176 206 85'}))
    entities.append(entity({'classname':'info_player_start','origin':'-1700 -7788 480','angles':'0 270 0'}))
    # Conventional script-driven game master, so standalone maps initialize
    # weather and travel callbacks before the first character connects.
    entities.append(entity({'classname':'ms_npc','scriptfile':'game_master','origin':'0 0 3000',
                            'targetname':'plains_game_master','angles':'0 0 0'}))
    spawn_checks=[]
    for classname,x,y,z in [('ms_player_begin',-1700,-7788,480),('ms_player_spec',-1000,-7100,544)]:
        angle='0 270 0' if classname=='ms_player_begin' else '0 25 0'
        entities.append(entity({'classname':classname,'origin':origin(x,y,z),'angles':angle}))
        spawn_checks.append({'classname':classname,'origin':[x,y,z]})
    # Unnamed arrivals are available to generic/elite spawn selection, while
    # character creation continues to use the existing ms_player_begin.
    for x in (-2050,-1700,-1350):
        p=[x,-7450,464]
        entities.append(entity({'classname':'ms_player_spawn','origin':origin(*p),'angles':'0 270 0'}))
        spawn_checks.append({'classname':'ms_player_spawn','origin':p})
    groups=[('daragoth01',-450,-8800),('deralia',350,8700),('from_nash',-10400,1000),
            ('mines',9600,4500),('prototype',-1000,-7300)]
    for name,x,y in groups:
        for dx,dy in ((-80,-80),(80,-80),(-80,80),(80,80)):
            px,py=x+dx,y+dy;pz=height(px,py)+48
            entities.append(entity({'classname':'ms_player_spawn','message':name,'origin':origin(px,py,pz),
                                    'angles':'0 90 0'}))
            spawn_checks.append({'classname':'ms_player_spawn','message':name,'origin':[px,py,pz]})
    horse_origin=[sx,sy,432]
    entities.append(entity({'classname':'ms_horse','origin':origin(*horse_origin),'angles':'0 0 0',
                            'targetname':'plains_stable_horse','model':'models/mounts/plains_horse.mdl'}))
    # Water is a contents brush, separate from the terrain collision.
    entities.append(entity({'classname':'func_water','skin':'-3','spawnflags':'0','WaveHeight':'0',
                            'rendermode':'2','renderamt':'120','rendercolor':'62 115 121'},
                           [box((-11980,1420,96),(11980,2180,216),'!DPWATER',4)]))
    scenery=add_scenery(entities,world,triangles,spawn_checks)
    entities.insert(0,entity(values,world))
    map_path=out/'daragoth_plains.map';map_path.write_text(''.join(entities),encoding='ascii',newline='\n')
    write_wad(wad)
    slopes=[triangle_slope(t) for t in triangles]
    maxslope=max(slopes)
    bad_spawns=[s for s in spawn_checks if not (-12000<s['origin'][0]<12000 and -10000<s['origin'][1]<10000)
                or s['origin'][2]-height(*s['origin'][:2])<40]
    if maxslope>30 or bad_spawns:
        raise RuntimeError(f'Invalid terrain or spawn placement: max slope {maxslope:.2f}, bad spawns {bad_spawns}')
    report={'map':'daragoth_plains','prototype':True,'size':[WIDTH,LENGTH],
            'bounds':{'mins':[-12000,-10000,BOTTOM],'maxs':[12000,10000,SKY_TOP]},
            'requested_grid_spacing':spacing,'grid_cells':[len(xs)-1,len(ys)-1],
            'terrain_triangles':len(triangles),'world_brushes':len(world),'entities':len(entities),
            'terrain_height_range':[min(v[2] for t in triangles for v in t),max(v[2] for t in triangles for v in t)],
            'max_terrain_slope_degrees':round(maxslope,3),'bridge_ramp_slope_degrees':round(math.degrees(math.atan2(112,400)),3),
            'spawn_checks':{'checked':len(spawn_checks),'failures':bad_spawns},
            'landmarks':{'stable':[*STABLE,416],'river_center_y':RIVER_Y,'bridge':[0,RIVER_Y,512],
                         'ruins':[*RUINS,480],'beacon':[lx,ly,lz]},
            'horse':{'classname':'ms_horse','origin':horse_origin,'model':'models/mounts/plains_horse.mdl'},
            'terrain_materials':{'continuous_field':'DPGRASS','continuous_road':'DPDIRT','texture_size':[256,256]},
            'scenery':scenery,
            'textures_original':True,'source_sha256':hashlib.sha256(map_path.read_bytes()).hexdigest(),
            'wad_sha256':hashlib.sha256(wad.read_bytes()).hexdigest()}
    (out/'daragoth_plains-source-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    counts=', '.join(f'{count} {kind}' for kind,count in scenery['counts'].items())
    config=f'// Original plains art: {scenery["entities"]} scenery entities ({counts}).\n'
    config+='// Native model wind idle; no PrimeXT auto-grass dependency.\n'
    config+='as_enabled 0\nms_mounts 1\nms_dynamic_events 0\n'
    (out/'daragoth_plains.cfg').write_text(config,encoding='ascii')
    summary={**report,'scenery':{k:v for k,v in scenery.items() if k!='placements'}}
    print(json.dumps(summary,indent=2))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=ROOT/'generated'/'msr'/'maps')
    parser.add_argument('--spacing',type=int,default=768)
    args=parser.parse_args()
    if not 384<=args.spacing<=1536:parser.error('spacing must be 384..1536 units')
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out.parent/'liblist.gam').write_text('game "Daragoth Plains map build"\ngamedir "msr"\n',encoding='ascii')
    build_map(args.out.resolve(),args.spacing)


if __name__=='__main__':main()
