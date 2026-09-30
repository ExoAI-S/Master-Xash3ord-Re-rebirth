"""Compile and validate the generated plains using a PrimeXT tools directory."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import struct
import subprocess
import zlib
from pathlib import Path

import build_daragoth_plains as source

ROOT=Path(__file__).resolve().parent


def load_collision(path):
    data=path.read_bytes()
    if struct.unpack_from('<i',data)[0]!=30:
        raise RuntimeError('Expected PrimeXT BSP30ext')
    lumps=[struct.unpack_from('<ii',data,4+i*8) for i in range(15)]
    def lump(i):
        offset,length=lumps[i];return data[offset:offset+length]
    planes=list(struct.iter_unpack('<4fi',lump(1)))
    nodes=list(struct.iter_unpack('<i2h6h2H',lump(5)))
    leaves=[struct.unpack_from('<i',lump(10),i)[0] for i in range(0,len(lump(10)),28)]
    raw=lump(9)
    # The compiler emits 16-bit clipnodes for this low-density prototype.
    if len(raw)//8>=32767:
        clips=list(struct.iter_unpack('<iii',raw))
    else:
        clips=list(struct.iter_unpack('<ihh',raw))
    model=struct.unpack_from('<9f4i3i',lump(14))
    entities=[]
    for block in re.findall(r'\{([^{}]*)\}',lump(0).decode('latin1')):
        entities.append(dict(re.findall(r'"([^"]*)"\s+"([^"]*)"',block)))
    return data,lumps,planes,clips,model,entities,nodes,leaves


def contents(planes,clips,head,point):
    node=head
    while node>=0:
        plane_id,front,back=clips[node];plane=planes[plane_id]
        dist=sum(point[i]*plane[i] for i in range(3))-plane[3]
        node=front if dist>=0 else back
    return node


def point_contents(planes,nodes,leaves,head,point):
    while head>=0:
        node=nodes[head];plane=planes[node[0]]
        dist=sum(point[i]*plane[i] for i in range(3))-plane[3]
        head=node[1] if dist>=0 else node[2]
    return leaves[-1-head]


def standing_ground(planes,clips,head,x,y,approximate_z):
    """Find the compiled hull's walkable surface near the anticipated floor.

    Sampling the analytic height alone falsely treats uphill movement as a
    collision on the coarse brush mesh. The standing hull already includes
    the player's vertical extents; scan below an unobstructed point above it.
    """
    top=approximate_z+96
    if contents(planes,clips,head,(x,y,top))!=-1:return None
    last_empty=top
    for step in range(1,33):
        z=top-step*8
        at=contents(planes,clips,head,(x,y,z))
        if at==-2:
            result=(x,y,last_empty+12)
            # An obstacle much taller than the nearby terrain is not a floor.
            if abs(result[2]-approximate_z)>96:return None
            return result if contents(planes,clips,head,result)==-1 else None
        if at!=-1:return None
        last_empty=z
    return None


def validate(path):
    data,lumps,planes,clips,world,entities,nodes,leaves=load_collision(path)
    failures=[];checked=0;spawn_space_checks=0;road_checks=0
    setup={'character_creation':any(e.get('classname')=='ms_player_begin' for e in entities),
           'spectator_spawn':any(e.get('classname')=='ms_player_spec' for e in entities),
           'generic_spawns':sum(e.get('classname')=='ms_player_spawn' and not e.get('message') for e in entities),
           'game_master':sum(e.get('classname')=='ms_npc' and e.get('scriptfile')=='game_master' for e in entities)}
    if not setup['character_creation'] or not setup['spectator_spawn'] or setup['generic_spawns'] < 1 or setup['game_master'] != 1:
        failures.append({'invalid_gameplay_setup':setup})
    for entity in entities:
        if entity.get('classname') not in ('ms_player_begin','ms_player_spec','ms_player_spawn'):
            continue
        p=tuple(float(v) for v in entity['origin'].split());checked+=1
        if contents(planes,clips,world[10],p)!=-1:
            failures.append({'spawn':entity,'contents':contents(planes,clips,world[10],p)})
        for angle in range(0,360,45):
            r=math.radians(angle);x=p[0]+128*math.cos(r);y=p[1]+128*math.sin(r)
            near=standing_ground(planes,clips,world[10],x,y,p[2])
            spawn_space_checks+=1
            if near is None:
                failures.append({'spawn_safe_space':[x,y],'spawn':entity})
    # The three lines fit well inside the 768-wide bridge, including the
    # shifted road center. Probe the compiled standing-player hull rather than
    # assuming non-solid scenery or the source exclusion rules worked.
    for y in range(-9400,9401,200):
        for lane in (-192,0,192):
            x=source.road_x(y)+lane
            level=source.height(x,y)
            if 700<=y<1100:level=400+(y-700)*112/400
            elif 1100<=y<=2500:level=512
            elif 2500<y<=2900:level=512-(y-2500)*112/400
            p=standing_ground(planes,clips,world[10],x,y,level+48);road_checks+=1
            if p is None:
                failures.append({'riding_lane_blocked_or_no_ground':[x,y,level+48]})
    # Every sparse field probe must have solid ground below it, including far
    # corners outside the old GoldSrc +-4096 range. This tests compiled hulls.
    ground_probes=0
    for x in range(-11500,11501,500):
        for y in range(-9500,9501,500):
            # Source surface is piecewise planar between height samples; the
            # analytical height can differ slightly. Probe safely below both.
            p=(x,y,source.height(x,y)-100);ground_probes+=1
            if contents(planes,clips,world[10],p)!=-2:
                failures.append({'missing_ground':p})
    scenery_checks=0;max_ground_error=0
    source_report=json.loads(path.with_name('daragoth_plains-source-report.json').read_text())
    for prop in source_report.get('scenery',{}).get('placements',[]):
        x,y,_=prop['origin'];expected=prop['terrain_ground_z'];scenery_checks+=1
        lo=expected-16;hi=expected+16
        if point_contents(planes,nodes,leaves,world[9],(x,y,lo))!=-2 or point_contents(planes,nodes,leaves,world[9],(x,y,hi))!=-1:
            failures.append({'decoration_floor_not_bracketed':prop});continue
        for _ in range(22):
            mid=(lo+hi)/2
            if point_contents(planes,nodes,leaves,world[9],(x,y,mid))==-2:lo=mid
            else:hi=mid
        error=abs((lo+hi)/2-expected);max_ground_error=max(error,max_ground_error)
        if error>2:failures.append({'decoration_floor_error':round(error,5),'prop':prop})
    report={'bsp':path.name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),
            'crc32':zlib.crc32(data)&0xffffffff,
            'world_mins':list(world[:3]),'world_maxs':list(world[3:6]),
            'counts':{'planes':len(planes),'vertices':lumps[3][1]//12,'nodes':lumps[5][1]//24,
                      'faces':lumps[7][1]//20,'clipnodes':len(clips),'models':lumps[14][1]//64,
                      'entities':len(entities)},
            'standing_hull_spawn_checks':checked,'spawn_safe_space_hull_checks':spawn_space_checks,
            'riding_corridor_hull_checks':road_checks,'compiled_ground_probes':ground_probes,
            'scenery_surface_checks':scenery_checks,'max_scenery_ground_error_units':round(max_ground_error,5),
            'gameplay_setup':setup,'failures':failures}
    if failures:
        raise RuntimeError(json.dumps(report,indent=2))
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tools',type=Path,required=True)
    parser.add_argument('--maps',type=Path,default=ROOT/'generated'/'msr'/'maps')
    parser.add_argument('--threads',type=int,default=1,
                        help='Default single-thread build preserves deterministic CSG/clip planes')
    args=parser.parse_args();map_path=(args.maps/'daragoth_plains.map').resolve()
    commands=[('pxcsg',['-threads',str(args.threads),'-nowadtextures',str(map_path)]),
              ('pxbsp',['-threads',str(args.threads),str(map_path.with_suffix('.bsp'))]),
              ('pxvis',['-fast','-threads',str(args.threads),str(map_path.with_suffix('.bsp'))]),
              ('pxrad',['-threads',str(args.threads),'-bounce','0','-fastsky','-nomodelshadow','-chop','256',str(map_path.with_suffix('.bsp'))])]
    logs=[]
    # PrimeXT's filesystem treats *.pak as Quake PAKs, but MSR's script library
    # has its own format. Keep it out of compiler auto-mounting, then restore it
    # even when a tool fails. It is never an input to BSP compilation.
    script_library=args.maps.parent/'scripts.pak'
    hidden_library=script_library.with_name('scripts.pak.compiler-disabled')
    if hidden_library.exists():raise RuntimeError('Another compilation has temporarily hidden scripts.pak')
    hide=script_library.exists()
    if hide:script_library.rename(hidden_library)
    try:
        for tool,arguments in commands:
            result=subprocess.run([str(args.tools/(tool+'.exe')),*arguments],cwd=ROOT,text=True,capture_output=True)
            logs.append({'tool':tool,'arguments':arguments,'exit_code':result.returncode,'output':result.stdout+result.stderr})
            print(tool,result.returncode)
            # Some errors still return success; reject missing inputs and leaks.
            if result.returncode or 'failed to load' in logs[-1]['output'] or "couldn't init game directory" in logs[-1]['output'] or 'LEAK' in logs[-1]['output'] or 'Error:' in logs[-1]['output']:
                (args.maps/'daragoth_plains-compile-log.json').write_text(json.dumps(logs,indent=2)+'\n',encoding='utf8')
                raise RuntimeError(logs[-1]['output'])
    finally:
        if hide:hidden_library.rename(script_library)
    report=validate(map_path.with_suffix('.bsp'))
    (args.maps/'daragoth_plains-compile-log.json').write_text(json.dumps(logs,indent=2)+'\n',encoding='utf8')
    (args.maps/'daragoth_plains-compiled-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
