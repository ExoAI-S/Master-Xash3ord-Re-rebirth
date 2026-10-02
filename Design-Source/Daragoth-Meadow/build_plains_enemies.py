"""Append eight existing scripted wilderness enemies after interior acceptance.

Four fixed spawners reuse an existing invisible, nonsolid compiled cube. Only
the entity lump changes; this cannot stage a map, change scripts or start a game.
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

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
LAB = REPO.parent / 'daragoth-development'
sys.path.insert(0, str(REPO / 'Packaging-Work/BigWorld/tools'))
from bsp30 import BSP, Entity, format_entities

BASE_SHA = 'cc879ec6bc9a6929f84ff0b39b04d70860dd89920f3c00c81133e18b4c97a6ab'
AUDIT_SHA = '4b3fea8c5be725df3160b369920211c90148e09d5f883f427654c6a4a9f77c87'
SCRIPT_CLASSES = {'monsters/orc_warrior': 'msmonster_orcwarrior',
                  'monsters/orc_archer': 'msmonster_orcarcher',
                  'monsters/troll': 'msmonster_troll',
                  'monsters/goblin': 'msmonster_goblin',
                  'monsters/skeleton': 'msmonster_skeleton'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def origin(point):
    require(all(math.isfinite(v) and abs(v) < 32767 for v in point),
            'Bigworld coordinates must be finite and within the widened delta range')
    return ' '.join(format(v, '.6f').rstrip('0').rstrip('.') if v else '0' for v in point)


def build(base, audit_path, model_root, interior_review, review_sha, out):
    out = out.resolve()
    require(out.is_relative_to((LAB / 'house-interiors-plains-enemies').resolve()),
            'Output must remain in the separate private enemy lab')
    target = out / 'daragoth_meadow_furnished_enemies.bsp'
    report_path = out / 'plains-enemies-build-report.json'
    require(not target.exists() and not report_path.exists(), 'Preserve previous outputs')
    require(sha(base) == BASE_SHA and sha(audit_path) == AUDIT_SHA,
            'Frozen furnishing map or placement audit changed')
    require(re.fullmatch('[0-9a-f]{64}', review_sha) and sha(interior_review) == review_sha,
            'Pin the completed interior review')
    review = json.loads(interior_review.read_text(encoding='utf-8-sig'))
    require(review.get('pass') is True and review.get('native_visual_accepted') is True
            and review.get('candidate_sha256') == BASE_SHA,
            'Finish the house furnishing native review before building enemies')
    audit = json.loads(audit_path.read_text(encoding='utf-8-sig'))
    require(audit['pass'] is True and len(audit['pads']) == 8 and
            audit['sample_summary']['world_nonempty'] == 0 and
            audit['sample_summary']['translated_water_hits'] == 0,
            'Eight dry, supported, finite checked spawn pads required')
    require(sha(model_root / 'scripts.pak') == audit['assets']['library_sha256'],
            'Use the existing frozen script library without changes')
    for name, item in audit['assets']['models'].items():
        path = (model_root / name).resolve()
        require(path.is_relative_to(model_root.resolve()) and sha(path) == item['sha256'],
                'A required original monster model changed')
    old = BSP.load(base)
    require(len(old.entities) == 1138 and len(old.models) == 166,
            'Expected furnished baseline inventory')
    reuse = audit['controller_reuse']
    require(old.entities[102].pairs == reuse['source_ordered_keys'] and
            reuse['model_key'] == '*24', 'Original controller donor changed')
    model = old.models[24]
    require(list(model.mins) == reuse['compiled_mins'] and
            list(model.maxs) == reuse['compiled_maxs'] and
            list(model.origin) == reuse['compiled_pivot'] and
            list(model.headnode) == reuse['headnodes'], 'Existing inline controller model changed')
    counts = Counter(p['group'] for p in audit['pads'])
    require(counts == {'east_orcs': 3, 'west_goblins': 2,
                       'north_troll': 1, 'ruins_skeletons': 2}, 'Unexpected encounter groups')
    require(all(0 < n <= 32 for n in counts.values()), 'Spawner slot capacity exceeded')
    entities, placements = [], []
    used = {e.get('targetname') for e in old.entities}
    for group, placement in reuse['proposed_new_controller_placements'].items():
        name = 'meadow_encounter_' + group
        require(name not in used, 'Encounter controller name conflicts')
        used.add(name)
        values = {'classname': 'msarea_monsterspawn', 'targetname': name,
                  'model': '*24', 'origin': origin(placement['controller_entity_origin']),
                  'angles': '0 0 0', 'skin': '0', 'spawnloc': '0', 'spawnstart': '0',
                  'resetwhen': '0', 'msr_region': 'daragoth_plains'}
        entities.append(Entity([[k, v] for k, v in values.items()]))
        placements.append({'kind': 'fixed_invisible_controller', 'group': group,
                           'entity': values, 'hidden_cube_center': placement['desired_hidden_cube_center'],
                           'maximum_simultaneous_new_monsters': counts[group]})
    species_count = Counter()
    for pad in audit['pads']:
        script = pad['scriptfile']
        require(script in SCRIPT_CLASSES and pad['dry_feet'] is True and
                pad['standing_hull1_contents'] == -1, 'Unknown script or invalid pad')
        species_count[pad['role']] += 1
        name = f'meadow_enemy_{pad["group"]}_{pad["role"]}_{species_count[pad["role"]]}'
        require(name not in used, 'Monster targetname conflicts')
        used.add(name)
        values = {'classname': SCRIPT_CLASSES[script], 'targetname': name,
                  'scriptfile': script, 'spawnarea': 'meadow_encounter_' + pad['group'],
                  'origin': origin(pad['template_origin']), 'angles': '0 180 0',
                  'spawnstart': '0', 'spawnchance': '100', 'lives': '0',
                  'delaylow': '90', 'delayhigh': '180', 'nplayers': '1', 'reqhp': '0',
                  'params': 'set_no_roam', 'msr_region': 'daragoth_plains'}
        entities.append(Entity([[k, v] for k, v in values.items()]))
        placements.append({'kind': 'monster_template', 'group': pad['group'], 'entity': values,
                           'expected_script_bounds': [pad['bbox_width'], pad['bbox_height']],
                           'baseline_script_stats': audit['baseline_stats'][script],
                           'highest_support_floor': pad['highest_support_floor'],
                           'initial_road_lateral_distance_approx': pad['road_lateral_distance_approx']})
    require(len(entities) == 12, 'Exactly four controllers and eight templates required')
    source = base.read_bytes()
    offset, length = struct.unpack_from('<2i', source, 4)
    old_text = source[offset:offset+length].rstrip(b'\0')
    changed = old_text + b'\n' + format_entities(entities).rstrip(b'\0') + b'\0'
    output = bytearray(source)
    output.extend(b'\0' * (-len(output) % 4))
    struct.pack_into('<2i', output, 4, len(output), len(changed))
    output.extend(changed)
    require(output[:4] == source[:4] and output[12:len(source)] == source[12:],
            'Source prefix changed outside the entity descriptor')
    require(sha(base) == BASE_SHA and sha(audit_path) == AUDIT_SHA and
            sha(interior_review) == review_sha, 'Inputs changed during construction')
    out.mkdir(parents=True, exist_ok=True)
    with target.open('xb') as stream:
        stream.write(output)
    after = BSP.load(target)
    require([e.pairs for e in after.entities[:1138]] == [e.pairs for e in old.entities],
            'An original or furnished entity changed')
    require([e.pairs for e in after.entities[1138:]] == [e.pairs for e in entities],
            'Encounter records differ')
    for index in range(1, 15):
        require(struct.unpack_from('<2i', output, 4+index*8) ==
                struct.unpack_from('<2i', source, 4+index*8), 'Nonentity descriptor changed')
    report = {'schema': 'daragoth-plains-enemies-build-v1', 'pass': True,
              'source_sha256': BASE_SHA, 'candidate_sha256': sha(target),
              'builder_sha256': sha(Path(__file__)), 'audit_sha256': AUDIT_SHA,
              'interior_native_review_sha256': review_sha,
              'scripts_sha256': audit['assets']['library_sha256'],
              'models': audit['assets']['models'], 'placements': placements,
              'old_ordered_entities_preserved': 1138, 'total_entities': 1150,
              'all_fourteen_nonentity_lumps_and_descriptors_unchanged': True,
              'old_file_prefix_preserved_except_entity_descriptor': True,
              'old_raw_entity_text_preserved': True, 'new_templates': 8, 'new_controllers': 4,
              'group_counts': dict(counts), 'maximum_simultaneous_new_enemies': 8,
              'respawn_seconds': [90, 180], 'controller_model_reused': '*24',
              'policy': 'Fixed dry pads, normal baseline scripts, deterministic initial species, no random placement, reset waves, boss keys, outputs or multipliers. set_no_roam suppresses wandering but does not prevent pursuit.',
              'limits': 'Finite static proposal; native script spawns, grounding, attacks, lifecycle, route and resource behavior remain pending. Initial separation is not a hard leash or town safety guarantee.',
              'native_acceptance': 'pending', 'runtime_installation_performed': False}
    with report_path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, indent=2); stream.write('\n')
    return {'pass': True, 'candidate_sha256': report['candidate_sha256'],
            'build_report_sha256': sha(report_path), 'new_templates': 8, 'new_controllers': 4}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True, type=Path)
    parser.add_argument('--audit', required=True, type=Path)
    parser.add_argument('--model-root', required=True, type=Path)
    parser.add_argument('--interior-review', required=True, type=Path)
    parser.add_argument('--review-sha', required=True)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.base, args.audit, args.model_root, args.interior_review,
                          args.review_sha, args.out)))


if __name__ == '__main__':
    main()
