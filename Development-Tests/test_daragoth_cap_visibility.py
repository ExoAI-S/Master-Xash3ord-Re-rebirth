"""Read-only cap/PVS audit and incremental actual C seam replay.

Use --previous for a frozen prior candidate and --require-sky for the separate
sky-closure candidate. Save its report under a new filename; this never writes
to either BSP or replaces earlier evidence. Matching collision semantic
fingerprints permit a bounded original-spawn contact check rather than repeating
the unchanged engine's exhaustive collision regression suite.

Stock world brushes use GL_CCW front faces with GL_FRONT culling. Their ordered
polygon area must point opposite the effective outward BSP plane (face.side).
The former positive-winding audit was incorrect and is not retained as a mode;
historical JSON evidence is preserved in its existing files.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'Packaging-Work/BigWorld/tools'))
sys.path.insert(0,str(ROOT/'Development-Tests'))
from bsp30 import BSP,decompress_vis,hull_point_contents
from merge_world import face_extents,tree_order_errors
import test_daragoth_expanded_collision as collision


def fingerprint(m):
    planes=json.dumps(m.planes,separators=(',',':')).encode()
    return [hashlib.sha256(planes+json.dumps(h,separators=(',',':')).encode()).hexdigest()for h in m.hulls]


def polygon(m,f):
    return [m.vertexes[m.edges[abs(se)][0 if se>0 else 1]]for se in m.surfedges[f.firstedge:f.firstedge+f.numedges]]


def effective_winding(m,f):
    pts=polygon(m,f);p=m.planes[f.planenum]
    if len(pts)<3:return 0.
    origin=pts[0];area=[0.,0.,0.]
    for a,b in zip(pts,pts[1:]+pts[:1]):
        u=[a[k]-origin[k]for k in range(3)];v=[b[k]-origin[k]for k in range(3)]
        area[0]+=u[1]*v[2]-u[2]*v[1]
        area[1]+=u[2]*v[0]-u[0]*v[2]
        area[2]+=u[0]*v[1]-u[1]*v[0]
    return sum(area[k]*p.normal[k]for k in range(3))*(-1 if f.side else 1)


def winding_repair_invariants(oldmap,newmap,oldrender,newrender):
    same=[];changed=[]
    for i in range(15):
        oa,ol=oldmap.lumps[i];na,nl=newmap.lumps[i]
        (same if oldmap.data[oa:oa+ol]==newmap.data[na:na+nl]else changed).append(i)
    root=oldrender.nodes[oldrender.models[0].headnode[0]]
    caps=range(root.firstface,root.firstface+root.numfaces)
    cap_points_identical=all(sorted(polygon(oldrender,oldrender.faces[i]))==sorted(polygon(newrender,newrender.faces[i]))for i in caps)
    cap_vertices=set()
    for i in caps:
        f=oldrender.faces[i]
        for se in oldrender.surfedges[f.firstedge:f.firstedge+f.numedges]:
            cap_vertices.add(oldrender.edges[abs(se)][0 if se>0 else 1])
    other_vertices=[i for i in range(len(oldrender.vertexes))if i not in cap_vertices]
    noncap_identical=len(oldrender.vertexes)==len(newrender.vertexes)and all(oldrender.vertexes[i]==newrender.vertexes[i]for i in other_vertices)
    extra_identical=oldrender.extra_lumps==newrender.extra_lumps
    passed=changed==[3]and cap_points_identical and noncap_identical and extra_identical
    return {'pass':passed,'unchanged_main_lumps':same,'changed_main_lumps':changed,'join_face_point_sets_identical':cap_points_identical,'noncap_vertices_unchanged':noncap_identical,'noncap_vertex_count':len(other_vertices),'extra_lumps_unchanged':extra_identical,'scope':'Only the ordered cap vertices may change; entities, collision, materials, PVS, lightmaps, face records, marks and model metadata must remain byte-identical.'}


def contains(mins,maxs,points):
    return all(mins[k]-.125<=p[k]<=maxs[k]+.125 for p in points for k in range(3))


def point_in_xz_polygon(x,z,pts,strict=False):
    # Test a convex BSP face using all edge halfspaces, accepting edge contact.
    crosses=[]
    for a,b in zip(pts,pts[1:]+pts[:1]):
        crosses.append((b[0]-a[0])*(z-a[2])-(b[2]-a[2])*(x-a[0]))
    if strict:return all(c>.01 for c in crosses)or all(c<-.01 for c in crosses)
    return all(c>=-.01 for c in crosses)or all(c<=.01 for c in crosses)


def render_audit(m,previous,require_sky=False):
    w=m.models[0];root=m.nodes[w.headnode[0]]
    caps=list(range(root.firstface,root.firstface+root.numfaces))
    failures=[]
    if not caps:failures.append({'missing_join_node_caps':True})
    parents={};root_side={}
    for side in (0,1):
        stack=[(root.children[side],w.headnode[0])]
        while stack:
            n,parent=stack.pop()
            if n in parents:continue
            parents[n]=parent;root_side[n]=side
            if n>=0:stack.extend((c,n)for c in m.nodes[n].children)
    holders={fi:[]for fi in caps}
    for i,leaf in enumerate(m.leafs):
        for fi in m.marksurfaces[leaf.firstmarksurface:leaf.firstmarksurface+leaf.nummarksurfaces]:
            if fi in holders:holders[fi].append(i)
    cap_details=[];rock=[];sky=[];cap_polygons=[]
    for fi in caps:
        f=m.faces[fi];pts=polygon(m,f);p=m.planes[f.planenum]
        if len(pts)<3 or any(abs(sum(p.normal[k]*v[k]for k in range(3))-p.dist)>.125 for v in pts):failures.append({'invalid_cap_polygon':fi})
        if f.planenum!=root.planenum or f.side!=0:failures.append({'invalid_cap_plane_or_side':fi})
        orientation=effective_winding(m,f)
        if orientation>=-.01:failures.append({'cap_winding_violates_stock_brush_front_culling':fi,'signed_area_dot_effective_plane':orientation})
        ti=m.texinfo[f.texinfo]
        faceinfo=(ti.flags>>16)&65535
        is_sky=m.textures[ti.miptex].name.lower().startswith('sky')
        if is_sky:
            sky.append(fi);size=0
            if not ti.flags&1 or f.lightofs!=-1 or f.styles!=[255,255,255,255]:failures.append({'sky_cap_render_contract':fi})
            if min(v[2]for v in pts)<3456-.125 or max(v[2]for v in pts)>6848+.125:
                failures.append({'sky_cap_outside_ceiling_envelope':fi})
        else:
            rock.append(fi)
            if faceinfo!=65535 or ti.flags&1 or f.styles!=[0,255,255,255] or f.lightofs<0:failures.append({'cap_lightmap_contract':fi})
            ext=face_extents(m,f,16);size=(ext[0][1]-ext[0][0]+1)*(ext[1][1]-ext[1][0]+1)*3
            if f.lightofs+size>len(m.lighting):failures.append({'cap_lightmap_bounds':fi})
        cap_polygons.append((is_sky,pts))
        valid=[];front=[]
        for li in holders[fi]:
            leaf=m.leafs[li]
            # SKY leaves participate in ordinary renderer visibility too.
            # Only SOLID is skipped by stock traversal; PrimeXT's marksurface
            # cache includes every visible non-solid leaf with attached faces.
            if leaf.contents==-2:continue
            if not contains(leaf.mins,leaf.maxs,pts):continue
            node=-li-1;ancestors=[]
            while node in parents:
                node=parents[node];ancestors.append(node)
            if any(not contains(m.nodes[n].mins,m.nodes[n].maxs,pts)for n in ancestors):continue
            valid.append(li)
            if root_side.get(-li-1)==0:front.append(li)
        if not valid:failures.append({'cap_has_no_holder_with_valid_leaf_and_ancestor_bounds':fi,'holders':holders[fi]})
        if not front:failures.append({'cap_has_no_front_side_holder_for_stock_renderer':fi,'holders':holders[fi]})
        cap_details.append({'face':fi,'kind':'sky'if is_sky else'lit-rock','signed_area_dot_effective_plane':orientation,'holders':holders[fi],'valid_bounded_holders':valid,'front_bounded_holders':front,'lightmap_bytes':size})
    rowbytes=(w.visleafs+7)//8;oldvis=previous.models[0].visleafs
    # Determine the original leaf split from the preceding merge report's
    # original Daragoth model; unchanged node count alone cannot identify it.
    original=BSP.load(Path('C:/MSR/Portable-Package/game/msr/maps/daragoth.bsp'))
    original_winding={'negative':0,'positive':0,'degenerate':0}
    for f in original.faces:
        sign=effective_winding(original,f)
        original_winding['negative'if sign<-.01 else'positive'if sign>.01 else'degenerate']+=1
    world_winding={'negative':0,'positive':0,'degenerate':0}
    ow=original.models[0]
    for f in original.faces[ow.firstface:ow.firstface+ow.numfaces]:
        sign=effective_winding(original,f)
        world_winding['negative'if sign<-.01 else'positive'if sign>.01 else'degenerate']+=1
    oldvis=original.models[0].visleafs
    rows={i:int.from_bytes(decompress_vis(m.visdata,m.leafs[i].visofs,rowbytes),'little')for i in range(1,w.visleafs+1)}
    pvs_misses=[]
    for li in range(oldvis+1,w.visleafs+1):
        mask=rows[li]
        for detail in cap_details:
            if not any(mask&(1<<(holder-1))for holder in detail['valid_bounded_holders']):
                if len(pvs_misses)<20:pvs_misses.append({'view_leaf':li,'cap':detail['face']})
    if pvs_misses:failures.append({'new_region_cap_pvs_misses':pvs_misses})
    reciprocal=[]
    for oi in range(1,oldvis+1):
        for ni in range(oldvis+1,w.visleafs+1):
            if bool(rows[oi]&(1<<(ni-1)))!=bool(rows[ni]&(1<<(oi-1))):
                if len(reciprocal)<20:reciprocal.append([oi,ni])
    if reciprocal:failures.append({'nonreciprocal_cross_pvs':reciprocal})
    for i,item in enumerate([*m.models,*m.nodes]):
        if item.firstface<0 or item.firstface+item.numfaces>len(m.faces):failures.append({'face_range_bounds':i})
    for i,leaf in enumerate(m.leafs):
        if leaf.firstmarksurface<0 or leaf.firstmarksurface+leaf.nummarksurfaces>len(m.marksurfaces):failures.append({'marksurface_range_bounds':i})
    if any(fi<0 or fi>=len(m.faces)for fi in m.marksurfaces):failures.append({'marksurface_face_indices':True})
    if tree_order_errors(m):failures.append({'tree_order_errors':tree_order_errors(m)})
    plains_spawns=[e.pairs for e in m.entities if e.classname.startswith('ms_player') and e.get('msr_region')=='daragoth_plains']
    if plains_spawns:failures.append({'remaining_plains_player_spawns':plains_spawns})
    spawn_classes=('ms_player_begin','ms_player_spawn','ms_player_spec')
    def spawn_pool(bsp):return sorted((e.classname,e.get('origin'),e.get('message',''))for e in bsp.entities if e.classname in spawn_classes)
    original_pool=spawn_pool(original);candidate_pool=spawn_pool(m)
    if candidate_pool!=original_pool:failures.append({'original_spawn_pool_changed':{'original':original_pool,'candidate':candidate_pool}})
    closure={'required':require_sky,'samples':0,'closed_surface_samples':0,'hole_count':0,'hole_examples':[],'protected_road_occlusion_examples':[],'material_overlap_count':0,'material_overlap_examples':[]}
    if len(rock)!=131:failures.append({'lit_rock_cap_count_changed':len(rock),'expected':131})
    if require_sky:
        if not sky:failures.append({'missing_sky_closure_faces':True})
        # Sample the physical old/front section independently of the builder.
        # Solid/sky on the old side adjoining non-solid new space requires a
        # rock or SKY boundary face to avoid an uninitialized framebuffer view.
        for x in range(math.ceil(w.mins[0]+16),math.floor(w.maxs[0]-16),128):
            for z in range(3096,6848,32):
                closure['samples']+=1
                old_content=hull_point_contents(original,original.models[0].headnode[0],(x,3215.875,z),0)
                front_content=hull_point_contents(m,w.headnode[0],(x,3216.125,z),0)
                hits=[(is_sky,pts)for is_sky,pts in cap_polygons if point_in_xz_polygon(x,z,pts)]
                covered=bool(hits)
                kinds={is_sky for is_sky,pts in hits if point_in_xz_polygon(x,z,pts,strict=True)}
                if len(kinds)>1:
                    closure['material_overlap_count']+=1
                    if len(closure['material_overlap_examples'])<20:closure['material_overlap_examples'].append([x,3216,z])
                if old_content in(-2,-6)and front_content not in(-2,-6):
                    closure['closed_surface_samples']+=1
                    if not covered:
                        closure['hole_count']+=1
                        if len(closure['hole_examples'])<20:closure['hole_examples'].append({'point':[x,3216,z],'old_contents':old_content,'new_contents':front_content})
                if 1104<x<2432 and z<3584 and covered and len(closure['protected_road_occlusion_examples'])<20:
                    closure['protected_road_occlusion_examples'].append([x,3216,z])
        if closure['hole_examples']:failures.append({'uncovered_old_solid_or_sky_boundary':closure['hole_examples']})
        if closure['protected_road_occlusion_examples']:failures.append({'protected_road_render_occluded':closure['protected_road_occlusion_examples']})
        if closure['material_overlap_count']:failures.append({'rock_sky_material_overlap':closure['material_overlap_examples']})
    lower_survey={'samples':0,'hull0_sky_below_3568':0,'hull1_solid_samples':0,'sky_and_standing_solid_examples':[]}
    for x in range(-4000,4001,64):
        for z in range(3088,3568,16):
            lower_survey['samples']+=1
            h0=hull_point_contents(m,w.headnode[0],(x,3215.875,z),0)
            h1=hull_point_contents(m,w.headnode[1],(x,3215.875,z+36),1)
            if h0==-6:lower_survey['hull0_sky_below_3568']+=1
            if h1==-2:lower_survey['hull1_solid_samples']+=1
            if h0==-6 and h1==-2 and len(lower_survey['sky_and_standing_solid_examples'])<20:lower_survey['sky_and_standing_solid_examples'].append([x,3215.875,z])
    return {'caps':len(caps),'lit_rock_caps':len(rock),'sky_closure_faces':len(sky),'sky_closure':closure,'lower_boundary_hull_survey':lower_survey,'stock_winding_contract':'GL_CCW front face + GL_FRONT culling requires negative ordered polygon area against effective outward plane normal, including face.side','original_face_winding_reference':original_winding,'original_world_face_winding_reference':world_winding,'cap_details':cap_details,'new_region_pvs_rows':w.visleafs-oldvis,'cross_pvs_pairs':oldvis*(w.visleafs-oldvis),'plains_player_spawns':len(plains_spawns),'original_spawn_pool_preserved':original_pool==candidate_pool,'original_spawn_count':len(original_pool),'failures':failures,'pass':not failures}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bsp',type=Path,required=True)
    parser.add_argument('--previous',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--require-sky',action='store_true',help='Audit separate sky-closure candidate and reproduce missing-boundary failure in the prior capped BSP')
    parser.add_argument('--winding-repair',action='store_true',help='Require vertex-only cap winding repair with every other render/collision/identity input unchanged')
    args=parser.parse_args();sys.setrecursionlimit(12000)
    previous=collision.MapCollision(args.previous);candidate=collision.MapCollision(args.bsp)
    oldfinger=fingerprint(previous);newfinger=fingerprint(candidate)
    report={'candidate':candidate.summary(),'previous':previous.summary(),'collision_fingerprints':newfinger,'collision_semantics_unchanged':oldfinger==newfinger,'render':render_audit(BSP.load(args.bsp),BSP.load(args.previous),args.require_sky)}
    if args.winding_repair:
        report['winding_repair_invariants']=winding_repair_invariants(previous,candidate,BSP.load(args.previous),BSP.load(args.bsp))
    assert report['collision_semantics_unchanged'],'Render-only candidate changed collision semantics; broader map audit required'
    # Keep the original spawn/begin/arrival floor contacts, omitting the large
    # randomized precision sweep already passed by this identical hull data.
    original=collision.MapCollision(Path('C:/MSR/Portable-Package/game/msr/maps/daragoth.bsp'))
    def keyfloors(m,seam):
        out=[]
        for e in m.entities:
            if e.get('classname')in('ms_player_begin','ms_player_spawn','ms_player_spec')and e.get('origin'):
                x,y,z=map(float,e['origin'].split())
                for dx,dy in((0,0),(-64,0),(64,0),(0,-64),(0,64)):out.append((e['classname']+':'+e.get('message',''),x+dx,y+dy,z+32,z-320))
        return out
    collision.sample_floors=keyfloors
    with tempfile.TemporaryDirectory(prefix='msr-cap-audit-')as td:
        folder=Path(td);exe=collision.actual.build(folder)
        base,cases=collision.audit_original(original,exe,folder,3216)
        report['original_key_contacts']=base
        report['collision']=collision.audit_candidate(original,candidate,exe,folder,3216,(0,0,0),cases)
    report['pass']=report['render']['pass']and report['collision']['pass']and report.get('winding_repair_invariants',{'pass':True})['pass']
    report['engine_source_sha256']=hashlib.sha256((ROOT/'Engine-Source/Xash3D/engine/common/pm_trace.c').read_bytes()).hexdigest()
    report['qa_helper_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'pass':report['pass'],'candidate':candidate.summary(),'render_caps':report['render']['caps'],'render_failure_count':len(report['render']['failures']),'render_failure_examples':report['render']['failures'][:5],'collision_semantics_unchanged':report['collision_semantics_unchanged'],'report':str(args.report)},indent=2))
    if not report['pass']:raise SystemExit(1)


if __name__=='__main__':main()
