"""Append opted-in wilderness encounter templates to the furnished meadow.

This prepares a separate candidate from pinned static evidence and mapper keys.
It does not modify core binaries, scripts, runtime maps, or player data.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import sys
import zlib

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
LAB = REPO.parent / 'daragoth-development'
sys.path.insert(0, str(REPO / 'Packaging-Work/BigWorld/tools'))
from bsp30 import BSP, Entity, format_entities

BASE_SHA = 'cc879ec6bc9a6929f84ff0b39b04d70860dd89920f3c00c81133e18b4c97a6ab'
INTERIOR_REVIEW_SHA = 'a69daef6d036e846c6b0fa3671657ea74861c772732590eda156b1ee12a50f7f'
ASSET_REVIEW_SHA = '87f7dbe9e5e8c39a69901aca1f8994a2ea1967ba2a393f4933139769cbb21c4c'
SCRIPT_CLASSES = {
    'monsters/orc_warrior': 'msmonster_orcwarrior',
    'monsters/orc_archer': 'msmonster_orcarcher',
    'monsters/troll': 'msmonster_troll',
    'monsters/goblin': 'msmonster_goblin',
    'monsters/skeleton': 'msmonster_skeleton',
    'monsters/wolf': 'ms_npc',
    'monsters/wolf_alpha': 'ms_npc',
    'monsters/spider_mini': 'ms_npc',
    'monsters/boar': 'msmonster_boar',
    'monsters/bear_black': 'ms_npc',
}
SCRIPT_BOUNDS = {
    'monsters/orc_warrior': (32, 72), 'monsters/orc_archer': (32, 60),
    'monsters/troll': (100, 125), 'monsters/goblin': (32, 60),
    'monsters/skeleton': (32, 80), 'monsters/wolf': (36, 48),
    'monsters/wolf_alpha': (36, 48), 'monsters/spider_mini': (16, 20),
    'monsters/boar': (50, 40), 'monsters/bear_black': (64, 95),
}
CONTROLLER_KEYS = {
    'encounter': '1', 'encounter_radius': '1600',
    'encounter_keep_radius': '2400', 'encounter_idle_time': '30',
    'encounter_min_distance': '320',
}
TEMPLATE_KEYS = {
    'spawnstart': '0', 'spawnchance': '100', 'lives': '0',
    'delaylow': '90', 'delayhigh': '180', 'nplayers': '0', 'reqhp': '0',
    'params': 'set_no_roam', 'msr_region': 'daragoth_plains',
}
DESCRIPTOR_KEYS = {'encounter_width': 'script_bbox_width',
                   'encounter_height': 'script_bbox_height'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_pin(path, expected):
    require(re.fullmatch('[0-9a-f]{64}', expected) and sha(path) == expected,
            f'Frozen input changed: {path.name}')
    return json.loads(path.read_text(encoding='utf-8-sig'))


def point_text(point):
    require(len(point) == 3 and all(type(v) in (int, float) and math.isfinite(v)
                                   and abs(v) < 32767 for v in point),
            'Coordinates must be finite within widened map deltas')
    return ' '.join(format(v, '.6f').rstrip('0').rstrip('.') if v else '0'
                    for v in point)


def targetname(name, used):
    require(re.fullmatch('[a-z0-9_]+', name) and len(name.encode('ascii')) < 96,
            'Unsupported or overlong encounter identity')
    require(name not in used, 'Encounter identity conflicts with another entity')
    used.add(name)
    return name


def build(base, audit_path, audit_sha, contract_path, contract_sha,
          model_root, interior_review, out):
    out = out.resolve()
    require(out.is_relative_to((LAB / 'house-interiors-plains-enemies'
                               / 'proximity-layout' / 'candidates').resolve()),
            'Output must remain in the separate proximity candidate lab')
    target = out / 'daragoth_meadow_proximity_encounters.bsp'
    report_path = out / 'proximity-encounters-build-report.json'
    require(not target.exists() and not report_path.exists(), 'Preserve earlier outputs')
    require(sha(base) == BASE_SHA, 'Furnished meadow baseline changed')
    review = read_pin(interior_review, INTERIOR_REVIEW_SHA)
    require(review.get('pass') is True and review.get('native_visual_accepted') is True
            and review.get('candidate_sha256') == BASE_SHA,
            'Pinned house-interior acceptance required')
    audit = read_pin(audit_path, audit_sha)
    contract = read_pin(contract_path, contract_sha)
    require(contract.get('mapper_api_frozen') is True
            and contract.get('controller_keys') == CONTROLLER_KEYS
            and contract.get('template_keys') == TEMPLATE_KEYS
            and contract.get('template_descriptor_keys') == list(DESCRIPTOR_KEYS)
            and contract.get('known_script_descriptors')
            == {name: {'width': size[0], 'height': size[1]}
                for name, size in SCRIPT_BOUNDS.items()}
            and contract.get('initial_global_cap') == 16
            and contract.get('birth_interval_seconds') == 0.2,
            'Mapper API must be explicitly agreed with the new core')
    for record in contract['source_contract_inputs']:
        path = Path(record['path']).resolve()
        require(path.is_relative_to((LAB / 'proximity-encounters').resolve())
                and sha(path) == record['sha256'], 'Core mapper contract changed')
    require(bool(contract['source_contract_inputs']), 'Missing core contract binding')
    require(audit.get('pass') is True and audit.get('source_map_sha256') == BASE_SHA
            and len(audit['groups']) == 30 and len(audit['pads']) == 163,
            'Thirty zones and 163 actually checked pads required')
    require(audit['failed_pads'] == [] and len(audit['water_volumes']) == 5
            and audit['inputs_unchanged_during_verification'] is True,
            'Placement audit has unresolved pads or water inputs')
    for name, expected in audit['frozen_inputs'].items():
        path = Path(name).resolve()
        require(path.is_relative_to(LAB.resolve()) or path.is_relative_to(REPO.resolve()),
                'Placement input outside the owned source/lab')
        require(sha(path) == expected, 'Frozen placement input changed')
    scripts_sha = audit['assets']['packed_library']['sha256']
    require(sha(model_root / 'scripts.pak') == scripts_sha
            and scripts_sha == contract['packed_library_sha256'],
            'Packed original scripts changed')
    asset_review = read_pin(LAB / 'house-interiors-plains-enemies/proximity-assets'
                           / 'original-asset-availability-review.json', ASSET_REVIEW_SHA)
    require(asset_review['pass'] is True and len(asset_review['models']) == 31,
            'Complete furnishing and creature asset pins required')
    model_pins = {item['model']: {'sha256': item['sha256']}
                  for item in asset_review['models']}
    for name, item in model_pins.items():
        path = (model_root / name).resolve()
        require(path.is_relative_to(model_root.resolve())
                and sha(path) == item['sha256'], 'Required original model changed')

    old = BSP.load(base)
    require(len(old.entities) == 1138 and len(old.models) == 166,
            'Unexpected furnished baseline inventory')
    reuse = audit['controller_reuse']
    model = old.models[24]
    require(reuse['model'] == '*24'
            and old.entities[102].pairs == reuse['source_ordered_keys']
            and list(model.mins) == reuse['compiled_bounds'][0]
            and list(model.maxs) == reuse['compiled_bounds'][1]
            and list(model.origin) == reuse['compiled_pivot']
            and list(model.headnode) == reuse['compiled_headnodes'],
            'Original invisible controller donor changed')
    compiled_center = [(a + b) / 2 for a, b in zip(model.mins, model.maxs)]
    require(list(model.origin) == [0, 0, 0], 'Only this zero-pivot donor is supported')
    groups = {g['id']: g for g in audit['groups']}
    require(len(groups) == 30, 'Duplicate encounter group')
    group_counts = Counter(p['group'] for p in audit['pads'])
    require(set(groups) == set(group_counts) and
            all(1 <= n <= 32 for n in group_counts.values()), 'Invalid template capacity')
    for identity, group in groups.items():
        cap = group['local_active_cap']
        require(type(cap) is int and 1 <= cap <= group_counts[identity] <= 32,
                'Local cap must fit the authored template pool')
        require(group['region_index'] == 1 and group['controller_center_contents'] == -1,
                'Controller center must be clear in the plains')
        require(all(abs(group['center'][i] - compiled_center[i]
                        - group['controller_entity_origin'][i]) < 0.000001
                    for i in range(3)), 'Wrong compiled controller-center translation')
    dense = {'proximity_09_east_ridge_orcs', 'proximity_21_east_far_field_goblins'}
    require(all(group_counts[g] == 24 and groups[g]['local_active_cap'] == 16
                for g in dense), 'Two capped dense pools required')
    require(all(groups[g]['local_active_cap'] <= 8 for g in groups if g not in dense),
            'Unexpected population increase in other packs')
    require(Counter(p['role'] for p in audit['pads']
                    if p['group'] == 'proximity_09_east_ridge_orcs')
            == {'orc_warrior': 16, 'orc_archer': 8}
            and Counter(p['role'] for p in audit['pads']
                        if p['group'] == 'proximity_21_east_far_field_goblins')
            == {'goblin': 24}, 'Unexpected dense-pool composition')

    used = {e.get('targetname') for e in old.entities}
    appended, placements = [], []
    for identity, group in groups.items():
        name = targetname('meadow_encounter_' + identity, used)
        values = {'classname': 'msarea_monsterspawn', 'targetname': name,
                  'model': '*24', 'origin': point_text(group['controller_entity_origin']),
                  'angles': '0 0 0', 'skin': '0', 'spawnloc': '0', 'spawnstart': '0',
                  'resetwhen': '0', 'msr_region': 'daragoth_plains', **CONTROLLER_KEYS,
                  'encounter_max_active': str(group['local_active_cap'])}
        appended.append(Entity([[k, v] for k, v in values.items()]))
        placements.append({'kind': 'opted_in_controller', 'group': identity,
                           'entity': values, 'center': group['center'],
                           'template_pool_size': group_counts[identity]})
    seen_slots = {g: set() for g in groups}
    species = Counter()
    for pad in audit['pads']:
        group, slot, script = pad['group'], pad['slot'], pad['scriptfile']
        require(type(slot) is int and 0 <= slot < group_counts[group]
                and slot not in seen_slots[group], 'Invalid or duplicate slot')
        seen_slots[group].add(slot)
        require(script in SCRIPT_CLASSES and pad['supported_classname'] == SCRIPT_CLASSES[script]
                and pad['dry_feet'] is True and pad['selected_hull_contents'] == -1
                and pad['standing_hull1_contents'] == -1
                and pad['existing_static_bounds_clear'] is True
                and pad['road_lateral_distance_approx'] > 832,
                'Unknown script or incompletely checked actor pad')
        require((pad['bbox_width'], pad['bbox_height']) == SCRIPT_BOUNDS[script],
                'Exact source-supported initial script collision bounds required')
        require(len(pad['support_samples']) == 18 and len(pad['body_samples']) == 54
                and all(s['world_below'] == -2 and s['world_above'] == -1
                        and len(s['water_overlay_above']) == 5
                        and all(v[1] == -1 for v in s['water_overlay_above'])
                        for s in pad['support_samples'])
                and all(s['contents'] == -1 and len(s['water_overlay']) == 5
                        and all(v[1] == -1 for v in s['water_overlay'])
                        for s in pad['body_samples']), 'Finite dry body/floor evidence incomplete')
        name = targetname(f'meadow_enemy_{group}_{slot:02d}', used)
        values = {'classname': SCRIPT_CLASSES[script], 'targetname': name,
                  'scriptfile': script, 'spawnarea': 'meadow_encounter_' + group,
                  'origin': point_text(pad['template_origin']), 'angles': '0 180 0',
                  'encounter_width': format(pad['bbox_width'], '.6g'),
                  'encounter_height': format(pad['bbox_height'], '.6g'),
                  **TEMPLATE_KEYS}
        appended.append(Entity([[k, v] for k, v in values.items()]))
        species[pad['role']] += 1
        placements.append({'kind': 'fixed_monster_template', 'group': group, 'slot': slot,
                           'role': pad['role'], 'entity': values,
                           'source_script_bbox': [pad['bbox_width'], pad['bbox_height']],
                           'highest_support_floor': pad['highest_support_floor'],
                           'initial_road_lateral_distance_approx': pad['road_lateral_distance_approx']})
    require(all(seen_slots[g] == set(range(group_counts[g])) for g in groups),
            'Template slots are not contiguous')

    source = base.read_bytes()
    offset, length = struct.unpack_from('<2i', source, 4)
    old_text = source[offset:offset + length].rstrip(b'\0')
    changed = old_text + b'\n' + format_entities(appended).rstrip(b'\0') + b'\0'
    output = bytearray(source)
    output.extend(b'\0' * (-len(output) % 4))
    struct.pack_into('<2i', output, 4, len(output), len(changed))
    output.extend(changed)
    require(output[:4] == source[:4] and output[12:len(source)] == source[12:],
            'Source prefix changed outside the entity descriptor')
    for index in range(1, 15):
        require(struct.unpack_from('<2i', output, 4 + index * 8)
                == struct.unpack_from('<2i', source, 4 + index * 8),
                'A nonentity descriptor changed')
    require(sha(base) == BASE_SHA and sha(audit_path) == audit_sha
            and sha(contract_path) == contract_sha
            and sha(interior_review) == INTERIOR_REVIEW_SHA,
            'Inputs changed during construction')
    out.mkdir(parents=True, exist_ok=True)
    with target.open('xb') as stream:
        stream.write(output)
    after = BSP.load(target)
    require([e.pairs for e in after.entities[:1138]] == [e.pairs for e in old.entities]
            and [e.pairs for e in after.entities[1138:]] == [e.pairs for e in appended],
            'Written entity records differ')
    require(len(after.entities) == 1331 and len(after.models) == 166,
            'Unexpected output inventory')
    report = {
        'schema': 'daragoth-proximity-encounters-build-v1', 'pass': True,
        'source_sha256': BASE_SHA, 'candidate_sha256': sha(target),
        'whole_file_crc32': zlib.crc32(output) & 0xffffffff,
        'builder_sha256': sha(Path(__file__)), 'audit_sha256': audit_sha,
        'mapper_contract_sha256': contract_sha,
        'interior_native_review_sha256': INTERIOR_REVIEW_SHA,
        'scripts_sha256': scripts_sha, 'models': model_pins, 'placements': placements,
        'original_asset_availability_sha256': ASSET_REVIEW_SHA,
        'placement_support_samples': 2934, 'placement_body_samples': 8802,
        'old_ordered_entities_preserved': 1138, 'total_entities': 1331,
        'new_controllers': 30, 'new_templates': 163,
        'group_pool_counts': dict(group_counts), 'species_pool_counts': dict(species),
        'initial_managed_global_cap': 16, 'birth_interval_seconds': 0.2,
        'respawn_seconds_after_real_death': [90, 180],
        'all_fourteen_nonentity_lumps_and_descriptors_unchanged': True,
        'old_file_prefix_preserved_except_entity_descriptor': True,
        'old_raw_entity_text_preserved': True,
        'policy': 'Opted-in fixed pads, proximity hysteresis, capped paced admissions, normal death cooldowns and bounded vacancy replenishment. Dense pools are reserves, not simultaneous population or finite waves.',
        'limits': 'Static construction only. Actual new core, player/mount occupancy, scripts, grounding, cleanup, damage credit, two-player union, cap starvation, resources and compatibility require new native evidence. Protected actors may hold capacity. set_no_roam is not a pursuit leash.',
        'native_acceptance': 'pending', 'runtime_installation_performed': False,
    }
    with report_path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    return {'pass': True, 'candidate_sha256': report['candidate_sha256'],
            'build_report_sha256': sha(report_path), 'new_templates': 163,
            'new_controllers': 30, 'runtime_installation_performed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('base', 'audit', 'contract', 'model-root', 'interior-review', 'out'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--audit-sha', required=True)
    parser.add_argument('--contract-sha', required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.base, args.audit, args.audit_sha, args.contract,
                          args.contract_sha, args.model_root, args.interior_review, args.out)))


if __name__ == '__main__':
    main()
