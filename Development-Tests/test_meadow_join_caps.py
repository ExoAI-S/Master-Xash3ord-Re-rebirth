"""Independent preservation and rendered-interface QA for meadow join caps.

Compare frozen BSP data, collision topology, old faces, leaf marks and bounds.
Check both directions of the compiled interface independently of builder parts.
Optional actual-C sweeps exercise the unchanged standing road across the join.
Native appearance/PVS and complete walking coverage are not claimed.
"""
from __future__ import annotations

import argparse
from collections import Counter,defaultdict
import json
import math
from pathlib import Path
import shutil
import struct
import sys
import tempfile

REPO=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(REPO/'Packaging-Work/BigWorld/tools'),str(REPO/'Design-Source/Daragoth-Meadow')]
from bsp30 import BSP,FACE
from test_meadow_creek import sha,section,fail,finish,hull0_contents

BASE_SHA='9b3ae9aaeb56ff274f0caa3979661de8970c0cdf43de603c0b06355bc098c064'
SEAM=3216.
CHANGED={3,5,7,8,10,11,12,13,14}


def raw_lump(data,index):
    at,size=struct.unpack_from('<2i',data,4+8*index)
    return data[at:at+size]


def polygon(bsp,face):
    points=[]
    for se in bsp.surfedges[face.firstedge:face.firstedge+face.numedges]:
        edge=bsp.edges[abs(se)];points.append(bsp.vertexes[edge[0 if se>=0 else 1]])
    return points


def contains_bounds(new_min,new_max,old_min,old_max):
    return all(new_min[k]<=old_min[k] and new_max[k]>=old_max[k] for k in range(3))


def preservation(base_path,path,old,bsp,at,count):
    result=section();a=base_path.read_bytes();b=path.read_bytes()
    result['immutable_lumps_identical']={}
    for i in range(15):
        if i in CHANGED:continue
        same=raw_lump(a,i)==raw_lump(b,i);result['immutable_lumps_identical'][str(i)]=same
        if not same:fail(result,'Immutable BSP lump changed',lump=i)
    prefix=bytearray(b[:len(a)])
    for i in CHANGED:prefix[4+8*i:12+8*i]=a[4+8*i:12+8*i]
    if prefix!=a:fail(result,'Frozen source prefix changed outside allowed render-lump descriptors')
    for i in (3,8,12,13):
        if not raw_lump(b,i).startswith(raw_lump(a,i)):fail(result,'Existing render data prefix changed',lump=i)
    old_faces=raw_lump(a,7);new_faces=raw_lump(b,7);stride=FACE.size
    if new_faces[:at*stride]!=old_faces[:at*stride] or new_faces[(at+count)*stride:]!=old_faces[at*stride:]:
        fail(result,'Old faces changed or lost their order around inserted caps')
    if len(old.nodes)!=len(bsp.nodes) or len(old.leafs)!=len(bsp.leafs) or len(old.models)!=len(bsp.models):
        fail(result,'Collision topology record counts changed')
        return finish(result)
    map_face=lambda i:i+count if i>=at else i
    root=old.models[0].headnode[0]
    enlarged_nodes=[];holders=set();mark_refs=Counter()
    for i,(before,after) in enumerate(zip(old.leafs,bsp.leafs)):
        if (before.contents,before.visofs,before.ambient)!=(after.contents,after.visofs,after.ambient):
            fail(result,'Leaf contents, PVS offset or ambient data changed',leaf=i)
        expected=[map_face(v) for v in old.marksurfaces[before.firstmarksurface:before.firstmarksurface+before.nummarksurfaces]]
        actual=bsp.marksurfaces[after.firstmarksurface:after.firstmarksurface+after.nummarksurfaces]
        kept=[v for v in actual if not at<=v<at+count];extra=[v for v in actual if at<=v<at+count]
        if kept!=expected:fail(result,'Old leaf marks changed, reordered or remapped incorrectly',leaf=i)
        if len(extra)!=len(set(extra)):fail(result,'Duplicate added cap in a leaf marksurface list',leaf=i)
        if extra:holders.add(i);mark_refs.update(extra)
        if (before.mins,before.maxs)!=(after.mins,after.maxs) and i not in holders:
            fail(result,'Unrelated leaf bounds changed',leaf=i)
        if not contains_bounds(after.mins,after.maxs,before.mins,before.maxs):fail(result,'Leaf render bounds shrank',leaf=i)
        for fi in extra:
            if any(any(p[k]<after.mins[k]-.001 or p[k]>after.maxs[k]+.001 for k in range(3)) for p in polygon(bsp,bsp.faces[fi])):
                fail(result,'Leaf render bounds do not contain its added cap',leaf=i,face=fi)
    parents=defaultdict(list)
    for i,n in enumerate(old.nodes):
        for child in n.children:parents[child].append(i)
    allowed=set();pending=[-i-1 for i in holders]
    while pending:
        for parent in parents.get(pending.pop(),()):
            if parent not in allowed:allowed.add(parent);pending.append(parent)
    for i,(before,after) in enumerate(zip(old.nodes,bsp.nodes)):
        if (before.planenum,before.children)!=(after.planenum,after.children):fail(result,'Render collision node plane or children changed',node=i)
        expected_first=map_face(before.firstface) if before.numfaces else before.firstface
        expected_count=before.numfaces+count if i==root else before.numfaces
        if after.firstface!=expected_first or after.numfaces!=expected_count:fail(result,'Node face range remapped incorrectly',node=i)
        if (before.mins,before.maxs)!=(after.mins,after.maxs):
            enlarged_nodes.append(i)
            if i not in allowed:fail(result,'Node bounds changed outside ancestors of cap holders',node=i)
        if not contains_bounds(after.mins,after.maxs,before.mins,before.maxs):fail(result,'Node render bounds shrank',node=i)
    for i,(before,after) in enumerate(zip(old.models,bsp.models)):
        if (before.mins,before.maxs,before.origin,before.headnode,before.visleafs)!=(after.mins,after.maxs,after.origin,after.headnode,after.visleafs):
            fail(result,'Model bounds, origin, collision headnodes or visleafs changed',model=i)
        expected_first=map_face(before.firstface) if before.numfaces else before.firstface
        expected_count=before.numfaces+count if i==0 else before.numfaces
        if after.firstface!=expected_first or after.numfaces!=expected_count:fail(result,'Submodel/world face range remapped incorrectly',model=i)
    if any(mark_refs[i]<1 for i in range(at,at+count)):fail(result,'An added cap has no leaf marksurface reference')
    old_root=old.nodes[root];old_caps=set(range(old_root.firstface,old_root.firstface+old_root.numfaces))
    common=[i for i,l in enumerate(old.leafs) if old_caps.issubset(set(old.marksurfaces[l.firstmarksurface:l.firstmarksurface+l.nummarksurfaces]))]
    for i in common:
        leaf=bsp.leafs[i];marks=set(bsp.marksurfaces[leaf.firstmarksurface:leaf.firstmarksurface+leaf.nummarksurfaces])
        if not set(range(at,at+count)).issubset(marks):fail(result,'Existing common visibility anchor lacks new caps',leaf=i)
    result.update({'entities_preserved':len(bsp.entities),'collision_nodes':len(bsp.nodes),
                   'models_headnodes_preserved':len(bsp.models),'leaves_contents_preserved':len(bsp.leafs),
                   'old_faces_preserved':len(old.faces),'added_cap_mark_references':sum(mark_refs.values()),
                   'cap_holder_leaves':sorted(holders),'common_visibility_anchors':common,'enlarged_render_nodes':len(enlarged_nodes)})
    return finish(result)


def cap_record(bsp,fi):
    f=bsp.faces[fi];points=polygon(bsp,f);plane=bsp.planes[f.planenum]
    normal=tuple(v*(-1 if f.side else 1) for v in plane.normal)
    projected=[(p[0],p[2]) for p in points]
    area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(projected,projected[1:]+projected[:1]))/2
    return {'face':fi,'side':0 if normal[1]>0 else 1,'normal':normal,'points':projected,'area':area,
            'bounds':(min(p[0] for p in projected),min(p[1] for p in projected),max(p[0] for p in projected),max(p[1] for p in projected))}


def inside(cap,x,z,tolerance=.02):
    sign=0
    for a,b in zip(cap['points'],cap['points'][1:]+cap['points'][:1]):
        dx,dz=b[0]-a[0],b[1]-a[1];cross=dx*(z-a[1])-dz*(x-a[0])
        length=math.hypot(dx,dz)
        if not length or abs(cross)<=tolerance*length:continue
        side=1 if cross>0 else -1
        if sign and sign!=side:return False
        sign=side
    return True


def strict_inside(cap,x,z,clearance=.02):
    orientation=1 if cap['area']>0 else -1
    for a,b in zip(cap['points'],cap['points'][1:]+cap['points'][:1]):
        dx,dz=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dz)
        if length and orientation*(dx*(z-a[1])-dz*(x-a[0]))<=clearance*length:return False
    return True


class CapIndex:
    def __init__(self,caps):
        self.cells=defaultdict(list)
        for c in caps:
            lo_x,lo_z,hi_x,hi_z=c['bounds']
            for x in range(math.floor(lo_x/256),math.floor(hi_x/256)+1):
                for z in range(math.floor(lo_z/256),math.floor(hi_z/256)+1):self.cells[x,z].append(c)
    def at(self,x,z,side,strict=False):
        test=strict_inside if strict else inside
        return [c for c in self.cells.get((math.floor(x/256),math.floor(z/256)),()) if c['side']==side and test(c,x,z)]


def interface(bsp,x,z):
    root=bsp.nodes[bsp.models[0].headnode[0]]
    north=hull0_contents(bsp,root.children[0],(x,SEAM,z));south=hull0_contents(bsp,root.children[1],(x,SEAM,z))
    side=1 if north==-2 and south in (-1,-6) else 0 if south==-2 and north in (-1,-6) else None
    return side,north,south


def math_interface(bsp,x,z):
    # Independent double-precision section decision avoids conflating thin
    # authored polygons with float32 collision boundary rounding.
    root=bsp.nodes[bsp.models[0].headnode[0]];out=[]
    for head in root.children:
        node=head
        while node>=0:
            r=bsp.nodes[node];p=bsp.planes[r.planenum]
            d=p.normal[0]*x+p.normal[1]*SEAM+p.normal[2]*z-p.dist
            node=r.children[0 if d>=0 else 1]
        out.append(bsp.leafs[-node-1].contents)
    n,s=out;side=1 if n==-2 and s in (-1,-6) else 0 if s==-2 and n in (-1,-6) else None
    return side,n,s


def geometry(old,bsp,at,count):
    result=section();root=bsp.nodes[bsp.models[0].headnode[0]];all_caps=[];original_caps=[];added=[]
    for fi in range(bsp.models[0].firstface,bsp.models[0].firstface+bsp.models[0].numfaces):
        points=polygon(bsp,bsp.faces[fi])
        if points and all(abs(p[1]-SEAM)<.002 for p in points):
            c=cap_record(bsp,fi)
            if abs(c['normal'][1])>.999:all_caps.append(c)
    for fi in range(old.models[0].firstface,old.models[0].firstface+old.models[0].numfaces):
        points=polygon(old,old.faces[fi])
        if points and all(abs(p[1]-SEAM)<.002 for p in points):
            c=cap_record(old,fi)
            if abs(c['normal'][1])>.999:original_caps.append(c)
    prior=CapIndex(original_caps);texture_counts=Counter();numeric_boundaries=0;shared_edge_samples=0
    for fi in range(at,at+count):
        f=bsp.faces[fi];points=polygon(bsp,f);c=cap_record(bsp,fi);added.append(c)
        material=bsp.textures[bsp.texinfo[f.texinfo].miptex].name;texture_counts[material]+=1
        if f.planenum!=root.planenum or any(abs(p[1]-SEAM)>.002 for p in points) or abs(c['area'])<.04:
            fail(result,'New cap is not a valid axial seam polygon',face=fi)
        if c['area']*(1 if f.side==0 else -1)<=0:fail(result,'New cap winding disagrees with stock front-face culling contract',face=fi,side=f.side,area=c['area'])
        if material!='DPROCK' or f.styles!=[0,255,255,255] or f.lightofs<len(old.lighting):
            fail(result,'New cap material/style/lightmap differs from preservation policy',face=fi)
        values=[]
        for axis in bsp.texinfo[f.texinfo].vecs:
            values.append([sum(p[k]*axis[k] for k in range(3))+axis[3] for p in points])
        sizes=[math.ceil(max(v)/16)-math.floor(min(v)/16)+1 for v in values]
        if f.lightofs<0 or f.lightofs+3*sizes[0]*sizes[1]>len(bsp.lighting):fail(result,'New cap lightmap exceeds its lump',face=fi)
        cx=sum(p[0] for p in c['points'])/len(points);cz=sum(p[1] for p in c['points'])/len(points)
        for x,z in [(cx,cz),*[(cx*.7+p[0]*.3,cz*.7+p[1]*.3) for p in c['points']]]:
            side,n,s=interface(old,x,z);exact,_,_=math_interface(old,x,z)
            if side!=f.side:
                if exact==f.side:numeric_boundaries+=1
                else:fail(result,'New cap covers a non-exposed or wrong-direction interface',face=fi,point=[x,z],north=n,south=s)
            if prior.at(x,z,f.side,strict=True):
                fail(result,'New cap overlaps existing coplanar coverage at an interior point',face=fi,point=[x,z])
            elif prior.at(x,z,f.side):shared_edge_samples+=1
    coverage=CapIndex(all_caps);surveys=[]
    bounds=old.models[0]
    for label,xmin,xmax,zmin,zmax,step in [('portal',-256,2816,2816,5504,16),
                                        ('whole_interface',bounds.mins[0],bounds.maxs[0],bounds.mins[2],bounds.maxs[2],64)]:
        counts=Counter();uncovered=[];examples=[]
        for gx in range(math.floor(xmin/step),math.ceil(xmax/step)):
            x=(gx+.5)*step
            if not xmin<=x<=xmax:continue
            for gz in range(math.floor(zmin/step),math.ceil(zmax/step)):
                z=(gz+.5)*step
                if not zmin<=z<=zmax:continue
                counts['grid_points']+=1;side,n,s=interface(old,x,z)
                if side is None:continue
                counts['north_facing_interfaces' if side==0 else 'south_facing_interfaces']+=1
                if not prior.at(x,z,side):counts['previously_uncovered']+=1
                if coverage.at(x,z,side):counts['covered']+=1
                else:
                    uncovered.append([x,z])
                    if len(examples)<10:examples.append({'x':x,'z':z,'side':side,'north':n,'south':s})
        if uncovered:fail(result,'Exposed interface remains uncapped on independent grid',survey=label,count=len(uncovered),examples=examples)
        surveys.append({'survey':label,'spacing':step,'counts':counts,'uncovered_count':len(uncovered),'examples':examples})
    # These are the independently reproduced visible defects, not builder
    # sample locations. The true road at this height stays uncapped.
    regression=[]
    for x,z,expected in [(768,3440,1),(64,3504,1),(128,3136,1),(1920,3120,0)]:
        before=bool(prior.at(x,z,expected));after=bool(coverage.at(x,z,expected))
        if before or not after:fail(result,'Known rendered-gap regression was not repaired',x=x,z=z)
        regression.append({'x':x,'z':z,'side':expected,'previously_capped':before,'now_capped':after})
    road=[]
    for x in (1432,1528,1624):
        for z in (3096,3120,3152,3200):
            side,n,s=interface(old,x,z)
            if n!=-1 or s!=-1:continue
            if any(inside(c,x,z) for c in added):fail(result,'New render cap closes an empty road aperture',x=x,z=z)
            road.append([x,z])
    result.update({'added_faces':count,'added_by_side':dict(Counter(c['side'] for c in added)),
                   'total_join_faces':len(all_caps),'texture_counts':texture_counts,
                   'float32_boundary_rounding_samples':numeric_boundaries,
                   'old_coverage_shared_edge_tolerance_samples':shared_edge_samples,
                   'coverage_surveys':surveys,'known_gap_regressions':regression,'empty_road_aperture_probes':road,
                   'coverage_tolerance_units':.02,'scope':'Rendered cap geometry and discrete compiled interface coverage; finite grids do not prove complete walkable terrain, native culling/PVS or appearance.'})
    return finish(result)


def actual_c(path):
    if shutil.which('cl.exe') is None:return {'status':'skipped','pass':None,'reason':'--actual-c requested but cl.exe unavailable'}
    import test_daragoth_expanded_collision as collision
    result=section();result['status']='ran';model=collision.MapCollision(path)
    cases=[((x,y,3110.),(x,y+4,3110.)) for x in (1432.,1528.,1624.) for y in range(3040,3400,4)]
    with tempfile.TemporaryDirectory(prefix='msr-join-caps-qa-') as temp:
        folder=Path(temp);exe=collision.actual.build(folder)
        for case,t in zip(cases,model.traces(exe,folder,1,cases)):
            if t['startsolid'] or t['allsolid'] or t['fraction']<1:fail(result,'Actual C standing road sweep is blocked',case=case,trace=t)
    result.update({'standing_road_sweeps':len(cases),'step_units':4,'engine_pm_trace_sha256':sha(REPO/'Engine-Source/Xash3D/engine/common/pm_trace.c'),
                   'scope':'Actual C hull1 straight 4-unit road sweeps across the join at standing center Z3110. No full-map movement, dynamic entity or native visual claim.'})
    return finish(result)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('base','bsp','report-source','report'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--actual-c',action='store_true');args=parser.parse_args();sys.setrecursionlimit(20000)
    inputs={'base':args.base,'bsp':args.bsp,'report_source':args.report_source}
    if args.report.resolve() in {p.resolve() for p in inputs.values()}:parser.error('Report must not overwrite an input')
    hashes={k:sha(p) for k,p in inputs.items()};source=json.loads(args.report_source.read_text());metadata=section()
    if hashes['base']!=BASE_SHA or source.get('base_sha256')!=hashes['base']:fail(metadata,'Frozen base hash mismatch')
    if source.get('output_sha256')!=hashes['bsp']:fail(metadata,'Frozen output hash mismatch')
    old=BSP.load(args.base);bsp=BSP.load(args.bsp);at=old.models[0].firstface+old.models[0].numfaces;count=len(bsp.faces)-len(old.faces)
    if count<=0 or source.get('insert_face_at')!=at or source.get('added_faces')!=count:fail(metadata,'Added cap count or insertion metadata differs from parsed BSP')
    report={'input_sha256':hashes,'metadata':finish(metadata),'actual_c_requested':args.actual_c}
    print('Checking unchanged collision/entity data and old render-face remapping',flush=True)
    report['preservation']=preservation(args.base,args.bsp,old,bsp,at,count)
    print('Checking both cap directions, winding/lightmaps and independent interface grids',flush=True)
    report['geometry']=geometry(old,bsp,at,count)
    report['actual_c']=actual_c(args.bsp) if args.actual_c else {'status':'not_requested','pass':None,'reason':'No C harness requested'}
    report['inputs_unchanged_during_verification']=hashes=={k:sha(p) for k,p in inputs.items()}
    report['static_pass']=report['inputs_unchanged_during_verification'] and all(report[k]['pass'] for k in ('metadata','preservation','geometry'))
    report['pass']=report['static_pass'] and (not args.actual_c or report['actual_c']['pass'] is True)
    report['scope']='Independent render-only join preservation and missing-interface cap checks. Actual-C road sweeps only if run; native visibility/appearance requires separate evidence.'
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'pass':report['pass'],'static_pass':report['static_pass'],'bsp_sha256':hashes['bsp'],
                      'added_faces':count,'actual_c':report['actual_c']['status'],'report':str(args.report)},indent=2))
    return 0 if report['pass'] else 1


if __name__=='__main__':raise SystemExit(main())
