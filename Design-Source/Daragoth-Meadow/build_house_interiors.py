"""Append original-game decorative furnishings to the six private meadow houses.

The frozen map's world, collision, lighting, PVS, entities and doors remain
unchanged. This writes a separate candidate; it never stages or launches a game.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
LAB = REPO.parent / 'daragoth-development'
sys.path.insert(0, str(REPO / 'Packaging-Work/BigWorld/tools'))
from bsp30 import BSP, Entity, format_entities

BASE_SHA = 'e942e42c6112a11858148ce279c8ffbe39e769059d60cb332c396b9c1020e927'
ALLOWED_KEYS = {'classname', 'model', 'targetname', 'origin', 'angles', 'scale',
                'dmg', 'body', 'skin', 'sequence', 'frame', 'framerate',
                'rendermode', 'renderamt', 'msr_region'}
ASSET_DEPENDENCIES = {
    'models/props/shovelT.mdl':
        'ed1b7afab812d5c62f283aa2082940558b630c2cd1b9f12197b49e0052e92c68'
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def build(base, model_root, layout_sha, out):
    import house_interiors as layout
    layout_path = ROOT / 'house_interiors.py'
    require(sha(layout_path) == layout_sha, 'Authored furnishing layout changed')
    require(re.fullmatch('[0-9a-f]{64}', layout_sha), 'Pin the reviewed layout SHA256')
    out = out.resolve()
    require(out.is_relative_to((LAB / 'house-interiors').resolve()),
            'Write only to the private house-interiors lab')
    target = out / 'daragoth_meadow_house_interiors.bsp'
    report_path = out / 'house-interiors-build-report.json'
    require(not target.exists() and not report_path.exists(), 'Keep previous outputs immutable')
    require(sha(base) == BASE_SHA, 'Use the frozen north-bank successor')
    old = BSP.load(base)
    require(len(old.entities) == 1053 and len(old.models) == 166,
            'Unexpected frozen map inventory')
    require(sum(e.classname in ('func_door', 'func_door_rotating')
                for e in old.entities) == 14, 'Preserve fourteen existing doors')
    authored = layout.build_layout(model_root)
    for relative, pin in ASSET_DEPENDENCIES.items():
        dependency = (model_root / relative).resolve()
        require(dependency.is_relative_to(model_root.resolve()) and sha(dependency) == pin,
                'Required original furnishing texture companion changed')
    if isinstance(authored, dict):
        objects = authored['placements']
        metadata = {k: v for k, v in authored.items() if k != 'placements'}
    else:
        objects = authored
        metadata = {'houses': layout.HOUSE_LAYOUTS}
    require(objects and {p['house_id'] for p in objects} ==
            {'inn', 'workshop', 'cottage_south', 'cottage_north', 'bakery', 'farmhouse'},
            'Furnish all six distinct houses')
    existing_names = {e.get('targetname') for e in old.entities}
    new_entities, names = [], set()
    for item in objects:
        values = item['entity']
        require(set(values) <= ALLOWED_KEYS and values.get('classname') == 'env_model',
                'Use only supported decorative env_model keys')
        require(values.get('dmg') == '0' and values.get('framerate') == '0',
                'Decorations must remain static and nonsolid')
        name = values.get('targetname')
        require(name and name.startswith('greenhollow_interior_') and
                name not in names and name not in existing_names, 'Unique furnishing names required')
        names.add(name)
        model = (model_root / values['model']).resolve()
        require(model.is_relative_to(model_root.resolve()) and
                sha(model) == item['model_sha256'], 'Pinned original-game furnishing model changed')
        require(len(item['world_bounds']) == 2 and len(item['posed_local_bounds']) == 2,
                'Actual selected-body frame0 bounds are required')
        require(all(isinstance(v, str) and '\n' not in v and '"' not in v
                    for v in values.values()), 'Entity values must be safe ASCII strings')
        new_entities.append(Entity([[k, v] for k, v in values.items()]))
    source = base.read_bytes()
    offset, length = struct.unpack_from('<2i', source, 4)
    old_lump = source[offset:offset + length]
    require(len(re.findall(rb'\{[^{}]*\}', old_lump)) == 1053,
            'Unexpected source entity syntax')
    old_text = old_lump.rstrip(b'\0')
    new_text = format_entities(new_entities).rstrip(b'\0')
    changed = old_text + b'\n' + new_text + b'\0'
    output = bytearray(source)
    output.extend(b'\0' * (-len(output) % 4))
    struct.pack_into('<2i', output, 4, len(output), len(changed))
    output.extend(changed)
    require(output[:4] == source[:4] and output[12:len(source)] == source[12:],
            'Only the entity descriptor may change in the old file prefix')
    require(sha(base) == BASE_SHA and sha(layout_path) == layout_sha,
            'Frozen inputs changed during construction')
    out.mkdir(parents=True, exist_ok=True)
    with target.open('xb') as stream:
        stream.write(output)
    after = BSP.load(target)
    require([e.pairs for e in after.entities[:1053]] == [e.pairs for e in old.entities],
            'An old ordered entity record changed')
    require([e.pairs for e in after.entities[1053:]] == [e.pairs for e in new_entities],
            'Appended furnishing records differ')
    for index in range(1, 15):
        require(struct.unpack_from('<2i', output, 4 + index*8) ==
                struct.unpack_from('<2i', source, 4 + index*8), 'Nonentity descriptor changed')
    report = {'schema': 'daragoth-house-interiors-build-v1', 'pass': True,
              'source_sha256': BASE_SHA, 'candidate_sha256': sha(target),
              'builder_sha256': sha(Path(__file__)), 'layout_sha256': layout_sha,
              'old_entities_preserved': 1053, 'new_decorations': len(objects),
              'total_entities': len(after.entities), 'model_count': len(after.models),
              'all_fourteen_nonentity_lumps_and_descriptors_unchanged': True,
              'old_raw_entity_text_preserved': changed.startswith(old_text),
              'old_file_prefix_preserved_except_entity_descriptor': True,
              'terrain_collision_pvs_lighting_water_doors_grass_preserved': True,
              'furnishing_semantics': 'Static nonsolid original-game model decorations; no pickup, collision, loot, shops or new lighting behavior claimed.',
              'layout': metadata, 'placements': objects,
              'asset_dependencies': ASSET_DEPENDENCIES,
              'native_acceptance': 'pending', 'runtime_installation_performed': False}
    with report_path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    return {'pass': True, 'candidate_sha256': report['candidate_sha256'],
            'build_report_sha256': sha(report_path), 'decorations': len(objects)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True, type=Path)
    parser.add_argument('--model-root', required=True, type=Path)
    parser.add_argument('--layout-sha', required=True)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.base, args.model_root, args.layout_sha, args.out)))


if __name__ == '__main__':
    main()
