"""Restore the meadow creek using translated instances of its compiled water brush.

Only the entity lump changes. Four touching volumes cover the wider meadow
channel while their outer edges remain buried in the banks. Existing terrain,
bridge geometry, collision hulls, lighting, textures and grass stay untouched.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'Packaging-Work/BigWorld/tools'))
from bsp30 import BSP, Entity, format_entities

BASE_SHA256 = '7db33aa84ff9f032d1267e3d37d2795e959e414c262dcb896c83a3169c1e5570'
Y_SHIFTS = (-1140, -380, 380, 1140)
SURFACE_RAISE = 32


def sha(data):
    return hashlib.sha256(data).hexdigest()


def lumps(data):
    return {str(i): sha(data[offset:offset + size])
            for i in range(15)
            for offset, size in [struct.unpack_from('<2i', data, 4 + 8 * i)]}


def build(base: Path, out: Path):
    data = base.read_bytes()
    if sha(data) != BASE_SHA256:
        raise ValueError('Use the accepted whole-map meadow BSP as the frozen base')
    target = out / 'daragoth_meadow_creek.bsp'
    if target.resolve() == base.resolve():
        raise ValueError('The frozen base cannot be overwritten')
    bsp = BSP.load(base)
    matches = [(i, e) for i, e in enumerate(bsp.entities)
               if e.classname == 'func_water' and
               e.get('msr_region') == 'daragoth_plains']
    if len(matches) != 1:
        raise ValueError('Expected exactly one plains creek water entity')
    index, original = matches[0]
    if original.get('model') != '*162':
        raise ValueError('The accepted compiled creek model changed')
    origin = tuple(map(float, original.get('origin').split()))
    model = bsp.models[162]
    names = {e.get('targetname') for e in bsp.entities}
    waters = []
    for n, dy in enumerate(Y_SHIFTS):
        name = f'plains_creek_water_{n:02d}'
        if name in names:
            raise ValueError('Creek targetname is already in use')
        water = Entity([pair.copy() for pair in original.pairs])
        water.set('origin', ' '.join(f'{v:g}' for v in
                                    (origin[0], origin[1] + dy, origin[2] + SURFACE_RAISE)))
        water.set('targetname', name)
        # CBaseDoor::Spawn uses negative skin as liquid contents and SOLID_NOT.
        water.set('skin', '-3')
        water.set('spawnflags', '0')
        water.set('rendermode', '2')
        water.set('renderamt', '120')
        water.set('WaveHeight', '0')
        waters.append(water)
    entities = list(bsp.entities)
    entities[index] = waters[0]
    entities.extend(waters[1:])
    output = bytearray(data)
    output.extend(b'\0' * (-len(output) % 4))
    entity_at = len(output)
    entity_data = format_entities(entities)
    output.extend(entity_data)
    struct.pack_into('<2i', output, 4, entity_at, len(entity_data))
    before, after = lumps(data), lumps(output)
    if any(before[str(i)] != after[str(i)] for i in range(1, 15)):
        raise ValueError('A non-entity lump changed')
    if output[:4] != data[:4] or output[12:len(data)] != data[12:]:
        raise ValueError('Existing BSP bytes changed outside the entity descriptor')
    if sha(base.read_bytes()) != BASE_SHA256:
        raise ValueError('Base changed during build')
    out.mkdir(parents=True, exist_ok=True)
    target.write_bytes(output)
    report = {
        'base_sha256': BASE_SHA256, 'output_sha256': sha(output),
        'base_entities': len(bsp.entities), 'total_entities': len(entities),
        'preserved_other_entities': len(bsp.entities) - 1,
        'original_entity_index': index, 'water_model': original.get('model'),
        'original_origin': list(origin), 'surface_raise': SURFACE_RAISE,
        'copies': [{'targetname': e.get('targetname'),
                    'origin': list(map(float, e.get('origin').split())),
                    'skin': int(e.get('skin')), 'spawnflags': int(e.get('spawnflags'))}
                   for e in waters],
        'model_bounds_with_compiler_padding': [list(model.mins), list(model.maxs)],
        'all_non_entity_lumps_identical': True,
        'source_prefix_preserved_except_entity_descriptor': True,
        'non_entity_lump_hashes': {k: v for k, v in before.items() if k != '0'},
        'nominal_entity_reserve': 2047 - len(entities),
        'requires_native_verification': True,
    }
    (out / 'creek-water-build-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in
                      ('output_sha256', 'total_entities', 'preserved_other_entities')}, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    build(args.base, args.out)
