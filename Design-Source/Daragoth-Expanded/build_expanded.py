"""Private continuous Daragoth BSP prototype; all original inputs are read-only.

Generate a separately compiled southern-entry variant of the original plains,
crop both render worlds and join all four collision trees at one axial plane.
Outputs belong in an isolated scratch directory, never a live game directory.
"""
from __future__ import annotations
import argparse, copy, hashlib, json, math, struct, subprocess, sys, zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
sys.path.insert(0, str(REPO / 'Packaging-Work/BigWorld/tools'))
from bsp30 import BSP, Entity, Face, TexInfo, decompress_vis, compress_vis, hull_point_contents, parse_entities
from merge_world import RegionSource, WorldBuilder, face_extents, fmt_vec, process_entities, tree_order_errors
from build_edana_world import region_entities

SEAM = 3216.0
LOCAL_SEAM = -10000.0
OFFSET = (1528.0 - 250.0 * math.sin(LOCAL_SEAM / 3800.0), SEAM - LOCAL_SEAM, 2688.0)
ORIGINAL_BSP_SHA256 = '88c34a065388e89d9f41a3f0f5f2ba0ddfe3a6c6ca1e02fc0ee0e3c167dfc9f6'
ORIGINAL_ENT_SHA256 = 'a93169fd13279314ab96973f1364e05bd0e4b0e4b13aa4b7ac7851b6d6b8a057'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def dump(path, value): path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf8')

def variant(maps):
    """Execute a transient generator adaptation; the frozen source stays untouched."""
    source = REPO / 'Design-Source/Daragoth-Plains/build_daragoth_plains.py'
    scope = {'__file__': str(source), '__name__': 'daragoth_entry_variant'}
    code = source.read_text(encoding='utf8')
    code = code.replace('WIDTH, LENGTH = 24000, 20000', 'WIDTH, LENGTH = 24000, 21280')
    code = code.replace('+[700,1100,1400,1800,2200,2500,2900]', '+[-10000,-9400,-8200,700,1100,1400,1800,2200,2500,2900]')
    exec(compile(code, str(source), 'exec'), scope)
    original_height = scope['height']
    original_box = scope['box']
    def entry_height(x,y):
        if y <= -9400: return 384
        if y >= -8200: return original_height(x,y)
        t=(y+9400)/1200; t=t*t*(3-2*t)
        return round((384*(1-t)+original_height(x,y)*t)/8)*8
    def shell_box(a,b,*args,**kwargs):
        # The historical generator shell is hardcoded at +/-10000.
        remap={-10064:-10704,-10000:-10640,10000:10640,10064:10704}
        a=(a[0],remap.get(a[1],a[1]),a[2]); b=(b[0],remap.get(b[1],b[1]),b[2])
        return original_box(a,b,*args,**kwargs)
    scope['height']=entry_height; scope['box']=shell_box
    maps.mkdir(parents=True,exist_ok=True)
    (maps.parent/'liblist.gam').write_text('game "MSR isolated map compiler"\n',encoding='ascii')
    scope['build_map'](maps,800)
    # Move the authentic Deralia exit to the far end. Arrival label is retained
    # from the original trigger; no same-BSP teleports connect these regions.
    y=10000; x=scope['road_x'](y); z=entry_height(x,y)
    gate=scope['entity']({'classname':'msarea_transition','targetname':'deralia',
        'destmap':'deralia','destname':'The City of Deralia'},
        [original_box((x-160,y,z),(x+160,y+48,z+160),'AAATRIGGER')])
    with (maps/'daragoth_plains.map').open('a',encoding='ascii',newline='\n') as f:f.write(gate)
    return {'frozen_generator_sha256':sha(source),'flat_entry_height':384,
            'flat_entry_y_max':-9400,'blend_y_max':-8200,'shell_south_y':-10640,
            'far_deralia_gate_local':[x,y,z],'terrain_spacing':800}

def compile_variant(maps,tools):
    path=(maps/'daragoth_plains.map').resolve()
    cmds=[('pxcsg',['-threads','1','-nowadtextures',str(path)]),
          ('pxbsp',['-threads','1',str(path.with_suffix('.bsp'))]),
          ('pxvis',['-fast','-threads','1',str(path.with_suffix('.bsp'))]),
          ('pxrad',['-threads','1','-bounce','0','-fastsky','-nomodelshadow','-chop','256',str(path.with_suffix('.bsp'))])]
    logs=[]
    for tool,args in cmds:
        r=subprocess.run([str(tools/(tool+'.exe')),*args],cwd=ROOT,text=True,capture_output=True)
        logs.append({'tool':tool,'exit_code':r.returncode,'output':r.stdout+r.stderr})
        dump(maps/'compile-log.json',logs)
        print(tool,r.returncode,flush=True)
        if r.returncode or any(t in logs[-1]['output'] for t in ['failed to load',"couldn't init game directory",'LEAK','Error:']):
            raise RuntimeError(logs[-1]['output'])

def sample_size(bsp,face):
    index=(bsp.texinfo[face.texinfo].flags>>16)&65535
    raw=bsp.extra_lumps.get(1,b'')
    if index!=65535 and index*22+22<=len(raw):return struct.unpack_from('<H',raw,index*22+16)[0]
    return 16

def polygon(bsp,face):
    out=[]
    for se in bsp.surfedges[face.firstedge:face.firstedge+face.numedges]:
        out.append(bsp.vertexes[bsp.edges[abs(se)][0 if se>=0 else 1]])
    return out

def clip_polygon(points,cut,keep_below):
    out=[]
    def inside(p):return p[1]<=cut+1e-5 if keep_below else p[1]>=cut-1e-5
    for a,b in zip(points,points[1:]+points[:1]):
        aa,bb=inside(a),inside(b)
        if aa:out.append(a)
        if aa!=bb:
            t=(cut-a[1])/(b[1]-a[1]);p=tuple(a[k]+t*(b[k]-a[k]) for k in range(3))
            out.append((p[0],cut,p[2]))
    cleaned=[]
    for p in out:
        if not cleaned or sum((p[k]-cleaned[-1][k])**2 for k in range(3))>1e-10:cleaned.append(p)
    if len(cleaned)>1 and sum((cleaned[0][k]-cleaned[-1][k])**2 for k in range(3))<1e-10:cleaned.pop()
    return cleaned

def repack_light(src,face,old_ext,new_ext,blob):
    ow=old_ext[0][1]-old_ext[0][0]+1;oh=old_ext[1][1]-old_ext[1][0]+1
    start=len(blob)
    for slot in range(sum(s!=255 for s in face.styles)):
        for t in range(new_ext[1][0],new_ext[1][1]+1):
            for s in range(new_ext[0][0],new_ext[0][1]+1):
                ss=min(max(s-old_ext[0][0],0),ow-1);tt=min(max(t-old_ext[1][0],0),oh-1)
                at=face.lightofs+(slot*ow*oh+tt*ow+ss)*3
                rgb=src[at:at+3]
                if len(rgb)!=3:raise ValueError('Lightmap source bounds invalid')
                blob.extend(rgb)
    return start

def crop(bsp,cut,below):
    """Remove outside world faces and clip straddlers; preserve lightmap grids."""
    w=bsp.models[0];world_range=range(w.firstface,w.firstface+w.numfaces)
    old_faces=bsp.faces;new=[];mapping={};lighting=bytearray(bsp.lighting)
    report={'kept':0,'clipped':0,'removed':0,'repacked_lightmaps':0}
    for i,f in enumerate(old_faces):
        nf=copy.copy(f)
        if i in world_range:
            pts=polygon(bsp,f);clipped=clip_polygon(pts,cut,below)
            if len(clipped)<3:
                mapping[i]=None;report['removed']+=1;continue
            if pts!=clipped:
                report['clipped']+=1; nf.firstedge=len(bsp.surfedges);nf.numedges=len(clipped)
                ids=[]
                for p in clipped:ids.append(len(bsp.vertexes));bsp.vertexes.append(p)
                for a,b in zip(ids,ids[1:]+ids[:1]):
                    bsp.surfedges.append(len(bsp.edges));bsp.edges.append((a,b))
                if f.lightofs>=0 and not bsp.texinfo[f.texinfo].flags&1:
                    size=sample_size(bsp,f);oldext=face_extents(bsp,f,size);newext=face_extents(bsp,nf,size)
                    nf.lightofs=repack_light(bsp.lighting,f,oldext,newext,lighting)
                    report['repacked_lightmaps']+=1
            else:report['kept']+=1
        mapping[i]=len(new);new.append(nf)
    for item in [*bsp.models,*bsp.nodes]:
        indices=[mapping[x] for x in range(item.firstface,item.firstface+item.numfaces) if mapping[x] is not None]
        item.firstface=indices[0] if indices else 0;item.numfaces=len(indices)
    old_marks=bsp.marksurfaces;bsp.marksurfaces=[]
    for leaf in bsp.leafs:
        indices=[mapping[x] for x in old_marks[leaf.firstmarksurface:leaf.firstmarksurface+leaf.nummarksurfaces] if mapping[x] is not None]
        leaf.firstmarksurface=len(bsp.marksurfaces);leaf.nummarksurfaces=len(indices);bsp.marksurfaces.extend(indices)
    bsp.faces=new;bsp.lighting=bytes(lighting)
    v=list(w.maxs if below else w.mins);v[1]=cut
    if below:w.maxs=tuple(v)
    else:w.mins=tuple(v)
    return report

def repair_shifted_lighting(builder,world):
    blob=bytearray(world.lighting);count=0
    for r,reg in enumerate(builder.regions):
        if reg.offset==(0.,0.,0.):continue
        for fi,f in enumerate(reg.bsp.faces):
            if f.lightofs<0 or reg.bsp.texinfo[f.texinfo].flags&1:continue
            of=world.faces[builder.face_map[r,fi]];size=sample_size(reg.bsp,f)
            old=face_extents(reg.bsp,f,size);new=face_extents(world,of,size)
            if old!=new:of.lightofs=repack_light(reg.bsp.lighting,f,old,new,blob);count+=1
    world.lighting=bytes(blob);return count

def cross_vis(builder,world,reciprocal=False):
    original,plains=builder.regions;old=original.bsp
    portal=[]
    for i in range(1,original.visleafs+1):
        l=old.leafs[i]
        if l.maxs[0]>=1150 and l.mins[0]<=1950 and l.maxs[1]>=2700 and l.mins[1]<=SEAM and l.maxs[2]>=3072 and l.mins[2]<=3700:portal.append(i)
    if not portal:raise ValueError('No original north road portal leaves')
    n=world.models[0].visleafs;rowbytes=(n+7)//8;oldbytes=(original.visleafs+7)//8
    def source_row(i):
        ofs=old.leafs[i].visofs
        return decompress_vis(old.visdata,ofs,oldbytes) if ofs>=0 else bytes([255])*oldbytes
    portal_mask=sum(1<<(i-1) for i in portal);old_visible=0
    for i in portal:old_visible|=int.from_bytes(source_row(i),'little')
    opened_old=0
    for i in range(1,original.visleafs+1):
        if int.from_bytes(source_row(i),'little')&portal_mask:opened_old|=1<<(i-1)
    cross_mask=old_visible|opened_old
    allnew=((1<<plains.visleafs)-1)<<original.visleafs
    blob=bytearray();cache={};opened=0
    for r,reg in enumerate(builder.regions):
        srcbytes=(reg.visleafs+7)//8
        for i in range(1,reg.visleafs+1):
            src=reg.bsp.leafs[i];raw=decompress_vis(reg.bsp.visdata,src.visofs,srcbytes) if src.visofs>=0 else bytes([255])*srcbytes
            mask=int.from_bytes(raw,'little') & ((1<<reg.visleafs)-1)
            if r==0:
                if (cross_mask&(1<<(i-1))) if reciprocal else (mask&portal_mask):mask|=allnew;opened+=1
            else:mask=(mask<<original.visleafs)|(cross_mask if reciprocal else old_visible)
            packed=compress_vis(mask.to_bytes(rowbytes,'little'))
            if packed not in cache:cache[packed]=len(blob);blob.extend(packed)
            world.leafs[builder.leaf_map[r,i]].visofs=cache[packed]
    world.visdata=bytes(blob)
    return {'portal_leaves':portal,'original_rows_opened':opened,'plains_rows_opened':plains.visleafs,
        'reciprocal_cross_visibility':reciprocal,'bytes':len(blob)}

def clip_2d(points,a,b,c,positive):
    """Clip an X/Z section polygon by a*x+b*z+c >= 0 (or <= 0)."""
    out=[]
    for p,q in zip(points,points[1:]+points[:1]):
        dp=a*p[0]+b*p[1]+c;dq=a*q[0]+b*q[1]+c
        ip=dp>=-1e-6 if positive else dp<=1e-6;iq=dq>=-1e-6 if positive else dq<=1e-6
        if ip:out.append(p)
        if ip!=iq:
            t=dp/(dp-dq);out.append((p[0]+t*(q[0]-p[0]),p[1]+t*(q[1]-p[1])))
    clean=[]
    for p in out:
        if not clean or sum((p[k]-clean[-1][k])**2 for k in range(2))>1e-8:clean.append(p)
    if len(clean)>1 and sum((clean[0][k]-clean[-1][k])**2 for k in range(2))<1e-8:clean.pop()
    if len(clean)<3:return []
    area=abs(sum(p[0]*q[1]-q[0]*p[1] for p,q in zip(clean,clean[1:]+clean[:1])))/2
    return clean if area>.01 else []

def visible_caps(builder,world,sky_close=False,stone_facing=False):
    """Render the existing solid section at the seam, without altering hulls.

    Every cap is attached to the axial join node and a portal leaf visible from
    every new-region PVS row. Faces receive ordinary style0 RGB lightmaps.
    """
    old=builder.regions[0].bsp;ow=old.models[0];w=world.models[0]
    xmin,xmax=w.mins[0],w.maxs[0];floor=3072.;segments=[]
    # Narrow cross-sections keep rock UV extents and face lightmaps modest.
    x=xmin
    while x<xmax-.001:
        right=min(x+256,xmax)
        def top(xx):return 3512+36*math.sin(xx/811)+20*math.sin(xx/277)
        initial=[(x,floor),(right,floor),(right,top(right)),(x,top(x))]
        stack=[(ow.headnode[0],initial)]
        while stack:
            index,poly=stack.pop()
            if not poly:continue
            if index<0:
                if old.leafs[-index-1].contents==-2:segments.append(poly)
                continue
            n=old.nodes[index];p=old.planes[n.planenum]
            a,b=p.normal[0],p.normal[2];c=p.normal[1]*(SEAM-.001)-p.dist
            if abs(a)+abs(b)<1e-10:
                stack.append((n.children[0 if c>=0 else 1],poly));continue
            for positive,child in [(True,n.children[0]),(False,n.children[1])]:
                part=clip_2d(poly,a,b,c,positive)
                if part:stack.append((child,part))
        x=right
    # Keep the broad original road aperture entirely clear. Small brush roofs
    # and wall overhangs within this band retain their original render faces.
    clipped_segments=[]
    for poly in segments:
        for a,c,positive in [(1,-1104,False),(1,-2432,True)]:
            part=clip_2d(poly,a,0,c,positive)
            if part:clipped_segments.append(part)
    segments=clipped_segments
    skysegments=[]
    if sky_close:
        # Cropping the new south wall also removed its projected sky coverage.
        # The original small map cannot fill rays outside its sky footprint.
        # Close only old solid/sky portions above the natural cliff silhouette;
        # keep the broad road band open below its genuine ceiling Z3584.
        cuts=sorted(set([xmin,xmax,1104.,2432.]+[min(xmin+i*256,xmax) for i in range(math.ceil((xmax-xmin)/256)+1)]))
        for left,right in zip(cuts,cuts[1:]):
            if left<xmin-.01 or right>xmax+.01:continue
            road=1104<=(left+right)/2<=2432
            low_left=3584. if road else top(left);low_right=3584. if road else top(right)
            initial=[(left,low_left),(right,low_right),(right,w.maxs[2]),(left,w.maxs[2])]
            stack=[(ow.headnode[0],initial)]
            while stack:
                index,poly=stack.pop()
                if not poly:continue
                if index<0:
                    if old.leafs[-index-1].contents in (-2,-6):skysegments.append(poly)
                    continue
                n=old.nodes[index];p=old.planes[n.planenum]
                a,b=p.normal[0],p.normal[2];c=p.normal[1]*(SEAM-.001)-p.dist
                if abs(a)+abs(b)<1e-10:
                    stack.append((n.children[0 if c>=0 else 1],poly));continue
                for positive,child in [(True,n.children[0]),(False,n.children[1])]:
                    part=clip_2d(poly,a,b,c,positive)
                    if part:stack.append((child,part))
    material=next((i for i,t in enumerate(world.textures) if t.name.lower()=='dprock'),None)
    if material is None:raise ValueError('Original procedural plains rock material missing')
    ti=len(world.texinfo);world.texinfo.append(TexInfo([[.25,0,0,0],[0,0,-.25,0]],material,-65536))
    newfaces=[];light=bytearray(world.lighting);plane=world.nodes[0].planenum
    for poly in segments:
        # Quake/GoldSrc brush polygons wind clockwise from their outward
        # plane side: stock Xash uses GL_CCW plus GL_FRONT culling. Keeping
        # CPU plane side0 does not make a positive-winding polygon visible.
        # The corrected candidate keeps the exact material partition/hulls.
        winding=poly if stone_facing else reversed(poly)
        pts=[(xx,SEAM,zz) for xx,zz in winding]
        ids=[]
        for p in pts:ids.append(len(world.vertexes));world.vertexes.append(p)
        first=len(world.surfedges)
        for aa,bb in zip(ids,ids[1:]+ids[:1]):
            world.surfedges.append(len(world.edges));world.edges.append((aa,bb))
        face=Face(plane,0,first,len(ids),ti,[0,255,255,255],len(light))
        ext=face_extents(world,face,16)
        for t in range(ext[1][0],ext[1][1]+1):
            for s in range(ext[0][0],ext[0][1]+1):
                z=-t*64;blend=max(0,min(1,(z-floor)/512))
                noise=4*math.sin(s*1.93+t*3.1)
                light.extend(bytes(int(max(0,min(255,v))) for v in [112+25*blend+noise,103+23*blend+noise,94+21*blend+noise]))
        newfaces.append(face)
    if skysegments:
        skytexture=next((i for i,t in enumerate(world.textures) if t.name.lower()=='sky'),None)
        if skytexture is None:raise ValueError('Original SKY texture missing')
        skyti=len(world.texinfo);world.texinfo.append(TexInfo([[.25,0,0,0],[0,0,-.25,0]],skytexture,-65535))
        for poly in skysegments:
            winding=poly if stone_facing else reversed(poly)
            pts=[(xx,SEAM,zz) for xx,zz in winding];ids=[]
            for p in pts:ids.append(len(world.vertexes));world.vertexes.append(p)
            first=len(world.surfedges)
            for aa,bb in zip(ids,ids[1:]+ids[:1]):
                world.surfedges.append(len(world.edges));world.edges.append((aa,bb))
            newfaces.append(Face(plane,0,first,len(ids),skyti,[255,255,255,255],-1))
    at=w.firstface+w.numfaces;count=len(newfaces)
    # Insert caps into the contiguous world face range; every later node,
    # submodel and marksurface range is remapped by exactly the same offset.
    for n in world.nodes:
        if n.numfaces and n.firstface>=at:n.firstface+=count
    for m in world.models[1:]:
        if m.numfaces and m.firstface>=at:m.firstface+=count
    world.marksurfaces=[fi+count if fi>=at else fi for fi in world.marksurfaces]
    for key,fi in list(builder.face_map.items()):
        if fi>=at:builder.face_map[key]=fi+count
    world.faces[at:at]=newfaces;w.numfaces+=count
    world.nodes[0].firstface=at;world.nodes[0].numfaces=count
    world.lighting=bytes(light)
    # Use one common original portal leaf. It is explicitly cross-visible in
    # all new rows and root-node faces are bounded by the combined world.
    orig=builder.regions[0];oldcount=orig.visleafs;nbytes=(w.visleafs+7)//8
    shared=(1<<oldcount)-1
    for i in range(oldcount+1,w.visleafs+1):
        l=world.leafs[i];shared&=int.from_bytes(decompress_vis(world.visdata,l.visofs,nbytes),'little')
    if not shared:raise ValueError('Caps have no leaf visible from every new PVS row')
    leafindex=(shared&-shared).bit_length()
    # Stock draw traversal visits the front/plain tree before the join faces.
    # Share one front portal anchor across every new PVS row as well, so its
    # marksurface stamping precedes the join-node face pass. PrimeXT marks
    # leaves up front but culls their bounds; both holders and their ancestors
    # must enclose the caps rather than their old, small portal boxes.
    frontindex=builder.leaf_map[1,1]
    blob=bytearray();cache={}
    for i,l in enumerate(world.leafs[1:w.visleafs+1],1):
        row=bytearray(decompress_vis(world.visdata,l.visofs,nbytes))
        if i>oldcount:row[(frontindex-1)//8]|=1<<((frontindex-1)%8)
        packed=compress_vis(bytes(row))
        if packed not in cache:cache[packed]=len(blob);blob.extend(packed)
        l.visofs=cache[packed]
    world.visdata=bytes(blob)
    oldmarks=world.marksurfaces;world.marksurfaces=[]
    holders={leafindex,frontindex}
    for i,l in enumerate(world.leafs):
        marks=oldmarks[l.firstmarksurface:l.firstmarksurface+l.nummarksurfaces]
        if i in holders:marks=marks+list(range(at,at+count))
        l.firstmarksurface=len(world.marksurfaces);l.nummarksurfaces=len(marks);world.marksurfaces.extend(marks)
    capmins=tuple(math.floor(min(v[k] for f in newfaces for v in polygon(world,f))) for k in range(3))
    capmaxs=tuple(math.ceil(max(v[k] for f in newfaces for v in polygon(world,f))) for k in range(3))
    for i in holders:
        l=world.leafs[i]
        l.mins=tuple(min(l.mins[k],capmins[k]) for k in range(3));l.maxs=tuple(max(l.maxs[k],capmaxs[k]) for k in range(3))
    parents={}
    for ni,node in enumerate(world.nodes):
        for child in node.children:parents.setdefault(child,[]).append(ni)
    pending=[-i-1 for i in holders];updated=set()
    while pending:
        child=pending.pop()
        for ni in parents.get(child,[]):
            if ni in updated:continue
            updated.add(ni);node=world.nodes[ni]
            node.mins=tuple(min(node.mins[k],capmins[k]) for k in range(3));node.maxs=tuple(max(node.maxs[k],capmaxs[k]) for k in range(3))
            pending.append(ni)
    return {'faces':count,'lit_rock_faces':len(segments),'sky_closure_faces':len(skysegments),
        'sky_closure_road_band_min_z':3584 if sky_close else None,
        'sky_closure_top_z':w.maxs[2] if sky_close else None,
        'common_visible_leaf':leafindex,'material':world.textures[material].name,
        'material_provenance':'Original procedural DPROCK from frozen Daragoth-Plains generator; geometry generated from audited BSP solid section',
        'lighting':'RGB style0 baked gradient 94..145; no fullbright','floor_z':floor,
        'natural_boundary_top_z_range':[3456,3568],'collision_trees_unchanged':True,
        'stock_brush_winding_corrected':stone_facing,
        'winding_contract':'clockwise from outward +Y plane; GL_CCW/GL_FRONT' if stone_facing else 'historical positive winding; native rock faces culled',
        'front_visible_leaf':frontindex,'holder_bounds_expanded_to_caps':True,
        'ancestor_bounds_expanded_count':len(updated),'cap_bounds':[capmins,capmaxs]}

def validate(world,original):
    failures=[];w=world.models[0];checks=0
    for x in [1450,1488,1528,1568,1606]:
        for y in [SEAM-64,SEAM-16,SEAM-0.125,SEAM,SEAM+0.125,SEAM+16,SEAM+64]:
            for h,z in [(0,3072.125),(1,3108.125),(2,3108.125),(3,3090.125)]:
                value=hull_point_contents(world,w.headnode[h],(x,y,z),h);checks+=1
                if value==-2:failures.append({'blocked_seam':[x,y,z],'hull':h})
    for x,y,z in [(-864,-3856,3200),(-3904,-1000,1980.31),(2048,1552,3108),(1528,3155,3108.31)]:
        for h in range(4):
            a=hull_point_contents(original,original.models[0].headnode[h],(x,y,z),h)
            b=hull_point_contents(world,w.headnode[h],(x,y,z),h);checks+=1
            if a!=b:failures.append({'original_collision_changed':[x,y,z],'hull':h,'before':a,'after':b})
    for i,f in enumerate(world.faces):
        if not 0<=f.texinfo<len(world.texinfo) or not 0<=f.planenum<len(world.planes):failures.append({'invalid_face':i})
        if f.lightofs>=0 and not world.texinfo[f.texinfo].flags&1:
            e=face_extents(world,f,sample_size(world,f));size=(e[0][1]-e[0][0]+1)*(e[1][1]-e[1][0]+1)*sum(s!=255 for s in f.styles)*3
            if f.lightofs+size>len(world.lighting):failures.append({'lightmap_bounds':i})
    order=tree_order_errors(world)
    if order:failures.append({'tree_order_errors':order})
    if any(x<0 or x>=len(world.faces) for x in world.marksurfaces):failures.append({'marksurface_bounds':True})
    if len(world.nodes)>=32767 or len(world.vertexes)>=65536 or len(world.faces)>=65536:failures.append({'disk_index_limits':True})
    return {'hull_content_checks':checks,'tree_order_errors':order,'failures':failures}

def build(original_path,ent_path,out,tools,reuse,caps=False,sky_close=False,stone_facing=False,variant_builder=None,output_suffix=None,omit_legacy_skyline=False):
    # The surgical edits below use original entity indices. Reject a changed
    # map or sidecar before writing anything rather than dropping unknown NPCs.
    if sha(original_path)!=ORIGINAL_BSP_SHA256 or sha(ent_path)!=ORIGINAL_ENT_SHA256:
        raise ValueError('Original BSP/ENT differs from the audited input; re-survey before editing entity indices')
    out.mkdir(parents=True,exist_ok=True);maps=out/'variant/msr/maps'
    report={'prototype':True,'public_release':False,'seam_world_y':SEAM,'plains_offset':OFFSET,
        'original_bsp_sha256':sha(original_path),'original_ent_sha256':sha(ent_path),
        'lifecycle_limitation':'All regions remain loaded via ms_region_unload_time 0; adjacency-aware streaming deferred.'}
    report['variant']=(variant_builder or variant)(maps)
    if not reuse:compile_variant(maps,tools)
    cfg={'regions':[{'name':'daragoth','bsp':str(original_path),'offset':[0,0,0],
           'meta':{'title':'The Plains of Daragoth','desc':'These expansive plains are contested by orcish hordes.',
                   'diff':'Levels 15-20 / 150-250hp','warnhp':'100','skyname':'grnplsnt','maxrange':'60000'}},
         {'name':'daragoth_plains','bsp':str(maps/'daragoth_plains.bsp'),'offset':OFFSET,
          'rename_prefix':'dp_','meta':{'title':'The Expanded Plains of Daragoth','desc':'Rolling fields and the southern riding stable.',
                'diff':'Riding development preview','skyname':'grnplsnt','maxrange':'60000'}}],
         'split':{'order':['daragoth_plains','daragoth'],'planes':[[1,SEAM]]},
         'worldspawn':{'maptitle':'Daragoth - Continuous Plains Preview','MaxRange':'60000'}}
    regs=[RegionSource(c,ROOT) for c in cfg['regions']]
    regs[0].bsp.entities=parse_entities(ent_path.read_text(encoding='latin1'))
    original=copy.deepcopy(regs[0].bsp)
    removed=[];kept=[]
    for i,e in enumerate(regs[0].bsp.entities):
        skyline=omit_legacy_skyline and i==468
        if skyline and (e.classname!='env_model' or e.get('model')!='models/terrain/Deralia_3dskybox.mdl'):
            raise ValueError('Legacy skyline exclusion no longer matches the surveyed decoration')
        drop=skyline or i in [303,304,376,409,410,470,471,472,473,474,475,476,477]
        if drop:
            detail={'index':i,'class':e.classname,'target':e.get('targetname'),
                    'model':e.get('model'),'origin':e.get('origin'),
                    'reason':'Legacy decorative skyline overlaps the traversable expanded fields' if skyline else 'North gateway decoration opens the continuous road' if i!=376 else 'Deralia exit moved to the far northern plains'}
            if (e.get('model') or '').startswith('*'):
                model=regs[0].bsp.models[int(e.get('model')[1:])]
                detail.update(mins=model.mins,maxs=model.maxs)
            removed.append(detail)
        else:kept.append(e)
    regs[0].bsp.entities=kept;report['removed_original_north_entities']=removed
    regs[1].bsp.entities=[e for e in regs[1].bsp.entities if e.classname not in ['ms_player_begin','ms_player_spec','info_player_start','light_environment','spawn_dis','info_player_deathmatch']
        and not(e.classname=='ms_npc' and e.get('scriptfile')=='game_master')
        and not(e.classname=='ms_player_spawn' and (caps or e.get('message') in ['daragoth01','deralia','from_nash','mines']))]
    # Old BSP has no faceinfo, so explicitly use the -1 sentinel before adding
    # the plains faceinfo0 (64 units). Without this old maps would inherit 64.
    for t in regs[0].bsp.texinfo:t.flags=(t.flags&65535)-65536
    report['crop_original']=crop(regs[0].bsp,SEAM,True)
    report['crop_plains']=crop(regs[1].bsp,LOCAL_SEAM,False)
    builder=WorldBuilder(regs,[1,0]);world=builder.build(1,[[1,SEAM]])
    world.extra_lumps[1]=regs[1].bsp.extra_lumps[1]
    report['shifted_lightmaps_repacked']=repair_shifted_lighting(builder,world)
    report['visibility']=cross_vis(builder,world,reciprocal=caps)
    if caps:report['visible_caps']=visible_caps(builder,world,sky_close,stone_facing)
    ents=process_entities(builder,cfg)
    for e in ents[1:]:
        if getattr(e,'region',None):e.set('msr_region',e.region)
        if e.classname.startswith('ms_player') or e.classname=='light_environment':e.set('msr_keep','1')
    metadata=region_entities(regs,cfg,report)
    world.entities=ents[:1]+metadata+ents[1:]
    # Ordinary map startup needs precisely one global game master; root will
    # preserve the base library and supply this map's metadata scripts.
    global_master=Entity([['classname','ms_npc'],['scriptfile','game_master'],['targetname','expanded_game_master'],
        ['origin','0 0 3500'],['msr_region','daragoth'],['msr_keep','1']])
    world.entities.append(global_master)
    masters=[e for e in world.entities if e.classname=='ms_npc' and e.get('scriptfile')=='game_master']
    if len(masters)!=1:raise ValueError('Continuous world must have exactly one explicit global game_master')
    original_gate=original.entities[376]
    relocated=[e for e in world.entities if e.classname=='msarea_transition' and e.get('targetname')=='deralia']
    if len(relocated)!=1:raise ValueError('Expected one relocated Deralia exit')
    destination_keys=('destmap','desttrans','destname')
    for key in destination_keys:
        if original_gate.get(key)!=relocated[0].get(key):raise ValueError('Deralia destination metadata changed: '+key)
    report['deralia_destination']={key:original_gate.get(key) for key in destination_keys}
    report['deralia_destination_absent_keys']=[key for key in destination_keys if original_gate.get(key) is None]
    report['global_game_master_count']=len(masters)
    report['intended_runtime_map_alias']='daragoth'
    suffix=output_suffix if output_suffix is not None else '_stonefaced' if stone_facing else '_skyclosed' if sky_close else '_capped' if caps else ''
    if suffix and (not suffix.startswith('_') or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789_' for c in suffix)):
        raise ValueError('Invalid candidate output suffix')
    path=out/('daragoth_expanded'+suffix+'.bsp');world.save(path,bsp30ext=True)
    written=BSP.load(path)
    report['verification']=validate(written,original)
    report['output']={'path':str(path),'sha256':sha(path),'crc32':zlib.crc32(path.read_bytes())&0xffffffff,'bytes':path.stat().st_size,
        'counts':{key:len(getattr(written,key)) for key in ['planes','vertexes','nodes','clipnodes','faces','leafs','models','entities']}}
    report['merge']=builder.report
    report['original_start_region_only']=caps
    report_suffix=suffix.replace('_','-')
    dump(out/('continuous-join'+report_suffix+'-report.json'),report)
    dump(out/('daragoth-expanded'+report_suffix+'-config.json'),cfg)
    if report['verification']['failures']:raise RuntimeError(json.dumps(report['verification'],indent=2))
    print(json.dumps(report['output'],indent=2),flush=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--original',type=Path,required=True);p.add_argument('--ent',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--tools',type=Path,required=True)
    p.add_argument('--reuse-compiled',action='store_true')
    p.add_argument('--caps',action='store_true',help='Separate capped candidate with reciprocal PVS and original-only spawn pool')
    p.add_argument('--sky-close',action='store_true',help='Separate sky-closed candidate; includes caps and original-only spawn pool')
    p.add_argument('--stone-facing',action='store_true',help='Separate native brush-winding repair; includes sky closure, same material sections and unchanged hulls')
    a=p.parse_args()
    # A separate filename preserves the first frozen candidate while QA runs.
    if a.out.resolve().is_relative_to(Path('C:/MSR').resolve()):p.error('Output must be private scratch, not the live installation')
    build(a.original.resolve(),a.ent.resolve(),a.out.resolve(),a.tools.resolve(),a.reuse_compiled,a.caps or a.sky_close or a.stone_facing,a.sky_close or a.stone_facing,a.stone_facing)
if __name__=='__main__':main()
