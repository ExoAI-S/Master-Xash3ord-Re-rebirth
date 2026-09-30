"""Original small timber village and harmless walking-resident routes."""
import math
import random

TOWN=(-3900,-7300)
BUILDINGS=[('inn',-4820,-7900,480,336,'east'),('workshop',-4820,-6820,384,320,'east'),
    ('cottage',-3050,-8260,288,272,'west'),('cottage',-3050,-6360,288,272,'west'),
    ('bakery',-4820,-6020,288,256,'east'),('farmhouse',-4950,-8740,256,256,'east')]
ROUTES={
    'innkeeper':[(-4130,-7990),(-3650,-7990),(-3650,-6640),(-4130,-6640)],
    'smith':[(-4150,-6910),(-3550,-6910),(-3550,-7090),(-4150,-7090)],
    'farmer':[(-3980,-8370),(-3460,-8370),(-3460,-7820),(-3980,-7820)],
    'traveler':[(-3570,-6600),(-4040,-6600),(-4040,-7120),(-3570,-7120)]}


def add_village(scope,entities,world):
    box=scope['box'];brush=scope['brush'];height=scope['height'];buildings=[]
    for role,cx,cy,hx,hy,facing in BUILDINGS:
        z=432;floor=z+8;walltop=floor+256
        world.append(box((cx-hx-8,cy-hy-8,z-16),(cx+hx+8,cy+hy+8,floor),'DPROCK',1))
        if role=='farmhouse':
            # The south-entry blend lowers this plot. Two 12-unit rises keep
            # its open doorway within the engine's 18-unit step allowance.
            edge=cx+hx
            world.append(box((edge+24,cy-112,392),(edge+72,cy+112,416),'DPROCK',1))
            world.append(box((edge,cy-112,392),(edge+24,cy+112,428),'DPROCK',1))
        # Back and side walls, with a real doorway and lintel at the front.
        back=cx-hx if facing=='east' else cx+hx-24
        world.append(box((back,cy-hy,floor),(back+24,cy+hy,walltop),'DPMASON',1))
        for y in (cy-hy,cy+hy-24):
            world.append(box((cx-hx,y,floor),(cx+hx,y+24,walltop),'DPMASON',1))
        front=cx+hx-24 if facing=='east' else cx-hx
        for ya,yb in ((cy-hy,cy-96),(cy+96,cy+hy)):
            world.append(box((front,ya,floor),(front+24,yb,walltop),'DPMASON',1))
        world.append(box((front,cy-96,floor+176),(front+24,cy+96,walltop),'DPWOOD',1))
        # Half-timber posts and broad eaves make distinct finished silhouettes.
        for x in (cx-hx-4,cx+hx-12):
            for y in (cy-hy-4,cy+hy-12):
                world.append(box((x,y,floor),(x+16,y+16,walltop+12),'DPWOOD',1))
        for y in (cy-hy-4,cy+hy-8):
            world.append(box((cx-hx-12,y,walltop-20),(cx+hx+12,y+12,walltop+12),'DPWOOD',1))
        roof=[(cx-hx-28,cy-hy-28,walltop),(cx+hx+28,cy-hy-28,walltop),
            (cx,cy-hy-28,walltop+180),(cx-hx-28,cy+hy+28,walltop),
            (cx+hx+28,cy+hy+28,walltop),(cx,cy+hy+28,walltop+180)]
        world.append(brush(roof,[(0,1,2),(3,5,4),(0,3,4),(1,4,5),(2,5,3)],'DPTHATCH',scale=1))
        # A chimney and lit leaded windows, using our own generated material.
        world.append(box((cx-96,cy+hy-130,walltop-32),(cx-16,cy+hy-50,walltop+240),'DPMASON',1))
        for wy in (cy-hy+112,cy+hy-112):
            wx=cx+hx if facing=='east' else cx-hx-6
            world.append(box((wx,wy-54,floor+76),(wx+6,wy+54,floor+166),'DPWINDOW',.5))
            for ya in (wy-62,wy+54):
                world.append(box((wx-2,ya,floor+68),(wx+10,ya+8,floor+174),'DPWOOD',1))
            for zz in (floor+68,floor+166):
                world.append(box((wx-2,wy-62,zz),(wx+10,wy+62,zz+8),'DPWOOD',1))
        # Interior has headroom, benches and warm point light; doors stay open.
        world.append(box((cx-150,cy+hy-92,floor),(cx+150,cy+hy-56,floor+36),'DPWOOD',1))
        entities.append(scope['entity']({'classname':'light','origin':scope['origin'](cx,cy,floor+180),
            '_light':'255 189 100 140'}))
        buildings.append({'role':role,'center':[cx,cy],'half_size':[hx,hy],'floor_z':floor,
            'door_facing':facing,'door_clear_width':192,'door_clear_height':176,'roof_top_z':walltop+180})
    # Well in the square; a low solid ring and roof, with clear pedestrian lanes.
    cx,cy=TOWN;z=432
    for a,b in [((cx-80,cy-80,z),(cx+80,cy-60,z+48)),
            ((cx-80,cy+60,z),(cx+80,cy+80,z+48)),
            ((cx-80,cy-60,z),(cx-60,cy+60,z+48)),
            ((cx+60,cy-60,z),(cx+80,cy+60,z+48))]:world.append(box(a,b,'DPROCK',1))
    world.append(box((cx-60,cy-60,z+6),(cx+60,cy+60,z+10),'DPWINDOW',1))
    for x in (cx-104,cx+88):world.append(box((x,cy-8,z),(x+16,cy+8,z+168),'DPWOOD',1))
    world.append(box((cx-132,cy-100,z+168),(cx+132,cy+100,z+188),'DPTHATCH',1))
    # Small kitchen garden and boundary fencing, rather than more empty sheds.
    for y in (-8530,-8430):
        world.append(box((-5270,y,432),(-4710,y+56,440),'DPDIRT',1))
    for x in (-5320,-4680):
        for y in range(-8620,-8260,120):world.append(box((x,y,432),(x+12,y+12,516),'DPWOOD',1))
        world.append(box((x,-8620,480),(x+12,-8260,492),'DPWOOD',1))
    actors=[]
    for role,route in ROUTES.items():
        x,y=route[0]
        entities.append(scope['entity']({'classname':'ms_npc','scriptfile':'daragoth_meadow/'+role,
            'targetname':'meadow_'+role,'origin':scope['origin'](x,y,440),'angles':'0 90 0',
            'lives':'0','spawnchance':'100','delaylow':'1','delayhigh':'1'}))
        actors.append({'role':role,'route':[[x,y,432]for x,y in route],'spawn':[route[0][0],route[0][1],440]})
    return {'name':'Greenhollow','center':[*TOWN,432],'buildings':buildings,'residents':actors,
        'walker_routes_authored':True,'original_geometry':True,'shops_inventory_not_yet_implemented':True}


def window_texture():
    width=height=256;rng=random.Random(73001)
    palette=bytes(c for i in range(256) for c in (
        max(0,min(255,round(15+i*.62))),max(0,min(255,round(24+i*.46))),max(0,min(255,round(27+i*.17)))))
    pixels=bytearray()
    for y in range(height):
        for x in range(width):
            frame=x<12 or x>=244 or y<12 or y>=244 or abs(x-128)<5 or abs(y-128)<5
            lead=(x+y)%64<3 or (x-y)%64<3
            value=25 if frame else 32 if lead else round(160+35*math.sin(y/256*math.pi)+rng.uniform(-8,8))
            pixels.append(value)
    return width,height,pixels,palette
