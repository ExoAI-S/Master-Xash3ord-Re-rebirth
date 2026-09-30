"""Create a sanitized continuous-world preview report from private lab evidence.

Only explicit numeric/boolean/hash/map fields leave the lab. Raw logs, player
names, FN identities, addresses, credentials, screenshots and private paths
are never included. Missing native checks remain pending rather than passing.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import zlib

ROOT=Path(__file__).resolve().parents[1]
FINAL_MAP_SHA='75920f034913b7d816f481a100d53c8c72264d691d62a3f5a43c9d426652e9f3'
FINAL_MAP_CRC=3926669937
TARGETS={'stonefaced':{'sha256':FINAL_MAP_SHA,'crc32':FINAL_MAP_CRC,'suffix':'stonefaced'},
    'skyclosed':{'sha256':'7c5b1b34ba07061f41cb139de4ec5b16df90453f64649c739318060b5ee1f6a5','crc32':1087111570,'suffix':'skyclosed'},
    'capped':{'sha256':'858bc81b01d4d9167c28b180cc8b695993977e0b6889c8717c27c08165455353','crc32':2976391842,'suffix':'capped'}}
REGIONS={'daragoth','daragoth_plains'}
NUM=r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)'
PLAYER=re.compile(r'^\s*player (\d+) (.+?): region (daragoth(?:_plains)?) at \(('+NUM+') ('+NUM+') ('+NUM+r')\)')
CHANGE=re.compile(r'^\s*MSR: (.+?) region (none|daragoth|daragoth_plains) -> (daragoth|daragoth_plains)(?:\s|$)')
MOUNT=re.compile(r'^\s*Mount (\d+) rider=(\d+) owner=(\d+) solid=(\d+) xyz=('+NUM+'),('+NUM+'),('+NUM+r') seq=(\d+)')
SPEED=re.compile(r'^\s*rider status=\d+ physics=\d+ view=('+NUM+') speed=('+NUM+') effect-percent='+NUM+r' hull='+NUM+r'\.\.'+NUM)
XYZ=re.compile(r'^\s*rider xyz=('+NUM+'),('+NUM+'),('+NUM+') velocity='+NUM+','+NUM+','+NUM)
MARKER=re.compile(r'^\s*(DC_(?:MOUNTED_NORTH|MOUNTED_SOUTH|MOUNTED_RETURN|START|END|CLIFF_LEFT|CLIFF_RIGHT|CLIFF_BACK))\s*$')

def read(path):return json.loads(path.read_text(encoding='utf8'))
def digest(path):
    raw=path.read_bytes()
    return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
def finite(values):
    v=[float(x) for x in values]
    if not all(math.isfinite(x) and abs(x)<=65536 for x in v):raise ValueError('Diagnostic number outside report bounds')
    return v

def native_log(path):
    """Parse only known diagnostic formats; identity matching is memory-only."""
    lines=path.read_text(encoding='utf8',errors='replace').splitlines()
    names={}
    for line in lines:
        m=PLAYER.match(line)
        if m:names[m[2]]=int(m[1])
    transitions=[];positions=[];mounted={};horse_riders={};riders=[];speeds=[];markers=Counter();owner_matches=0;dismounts=0
    current_rider=None;placed_commands=0;map_starts=Counter()
    for line in lines:
        m=PLAYER.match(line)
        if m:
            positions.append({'slot':int(m[1]),'region':m[3],'origin':finite(m.group(4,5,6))});continue
        m=CHANGE.match(line)
        if m:
            slot=names.get(m[1]);mode='mounted' if mounted.get(slot) is True else 'on_foot' if mounted.get(slot) is False else 'unclassified'
            transitions.append({'slot':slot,'from_region':m[2],'to_region':m[3],'mode':mode});continue
        m=MOUNT.match(line)
        if m:
            horse,slot=int(m[1]),int(m[2]);previous=horse_riders.get(horse)
            if previous and previous!=slot:mounted[previous]=False;dismounts+=1
            horse_riders[horse]=slot;current_rider=slot if slot else None
            if slot:
                mounted[slot]=True
                if int(m[3])==slot:owner_matches+=1
            continue
        m=SPEED.match(line)
        if m:speeds.append({'slot':current_rider,'view_height':finite([m[1]])[0],'horizontal_speed':finite([m[2]])[0]});continue
        m=XYZ.match(line)
        if m:riders.append({'slot':current_rider,'origin':finite(m.group(1,2,3))});continue
        m=MARKER.match(line)
        if m:markers[m[1]]+=1;continue
        # Count diagnostic placement separately: these lines never establish
        # a walking/ride pass and their command text is never copied.
        if line.lstrip().startswith('Mount place: player '):placed_commands+=1
        if line.strip()=='Mount lifecycle: ownership, duplicate denial, airborne denial and cleanup PASS.':markers['mount_lifecycle_pass']+=1
        if line.lstrip().startswith('MSR: 2 regions active on daragoth'):map_starts['daragoth']+=1
    return {'region_transitions':transitions,'player_positions':positions,'rider_positions':riders,
            'rider_speed_samples':speeds,'markers':dict(markers),'diagnostic_placements':placed_commands,
            'map_start_counts':dict(map_starts),'owner_link_samples':owner_matches,'dismount_clear_samples':dismounts}

def review_native(review,observations,expected_sha=FINAL_MAP_SHA):
    """Allowlisted manual view confirmations supplement actual log telemetry."""
    verified=review.get('candidate_sha256')==expected_sha
    def section(name,keys):
        source=review.get(name,{}) if verified else {}
        out={key:source.get(key) if isinstance(source.get(key),bool) else None for key in keys}
        out['status']='pass' if out and all(v is True for v in out.values()) else 'fail' if any(v is False for v in out.values()) else 'pending'
        return out
    fresh=section('fresh_character_start',['original_valley_visible','original_region'])
    raw=review.get('fresh_character_start',{}) if verified else {}
    origin=raw.get('origin')
    fresh['origin']=finite(origin) if isinstance(origin,list) and len(origin)==3 else None
    fresh['origin_recorded']=fresh['origin'] is not None
    fresh['independent_new_profile']=raw.get('independent_new_profile') if isinstance(raw.get('independent_new_profile'),bool) else None
    fresh['expected_original_begin_origin']=[-864,-3856,3200]
    fresh['region']='daragoth' if raw.get('region')=='daragoth' else None
    fresh['region_entry_observed']=any(e['from_region']=='none' and e['to_region']=='daragoth' for o in observations for e in o['region_transitions'])
    if fresh['status']=='pass' and not(fresh['region']=='daragoth' and fresh['region_entry_observed']):fresh['status']='pending'
    if expected_sha==FINAL_MAP_SHA and fresh['status']=='pass' and fresh['independent_new_profile'] is not True:
        fresh['status']='pending'
    foot=section('on_foot',['north','south','ordinary_movement','no_map_load','no_fade'])
    mounted=section('mounted',['north','south','ordinary_movement','no_map_load','no_fade','remote_seated_rider','walk_320','gallop_520','dismount_cleared'])
    visual=section('visual',['cap_cliffs_visible','road_aperture_clear','original_guards_visible','scenery_visible'])
    raw_visual=review.get('visual',{}) if verified else {}
    visual['no_stale_frame_sky']=raw_visual.get('no_stale_frame_sky') if isinstance(raw_visual.get('no_stale_frame_sky'),bool) else None
    shutdown=section('shutdown',['both_clients_quit_normally'])
    transitions=[e for o in observations for e in o['region_transitions']]
    positions=[e for o in observations for e in o['player_positions']]
    riders=[e for o in observations for e in o['rider_positions']]
    crossing_slots={e['slot'] for e in positions if e['slot'] is not None}
    both_region_slots={slot for slot in crossing_slots if {e['region'] for e in positions if e['slot']==slot}>=REGIONS}
    transition_slots={slot for slot in crossing_slots if {(e['from_region'],e['to_region']) for e in transitions if e['slot']==slot}>={('daragoth','daragoth_plains'),('daragoth_plains','daragoth')}}
    foot['loaded_character_both_region_telemetry']=bool(both_region_slots&transition_slots)
    if foot['status']=='pass' and not foot['loaded_character_both_region_telemetry']:foot['status']='pending'
    seam_riders={slot for slot in crossing_slots if any(e['slot']==slot and 1400<=e['origin'][0]<=1650 and e['origin'][1]<3216 for e in riders)
        and any(e['slot']==slot and 1400<=e['origin'][0]<=1650 and e['origin'][1]>3216 for e in riders)}
    mounted['loaded_rider_both_sides_and_regions']=bool(seam_riders&both_region_slots&transition_slots)
    mounted['owner_link_observed']=any(o['owner_link_samples'] for o in observations)
    mounted['dismount_clear_observed']=any(o['dismount_clear_samples'] for o in observations)
    final_speeds=[e['horizontal_speed'] for o in observations for e in o['rider_speed_samples']]
    mounted['final_candidate_walk_320_observed']=any(abs(v-320)<.01 for v in final_speeds)
    mounted['final_candidate_gallop_520_observed']=any(abs(v-520)<.01 for v in final_speeds)
    if mounted['final_candidate_walk_320_observed'] and mounted['final_candidate_gallop_520_observed']:
        mounted['speed_limit_scope']='Final candidate native ride telemetry.'
    # DC_* echoes alone only prove that a config ran. A failed login can emit
    # every marker, so they must never satisfy mounted crossing evidence.
    if mounted['status']=='pass' and not(mounted['loaded_rider_both_sides_and_regions'] and mounted['owner_link_observed']):mounted['status']='pending'
    return {'review_candidate_matches':verified,'fresh_character_start':fresh,'on_foot':foot,
            'mounted':mounted,'visual':visual,'shutdown':shutdown}

def generate(lab,native_paths,review_path,out,kind='stonefaced'):
    out=out.resolve();target=TARGETS[kind];suffix=target['suffix']
    qa=read(lab/('expanded-daragoth-'+suffix+'-final-qa.json'))
    build=read(lab/('expanded/continuous-join-'+suffix+'-report.json'))
    engine=read(lab/'engine-build-report.json')
    candidate=lab/('expanded/daragoth_expanded_'+suffix+'.bsp')
    actual=digest(candidate);crc=zlib.crc32(candidate.read_bytes())&0xffffffff
    if actual['sha256']!=target['sha256'] or crc!=target['crc32']:raise ValueError('Candidate differs from frozen native QA target')
    if any(x.get('sha256')!=target['sha256'] for x in [qa['candidate'],build['output']]):raise ValueError('Evidence candidate hashes disagree')
    if not qa.get('pass') or not build['verification']['failures']==[]:raise ValueError('Final QA did not pass')
    if qa['engine_source_sha256']!=engine['source_trace_sha256']:raise ValueError('Engine source hash differs between QA and build')
    brush_winding=None
    winding_path=lab/'brush-cap-winding-diagnosis.json'
    if winding_path.exists():
        winding=read(winding_path)
        measurement=next((m for m in winding.get('measurements',{}).values() if m.get('sha256')==target['sha256']),None)
        if measurement and measurement.get('join_faces'):
            counts=measurement['join_faces']['counts']
            brush_winding={'original_world_clockwise_faces':winding['measurements']['original']['world_faces']['counts']['negative'],
                'join_clockwise_faces':counts['negative'],'join_counterclockwise_faces':counts['positive'],
                'join_degenerate_faces':counts['degenerate'],
                'pass':counts['positive']==0 and counts['degenerate']==0}
            if kind=='stonefaced':brush_winding['material_ray_samples_pass']=winding.get('v4_material_ray_sample_pass') is True
    observations=[native_log(p) for p in native_paths]
    review=read(review_path) if review_path else {}
    native=review_native(review,observations,target['sha256'])
    transitions=[e for o in observations for e in o['region_transitions']]
    positions=[e for o in observations for e in o['player_positions']]
    markers=Counter()
    for o in observations:markers.update(o['markers'])
    seam=qa['collision']['seam'];render=qa['render'];movement=qa['collision']['actual_walk_move_replay']
    runtime=lab/'runtime/game'
    files={}
    runtime_map=runtime/'msr/maps/daragoth.bsp'
    runtime_map_matches=runtime_map.exists() and digest(runtime_map)['sha256']==target['sha256']
    # Historical targets deliberately remain reportable after a later map is
    # staged. Current native acceptance additionally checks the actual alias.
    if kind=='stonefaced' and native_paths and not runtime_map_matches:
        raise ValueError('Runtime daragoth alias differs from the frozen native QA target')
    if runtime_map_matches:files['runtime_world_bsp']=digest(runtime_map)
    for label,path in [('engine_debug_dll',runtime/'xash.dll'),('server_debug_dll',runtime/'msr/dlls/ms.dll'),('client_debug_dll',runtime/'msr/cl_dlls/client.dll')]:
        if path.exists():files[label]=digest(path)
    if 'engine_debug_dll' in files:
        expected=next(a['sha256'] for a in engine['artifacts'] if Path(a['path']).name=='xash.dll')
        if files['engine_debug_dll']['sha256']!=expected:raise ValueError('Runtime engine differs from frozen debug artifact')
    scripts=runtime/'msr/scripts.pak'
    if scripts.exists():files['scripts']={**digest(scripts),'crc32':zlib.crc32(scripts.read_bytes())&0xffffffff}
    speed_evidence=None
    earlier_speed=lab/'expanded-ride-native.log'
    earlier_report=ROOT/'Development-Tests/Reports/daragoth-capped-preview-20260929.json'
    if kind=='stonefaced' and earlier_speed.exists() and earlier_report.exists():
        prior=read(earlier_report);speed=native_log(earlier_speed)
        labels=('engine_debug_dll','server_debug_dll','client_debug_dll','scripts')
        same_artifacts=all(files.get(label,{}).get('sha256')==prior.get('files',{}).get(label,{}).get('sha256')
            and files.get(label,{}).get('sha256') is not None for label in labels)
        samples=speed['rider_speed_samples']
        speed_evidence={'scope':'Earlier capped-map native ride test with matching frozen DLLs/scripts; separate from final-map crossing evidence.',
            'source_candidate_sha256':prior['candidate']['sha256'],'archive_digest':digest(earlier_speed),
            'same_frozen_artifacts':same_artifacts,'rider_speed_samples':samples,
            'walk_320_observed':same_artifacts and any(abs(e['horizontal_speed']-320)<.01 for e in samples),
            'gallop_520_observed':same_artifacts and any(abs(e['horizontal_speed']-520)<.01 for e in samples),
            'dismount_clear_samples':speed['dismount_clear_samples']}
        native['mounted'].setdefault('speed_limit_scope','Earlier capped-map test with identical frozen DLLs/scripts; final-map seam telemetry reported separately.')
    baseline=read(ROOT/'Development-Tests/Reports/daragoth-plains-preview-20260929.json')['baseline_commit']
    report={'schema_version':2,'scope':'Isolated continuous Daragoth development preview; no public release, live FN or main installation changes.',
        'candidate_kind':kind,
        'baseline_commit':baseline,'build':'MSVC Win32 Debug engine and matching client/server DLLs',
        'runtime_map_alias':'daragoth','runtime_alias_matches_candidate':runtime_map_matches,'candidate':{**actual,'crc32':crc},'files':files,
        'engine':{k:engine[k] for k in ['base_engine_commit','base_engine_build_number','source_trace_sha256','architecture','pointer_size','build_type','exports_match','engine_header_interfaces_changed']},
        'geometry':{'seam_y':build['seam_world_y'],'plains_offset':build['plains_offset'],
            'original_bsp_sha256':build['original_bsp_sha256'],'original_ent_sha256':build['original_ent_sha256'],
            'terrain_generator_sha256':build['variant']['frozen_generator_sha256'],
            'original_start_pool_only':build['original_start_region_only'],'global_game_master_count':build['global_game_master_count'],
            'join_faces':render['caps'],'lit_rock_caps':render.get('lit_rock_caps',render['caps']),
            'sky_closure_faces':render.get('sky_closure_faces',0),'cap_material':build['visible_caps']['material'],
            'stock_brush_winding_corrected':build['visible_caps'].get('stock_brush_winding_corrected',False),
            'cap_material_original_procedural':build['visible_caps']['material']=='DPROCK',
            'deralia_destination':build['deralia_destination'],'counts':build['output']['counts']},
        'collision':{'pass':qa['collision']['pass'],'all_four_hull_semantics_unchanged':qa['collision_semantics_unchanged'],
            'fingerprints':qa['collision_fingerprints'],'seam_floor_checks':sum(h['ground_checks'] for h in seam),
            'seam_movement_checks':sum(h['movement_checks'] for h in seam),'actual_walk_move_frames':movement['frames'],
            'actual_walk_move_speeds':movement['speeds'],'actual_walk_move_pass':movement['pass'],
            'original_point_checks':sum(h['point_checks'] for h in qa['collision']['preserved_geometry']),
            'incremental_original_contact_checks':sum(h['contact_checks'] for h in qa['collision']['preserved_geometry'])},
        'cap_visibility':{'pass':render['pass'],'caps':render['caps'],'new_region_rows':render['new_region_pvs_rows'],
            'cross_pvs_pairs_checked':render['cross_pvs_pairs'],
            'all_caps_have_valid_bounded_front_holder':all(d['front_bounded_holders'] for d in render['cap_details']),
            'all_caps_match_stock_clockwise_winding':all(d.get('signed_area_dot_effective_plane',0)<0 for d in render['cap_details']),
            'new_region_player_spawns':render['plains_player_spawns'],'failure_count':len(render['failures'])},
        'stock_brush_winding':brush_winding,
        'sky_coverage':{'required':render.get('sky_closure',{}).get('required',False),
            'samples':render.get('sky_closure',{}).get('samples',0),
            'hole_count':render.get('sky_closure',{}).get('hole_count'),
            'rock_sky_overlap_count':render.get('sky_closure',{}).get('material_overlap_count'),
            'protected_road_occlusion_count':len(render.get('sky_closure',{}).get('protected_road_occlusion_examples',[])),
            'road_band_min_sky_z':build['visible_caps'].get('sky_closure_road_band_min_z')},
        'native':native,
        'earlier_native_speed_evidence':speed_evidence,
        'native_log_evidence':{'archive_count':len(observations),'region_transitions':transitions,'player_positions':positions,
            'rider_speed_samples':[e for o in observations for e in o['rider_speed_samples']],
            'rider_positions':[e for o in observations for e in o['rider_positions']],
            'markers':dict(markers),'diagnostic_placements':sum(o['diagnostic_placements'] for o in observations)},
        'limitations':['All regions stay loaded via ms_region_unload_time 0; adjacency-aware preloading is deferred.',
            'Transient horse ownership; FN horse possession persistence is not implemented.',
            'Standing-player collision hull while mounted.',
            'The original low sky ceiling and remote Deralia entrance scene need further visual work.',
            'Broad flat gray cliff facings and jagged cut silhouettes need authored relief and transition landscaping.',
            'Regional quests, external map travel and performance on other PCs have not been tested.',
            'Public installation and release remain outside this private-preview report.'],
        'privacy':'Only allowlisted telemetry and review booleans are stored; raw logs, names, profiles, credentials, screenshots and private paths are excluded.'}
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    return {'report':out.relative_to(ROOT).as_posix(),'native':{k:v['status'] for k,v in native.items() if isinstance(v,dict) and 'status' in v}}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--lab',type=Path,default=ROOT.parent/'daragoth-development')
    p.add_argument('--native-log',type=Path,action='append',default=[]);p.add_argument('--native-review',type=Path)
    p.add_argument('--candidate',choices=sorted(TARGETS),default='stonefaced')
    p.add_argument('--out',type=Path,default=ROOT/'Development-Tests/Reports/daragoth-continuous-preview-20260929.json')
    a=p.parse_args();print(json.dumps(generate(a.lab,a.native_log,a.native_review,a.out,a.candidate),indent=2))
if __name__=='__main__':main()
