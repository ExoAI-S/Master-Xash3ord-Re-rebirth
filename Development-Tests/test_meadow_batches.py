"""Verify preserved BSP data and compiled static meadow sector models.

Checks every source patch once, all baked root positions/normals, texture bytes,
per-submodel limits, and above-ground lighting anchors. Optional --actual-c compiles a temporary engine C
tracer in a Visual Studio environment; no games or existing builds are run.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import shutil
import struct
import sys
import tempfile

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'Packaging-Work/BigWorld/tools'))
sys.path.insert(0, str(REPO / 'Design-Source/Daragoth-Meadow'))
from bsp30 import BSP
from meadow_surface import SurfaceIndex
from test_meadow_polish import OLD_MODEL, NEW_MODEL, TEXTURES, ROOT_LIMITS
from test_meadow_polish import failure, section, sha, rotated, model_check

PREFIX = 'models/plains/meadow_sector_'
POSITION_TOLERANCE = .005
# pxstudiomdl LookupNormal reuses normals with dot > cos(2 degrees).
# Compare against frozen SMD normals, not normals already merged in the
# single-patch MDL. The .001-degree allowance covers decimal/float32 rounding.
NORMAL_MERGE_DEGREES = 2.001
LIGHTING_ANCHOR_POLICY = 'nearest_patch_to_grid_center_xy_then_index_ground_plus_64_z_rounded_4'


def batch_entity(entity):
    return entity.classname == 'env_model' and entity.get('model', '').startswith(PREFIX)


def textures(data):
    count, at = struct.unpack_from('<2i', data, 180)
    result = []
    for i in range(count):
        name, flags, width, height, pixels = struct.unpack_from('<64s4i', data, at+80*i)
        length = width*height
        if width <= 0 or height <= 0 or pixels < 0 or pixels+length+768 > len(data):
            raise ValueError('Compiled texture data out of bounds')
        result.append((name.rstrip(b'\0'), flags, width, height,
                       data[pixels:pixels+length], data[pixels+length:pixels+length+768]))
    return result


def decode_model(path):
    """Read actual command vertex/normal/UV references, with all bodyparts."""
    data = path.read_bytes()
    if data[:4] != b'IDST' or struct.unpack_from('<i',data,4)[0] != 10:
        raise ValueError('Expected GoldSrc studio v10 sector model')
    bones, bone_at = struct.unpack_from('<2i',data,140)
    if bones != 1 or struct.unpack_from('<6f',data,bone_at+64) != (0,0,0,0,0,0):
        raise ValueError('Sector model must retain one neutral bone')
    if struct.unpack_from('<i',data,148)[0] != 0 or any(v != -1 for v in struct.unpack_from('<6i',data,bone_at+40)):
        raise ValueError('Static grass must have no bone controllers')
    sequences, seq_at = struct.unpack_from('<2i',data,164)
    if sequences != 1 or struct.unpack_from('<i',data,seq_at+156)[0] != 0:
        raise ValueError('Expected one embedded idle sequence')
    blends, animation = struct.unpack_from('<2i',data,seq_at+120)
    if blends != 1 or struct.unpack_from('<6H',data,animation) != (0,0,0,0,0,0):
        raise ValueError('Static idle has a non-neutral animation channel')
    seq_bounds = struct.unpack_from('<6f',data,seq_at+96)
    body_count, body_at = struct.unpack_from('<2i',data,204)
    points = set()
    samples = set()
    submodels = []
    for i in range(body_count):
        _, count, body_base, model_at = struct.unpack_from('<64s3i',data,body_at+76*i)
        if count != 1 or body_base <= 0:
            raise ValueError('Each permanent bodypart needs one submodel and positive body base')
        record = struct.unpack_from('<64sif10i',data,model_at)
        meshes, mesh_at, nv, vertex_bones, vertex_at, nn, normal_bones, normal_at = record[3:11]
        if any(v != 0 for v in data[vertex_bones:vertex_bones+nv]+data[normal_bones:normal_bones+nn]):
            raise ValueError('Sector geometry assigned to a non-neutral bone')
        vertices = [struct.unpack_from('<3f',data,vertex_at+12*k) for k in range(nv)]
        normals = [struct.unpack_from('<3f',data,normal_at+12*k) for k in range(nn)]
        points.update(vertices)
        submitted = triangles = 0
        for j in range(meshes):
            expected_triangles, at, _, _, _ = struct.unpack_from('<5i',data,mesh_at+20*j)
            mesh_triangles = 0
            while True:
                if at < 0 or at+2 > len(data):
                    raise ValueError('Command stream outside compiled model')
                count = struct.unpack_from('<h',data,at)[0]
                at += 2
                if not count:
                    break
                count = abs(count)
                if count < 3 or at+8*count > len(data):
                    raise ValueError('Invalid compiled strip/fan length')
                for vertex, normal, s, t in struct.iter_unpack('<4h',data[at:at+8*count]):
                    if not (0 <= vertex < nv and 0 <= normal < nn):
                        raise ValueError('Compiled command vertex or normal index out of range')
                    samples.add((vertices[vertex], normals[normal], (s,t)))
                at += 8*count
                submitted += count
                mesh_triangles += count-2
            if mesh_triangles != expected_triangles:
                raise ValueError('Mesh triangle count differs from command stream')
            triangles += mesh_triangles
        if nv > 3696 or triangles > 3696 or submitted > 7392 or submitted > 16384:
            raise ValueError(f'Sector bodypart exceeds planned or renderer budget: {nv}/{triangles}/{submitted}')
        submodels.append({'bodypart':i, 'source_vertices':nv, 'triangles':triangles, 'submitted_vertices':submitted})
    if not points:
        raise ValueError('Sector model contains no geometry')
    if any(any(p[k] < seq_bounds[k]-.01 or p[k] > seq_bounds[k+3]+.01 for k in range(3)) for p in points):
        raise ValueError('Compiled idle PVS bounds do not contain model geometry')
    return {'data':data, 'textures':textures(data), 'points':points, 'samples':samples,
            'submodels':submodels, 'sequence_bounds':seq_bounds}


def smd_samples(path, texture_records):
    """Read the frozen authored normals/UVs independently of the batch builder."""
    lines=path.read_text().splitlines();start=lines.index('triangles')+1
    body=lines[start:lines.index('end',start)]
    if len(texture_records)!=1 or len(body)%4:
        raise ValueError('Expected a single-texture source SMD triangle list')
    _,_,width,height,_,_=texture_records[0]
    samples=set()
    for i in range(0,len(body),4):
        for line in body[i+1:i+4]:
            values=line.split()
            if len(values)!=9 or values[0]!='0':
                raise ValueError('Source SMD vertex must use one neutral bone')
            x,y,z,nx,ny,nz,u,v=map(float,values[1:])
            samples.add(((x,y,z),(nx,ny,nz),(round(u*width),round((1-v)*height))))
    return samples


def match_records(expected, actual, *, with_normals=False):
    """One-to-one tolerance matching using nearby 3-D bins, not rounding equality.

    Sort for stable output, but match neighboring bins so a rounding boundary
    cannot mispair roots with similar X and widely different Y coordinates.
    """
    bins = defaultdict(list)
    for number, item in enumerate(actual):
        point = item[0] if with_normals else item
        uv = item[2] if with_normals else None
        key = tuple(math.floor(v/POSITION_TOLERANCE) for v in point)+(uv,)
        bins[key].append((number,item))
    used = set()
    failures = []
    maximum = 0.
    maximum_normal = 0.
    for item in sorted(expected):
        point = item[0] if with_normals else item
        uv = item[2] if with_normals else None
        cell = tuple(math.floor(v/POSITION_TOLERANCE) for v in point)
        found = None
        for dx in (-1,0,1):
            for dy in (-1,0,1):
                for dz in (-1,0,1):
                    for number, candidate in bins.get((cell[0]+dx,cell[1]+dy,cell[2]+dz,uv),()):
                        if number in used:
                            continue
                        other = candidate[0] if with_normals else candidate
                        error = max(abs(a-b) for a,b in zip(point,other))
                        if error > POSITION_TOLERANCE:
                            continue
                        if with_normals:
                            a,b=item[1],candidate[1]
                            length=math.sqrt(sum(v*v for v in a)*sum(v*v for v in b))
                            if not length: continue
                            cosine=max(-1,min(1,sum(x*y for x,y in zip(a,b))/length))
                            normal_error=math.degrees(math.acos(cosine))
                        else: normal_error=0
                        if normal_error > NORMAL_MERGE_DEGREES:
                            continue
                        found = (number,error,normal_error)
                        break
                    if found is not None: break
                if found is not None: break
            if found is not None: break
        if found is None:
            if len(failures)<5: failures.append(item)
        else:
            used.add(found[0]); maximum=max(maximum,found[1]); maximum_normal=max(maximum_normal,found[2])
    return {'pass':len(expected)==len(actual)==len(used), 'expected':len(expected), 'compiled':len(actual),
            'matched':len(used), 'max_position_error':maximum, 'max_normal_angle_error_degrees':maximum_normal,
            'unmatched_expected_examples':failures}


def preservation(base, candidate, batch_report):
    result = section()
    old, new = base.read_bytes(), candidate.read_bytes()
    result['non_entity_lumps_identical'] = {}
    for i in range(1,15):
        a,n=struct.unpack_from('<2i',old,4+8*i);b,m=struct.unpack_from('<2i',new,4+8*i)
        same=n==m and old[a:a+n]==new[b:b+m]
        result['non_entity_lumps_identical'][str(i)]=same
        if not same: failure(result,'Non-entity lump changed',lump=i)
    if len(new)<len(old) or new[:4]!=old[:4] or new[12:len(old)]!=old[12:]:
        failure(result,'Base bytes outside entity descriptor were modified')
    old_bsp,new_bsp=BSP.load(base),BSP.load(candidate)
    expected=[e.pairs for e in old_bsp.entities if not(e.classname=='env_model' and e.get('model')==OLD_MODEL)]
    kept=[e.pairs for e in new_bsp.entities if not batch_entity(e)]
    if expected!=kept: failure(result,'Ordered non-grass entity records changed')
    entities=[e for e in new_bsp.entities if batch_entity(e)]
    models=Counter(e.get('model') for e in entities)
    reported=Counter(b['model_runtime_path'] for b in batch_report['batches'])
    if models!=reported or any(n!=1 for n in models.values()):
        failure(result,'Expected exactly one entity for every reported sector model')
    if len(entities)>130 or len(new_bsp.entities)!=len(expected)+len(entities):
        failure(result,'Sector entity count exceeds limit or replacement count is inconsistent')
    for e in entities:
        for key,value in {'dmg':'0','sequence':'0','framerate':'0','rendermode':'0','renderamt':'255','scale':'1','body':'0','skin':'0'}.items():
            if e.get(key)!=value: failure(result,'Sector entity not static/nonsolid',model=e.get('model'),key=key,value=e.get(key))
        if tuple(map(float,e.get('angles','').split()))!=(0.,0.,0.):
            failure(result,'Sector entity has an unexpected angle transform',model=e.get('model'))
    result.update({'preserved_non_grass_records':len(expected), 'sector_entities':len(entities),
                   'total_entities':len(new_bsp.entities), 'nominal_network_reserve':2047-len(new_bsp.entities)})
    result['pass']=not result['failure_count']
    return result,new_bsp,{e.get('model'):e for e in entities}


def verify_models(batch_report, patch_report, grass_model, entities, index):
    result=section()
    source=decode_model(grass_model)
    source_check, source_roots=model_check(grass_model)
    if not source_check['pass']: failure(result,'Single-patch source model failed its checker')
    bottom_uv={uv for point,normal,uv in source['samples'] if abs(point[2])<.0001}
    top_uv={uv for point,normal,uv in source['samples'] if abs(point[2])>=.0001}
    if not bottom_uv or bottom_uv&top_uv:
        raise ValueError('Cannot identify compiled roots independently from source UVs')
    if any(not(t[1]&64 and t[1]&1) or t[1]&4 for t in source['textures']):
        raise ValueError('Source grass must retain masked, scene-lit flatshade textures')
    smd_path=grass_model.with_name('meadow_grass_patch_reference.smd')
    smd_hash=sha(smd_path)
    expected_smd_hash=batch_report.get('input_hashes',{}).get(str(smd_path.resolve()))
    if smd_hash!=expected_smd_hash:
        failure(result,'Frozen source SMD hash mismatch',expected=expected_smd_hash,actual=smd_hash)
    source_samples=smd_samples(smd_path,source['textures'])
    source_match=match_records(sorted(source_samples),sorted(source['samples']),with_normals=True)
    if not source_match['pass']:
        failure(result,'Authored SMD differs from compiled single-patch geometry/UVs or normal merge contract',match=source_match)
    patches=patch_report['placements']
    ids=[i for batch in batch_report['batches'] for i in batch['patch_indices']]
    if Counter(ids)!=Counter(range(920)) or len(patches)!=920:
        failure(result,'Each of 920 patch IDs must occur exactly once')
    hashes={str(smd_path.resolve()):smd_hash}
    world_roots=[]
    errors=[]
    model_reports=[]
    textures_identical=True
    for batch in batch_report['batches']:
        path=Path(batch['model_path'])
        hashes[str(path.resolve())]=sha(path)
        if hashes[str(path.resolve())]!=batch['sha256']:
            failure(result,'Sector model hash differs from report',model=str(path))
        decoded=decode_model(path)
        entity=entities.get(batch['model_runtime_path'])
        if entity is None:
            failure(result,'Reported model entity absent',model=batch['model_runtime_path']);continue
        origin=tuple(map(float,entity.get('origin').split()))
        if max(abs(a-b) for a,b in zip(origin,batch['origin']))>.00011:
            failure(result,'Compiled entity origin differs from batch metadata',model=batch['model_runtime_path'])
        if decoded['textures']!=source['textures']:
            textures_identical=False
            failure(result,'Sector texture flags/dimensions/pixels/palette differ from source',model=str(path))
        expected_roots=[]
        expected_samples=set()
        for patch_id in batch['patch_indices']:
            if not isinstance(patch_id,int) or not 0<=patch_id<len(patches):
                failure(result,'Patch index out of bounds',index=patch_id);continue
            patch=patches[patch_id];angles=(patch['pitch'],patch.get('yaw',0),patch['roll'])
            for point in source_roots:
                delta=rotated(point,angles)
                expected_roots.append(tuple(patch['origin'][k]+delta[k] for k in range(3)))
            for point,normal,uv in source_samples:
                delta=rotated(point,angles);direction=rotated(normal,angles)
                expected_samples.add((tuple(patch['origin'][k]+delta[k]-origin[k] for k in range(3)),direction,uv))
        local_roots=sorted({point for point,normal,uv in decoded['samples'] if uv in bottom_uv})
        compiled_roots=[tuple(point[k]+origin[k] for k in range(3)) for point in local_roots]
        root_match=match_records(expected_roots,compiled_roots)
        sample_match=match_records(sorted(expected_samples),sorted(decoded['samples']),with_normals=True)
        if not root_match['pass']: failure(result,'Baked root replay differs from source patch transforms',model=str(path),match=root_match)
        if not sample_match['pass']: failure(result,'Baked vertices/normals/UVs differ from source patch transforms',model=str(path),match=sample_match)
        triangles=sum(r['triangles'] for r in decoded['submodels'])
        expected_triangles=len(batch['patch_indices'])*sum(r['triangles'] for r in source['submodels'])
        if triangles!=expected_triangles: failure(result,'Compiled sector triangle count differs from assigned patches',model=str(path))
        for point in compiled_roots:
            surface=index.at(point[0],point[1],TEXTURES)
            if surface is None:
                failure(result,'No grass surface under baked root',model=str(path),root=point);continue
            residual=point[2]-surface['z'];errors.append(residual)
            if not ROOT_LIMITS[0]<=residual<=ROOT_LIMITS[1]:
                failure(result,'Baked root outside ground-contact limits',model=str(path),root=point,residual=residual)
        world_roots.extend((batch['model_runtime_path'],point) for point in compiled_roots)
        model_reports.append({'model':batch['model_runtime_path'], 'patches':len(batch['patch_indices']),
                              'submodels':decoded['submodels'], 'compiled_roots':len(compiled_roots),
                              'root_replay':root_match, 'vertex_normal_uv_replay':sample_match,
                              'idle_bounds':decoded['sequence_bounds']})
    result.update({'patch_ids':len(ids), 'patches':len(patches), 'source_roots_per_patch':len(source_roots),
                   'compiled_root_probes':len(world_roots), 'root_uv_pairs':sorted(bottom_uv),
                   'root_height_above_ground_range':[min(errors),max(errors)] if errors else None,
                   'root_limits':ROOT_LIMITS, 'position_tolerance':POSITION_TOLERANCE,
                   'normal_merge_limit_degrees':NORMAL_MERGE_DEGREES,
                   'normal_merge_contract':'pxstudiomdl LookupNormal uses dot>cos(2 degrees); authored SMD normals are compared before either compilation merges them.',
                   'source_smd_replay':source_match,
                   'maximum_submodel_submitted_vertices':max(r['submitted_vertices'] for m in model_reports for r in m['submodels']),
                   'models':model_reports, 'texture_pixels_palettes_and_flags_identical':textures_identical})
    result['pass']=not result['failure_count']
    return result,world_roots,hashes


def verify_lighting_anchors(path, bsp, batch_report, patch_report, entities, index):
    """Replay entity-origin light sampling; bounding boxes are not sampled.

    Production R_EntityDynamicLight starts at origin+(0,0,8), tries the sky,
    then samples a 2048-unit downward ray. Verify a known lightmapped meadow
    floor and empty starts rather than treating mesh root contact as lighting.
    """
    import test_daragoth_expanded_collision as collision
    result=section();probes=[];clearances=[];patches=patch_report['placements']
    model=collision.MapCollision(path)
    grid_size=batch_report.get('grid_size')
    if grid_size!=2560:
        failure(result,'Unexpected lighting-anchor grid size',actual=grid_size)
        grid_size=2560
    if batch_report.get('lighting_anchor_policy')!=LIGHTING_ANCHOR_POLICY:
        failure(result,'Missing or incorrect top-level lighting-anchor policy')
    for batch in batch_report['batches']:
        name=batch['model_runtime_path'];entity=entities.get(name)
        ids=batch['patch_indices']
        if not ids or any(not isinstance(i,int) or not 0<=i<len(patches) for i in ids):
            failure(result,'Cannot select lighting anchor from invalid patch indices',model=name);continue
        cells={(math.floor(patches[i]['origin'][0]/grid_size),
                math.floor(patches[i]['origin'][1]/grid_size)) for i in ids}
        regions={patches[i]['region'] for i in ids}
        if len(cells)!=1 or len(regions)!=1:
            failure(result,'Sector patches must share one spatial cell and region',model=name);continue
        grid=next(iter(cells));region=next(iter(regions))
        if tuple(batch.get('grid',()))!=grid or batch.get('region')!=region:
            failure(result,'Reported sector cell or region differs from actual patches',model=name)
        center=tuple((v+.5)*grid_size for v in grid)
        anchor=min(ids,key=lambda i:(sum((patches[i]['origin'][k]-center[k])**2 for k in (0,1)),i))
        patch=patches[anchor]
        expected=(*patch['origin'][:2],round(patch['terrain_ground_z']+64,4))
        if batch.get('lighting_anchor_patch_id')!=anchor or batch.get('lighting_anchor_policy')!=LIGHTING_ANCHOR_POLICY:
            failure(result,'Lighting-anchor identity or policy differs from independent selection',model=name,expected_patch=anchor)
        if entity is None:
            failure(result,'Lighting-anchor entity is absent',model=name);continue
        origin=tuple(map(float,entity.get('origin','').split()))
        if len(origin)!=3 or max(abs(a-b) for a,b in zip(origin,expected))>.00011:
            failure(result,'Entity origin differs from nearest planted patch ground plus64',model=name,expected=expected,actual=origin)
            if len(origin)!=3:continue
        if entity.get('effects','0')!='0' or entity.get('renderfx','0')!='0':
            failure(result,'Unexpected entity lighting effect override',model=name)
        start=(origin[0],origin[1],origin[2]+8)
        for label,hull,point in [('origin',0,origin),('renderer_start',0,start),('standing_origin',1,origin)]:
            contents=model.point(hull,point)
            if contents!=-1:
                failure(result,'Lighting-anchor point is not empty',model=name,probe=label,hull=hull,contents=contents)
        # Query all upward surfaces below the start so a roof or other material
        # cannot be ignored merely by filtering for grass before selection.
        surface=index.at(start[0],start[1],max_z=start[2])
        if surface is None:
            failure(result,'Missing rendered floor below lighting anchor',model=name);continue
        face=bsp.faces[surface['face']]
        if surface['texture'] not in TEXTURES or face.lightofs<0 or 0 not in face.styles:
            failure(result,'Lighting anchor does not sample a lightmapped style0 meadow floor',model=name,surface=surface,lightofs=face.lightofs,styles=face.styles)
        clearance=start[2]-surface['z'];clearances.append(clearance)
        if abs(clearance-72)>.001 or abs(surface['z']-patch['terrain_ground_z'])>.001:
            failure(result,'Lighting sample does not lie72units above its planted ground',model=name,clearance=clearance)
        probes.append({'model':name,'anchor_patch_id':anchor,'origin':origin,'start':start,
                       'end':(start[0],start[1],start[2]-2048),'floor_z':surface['z'],
                       'floor_face':surface['face'],'floor_texture':surface['texture'],
                       'floor_lightofs':face.lightofs,'floor_styles':face.styles})
    result.update({'policy':LIGHTING_ANCHOR_POLICY,'anchors_checked':len(probes),
                   'expected_anchors':len(batch_report['batches']),
                   'renderer_start_clearance_range':[min(clearances),max(clearances)] if clearances else None,
                   'renderer_sample_contract':'ref/common/ref_light.c R_EntityDynamicLight: entity origin+8, sky ray then2048-unit downward floor ray; no bounding-box center.',
                   'engine_ref_light_sha256':sha(REPO/'Engine-Source/Xash3D/ref/common/ref_light.c'),
                   'anchors':probes})
    if len(probes)!=len(batch_report['batches']):
        failure(result,'Not every batch produced an independently checked lighting anchor')
    result['pass']=not result['failure_count']
    return result,probes


def actual_c(path, roots, patches, index, lighting_anchors):
    if shutil.which('cl.exe') is None:
        return {'status':'skipped','pass':None,'reason':'--actual-c requested but cl.exe is unavailable'}
    import test_daragoth_expanded_collision as collision
    result=section();result.update({'status':'ran','root_traces':0,'patch_center_traces':0,
                                   'lighting_anchor_traces':0,'chunk_limit':5000})
    model=collision.MapCollision(path);errors=[]
    with tempfile.TemporaryDirectory(prefix='msr-meadow-batch-qa-') as temp:
        folder=Path(temp);exe=collision.actual.build(folder)
        for start in range(0,len(roots),5000):
            info=[];cases=[]
            for name,point in roots[start:start+5000]:
                surface=index.at(point[0],point[1],TEXTURES)
                if surface is None:
                    failure(result,'Missing rendered floor for C root probe',model=name);continue
                z=surface['z'];info.append((name,point));cases.append(((point[0],point[1],z+32),(point[0],point[1],z-32)))
            for (name,point),trace in zip(info,model.traces(exe,folder,0,cases)):
                residual=point[2]-trace['end'][2];errors.append(residual)
                if trace['fraction']==1 or trace['startsolid'] or trace['allsolid'] or trace['normal'][2]<.7 or not ROOT_LIMITS[0]<=residual<=ROOT_LIMITS[1]:
                    failure(result,'Actual C hull0 baked root contact failed',model=name,residual=residual,trace=trace)
            result['root_traces']+=len(cases)
        # Centers are individual planted patches, not sector origins, which
        # may lie between patches on roads, water, or other excluded ground.
        for start in range(0,len(patches),5000):
            info=[];cases=[]
            for number,patch in enumerate(patches[start:start+5000],start):
                x,y,_=patch['origin'];surface=index.at(x,y,TEXTURES)
                if surface is None: failure(result,'Missing rendered patch-center floor',patch=number);continue
                z=surface['z']+36;info.append(number);cases.append(((x,y,z+96),(x,y,z-96)))
            for number,trace in zip(info,model.traces(exe,folder,1,cases)):
                if trace['fraction']==1 or trace['startsolid'] or trace['allsolid'] or trace['normal'][2]<.7:
                    failure(result,'Actual C standing hull1 patch-center floor failed',patch=number,trace=trace)
            result['patch_center_traces']+=len(cases)
        # Exact production fallback light-ray length and start point. These
        # traces prove an empty start and the expected floor, not sky lighting
        # or a rendered pixel's final lightstyle/color contribution.
        lighting_errors=[]
        for start in range(0,len(lighting_anchors),5000):
            info=lighting_anchors[start:start+5000]
            cases=[(p['start'],p['end']) for p in info]
            for probe,trace in zip(info,model.traces(exe,folder,0,cases)):
                error=trace['end'][2]-probe['floor_z'];lighting_errors.append(error)
                if trace['fraction']==1 or trace['startsolid'] or trace['allsolid'] or trace['normal'][2]<.7 or abs(error)>.1:
                    failure(result,'Actual C lighting-origin downward floor failed',model=probe['model'],expected_floor_z=probe['floor_z'],floor_error=error,trace=trace)
            result['lighting_anchor_traces']+=len(cases)
        result['lighting_floor_z_error_range']=[min(lighting_errors),max(lighting_errors)] if lighting_errors else None
    result['root_height_above_ground_range']=[min(errors),max(errors)] if errors else None
    result['engine_pm_trace_sha256']=sha(REPO/'Engine-Source/Xash3D/engine/common/pm_trace.c')
    result['scope']='Actual engine C static world hull0 root and lighting-origin floors and hull1 planted-patch center floors. No movement path, PVS, network packet, dynamic entity, appearance, or performance proof.'
    result['pass']=not result['failure_count']
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('base','bsp','batch-report','patch-report','grass-model','report'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--actual-c',action='store_true')
    args=parser.parse_args();sys.setrecursionlimit(20000)
    inputs={'base':args.base,'bsp':args.bsp,'batch_report':args.batch_report,'patch_report':args.patch_report,'grass_model':args.grass_model}
    if args.report.resolve() in {p.resolve() for p in inputs.values()}: parser.error('Report must not overwrite an input')
    hashes={k:sha(p) for k,p in inputs.items()};batch=json.loads(args.batch_report.read_text());patch=json.loads(args.patch_report.read_text())
    metadata=section()
    for label,expected,actual in [('batch output',batch['output_sha256'],hashes['bsp']),
                                   ('batch source map',batch['source_map_sha256'],patch['sha256']),
                                   ('batch source report',batch['source_report_sha256'],hashes['patch_report']),
                                   ('original base',patch['base_sha256'],hashes['base']),
                                   ('single-patch model',patch['grass_model_sha256'],hashes['grass_model'])]:
        if expected!=actual: failure(metadata,'Frozen metadata mismatch',input=label,expected=expected,actual=actual)
    metadata['pass']=not metadata['failure_count']
    report={'input_sha256':hashes,'metadata':metadata,'actual_c_requested':args.actual_c}
    print('Checking world/entity preservation and sector model metadata',flush=True)
    report['preservation'],bsp,entities=preservation(args.base,args.bsp,batch);index=SurfaceIndex(bsp)
    print('Checking every baked root, vertex/normal/UV and texture; all bodypart budgets',flush=True)
    report['models'],roots,model_hashes=verify_models(batch,patch,args.grass_model,entities,index)
    print('Checking each lighting anchor and lightmapped meadow floor independently',flush=True)
    report['lighting_anchors'],lighting_anchors=verify_lighting_anchors(args.bsp,bsp,batch,patch,entities,index)
    if args.actual_c:
        print('Checking optional actual C static floors in <=5000-trace chunks',flush=True)
        report['actual_c']=actual_c(args.bsp,roots,patch['placements'],index,lighting_anchors)
    else: report['actual_c']={'status':'not_requested','pass':None,'reason':'Static verifier only; no C harness compiled or run'}
    after={k:sha(p) for k,p in inputs.items()};after_models={p:sha(Path(p)) for p in model_hashes}
    report['inputs_unchanged_during_verification']=hashes==after and model_hashes==after_models
    report['batch_model_sha256']={p:h for p,h in model_hashes.items() if Path(p).suffix.lower()=='.mdl'}
    report['source_reference_sha256']={p:h for p,h in model_hashes.items() if Path(p).suffix.lower()=='.smd'}
    if hashes!=after or model_hashes!=after_models: report['changed_inputs']={'inputs':after,'models':after_models}
    report['static_pass']=report['inputs_unchanged_during_verification'] and all(report[k]['pass'] for k in ('metadata','preservation','models','lighting_anchors'))
    report['pass']=report['static_pass'] and (not args.actual_c or report['actual_c']['pass'] is True)
    report['scope']='Independent compiled batching preservation, exact patch coverage, geometry/normal/UV replay, texture bytes, bodypart budgets and root contact. Optional C floors only when explicitly run. Reduced entity count does not prove packet/frame/performance success; native evidence is required.'
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'pass':report['pass'],'static_pass':report['static_pass'],'bsp_sha256':hashes['bsp'],
                      'sectors':report['preservation']['sector_entities'],'compiled_roots':report['models']['compiled_root_probes'],
                      'root_range':report['models']['root_height_above_ground_range'],'actual_c':report['actual_c']['status'],
                      'report':str(args.report)},indent=2))
    return 0 if report['pass'] else 1


if __name__=='__main__':
    raise SystemExit(main())
