"""Fit one original bush clear of the north entrance bank in a private candidate.

Only entity 304's origin changes. The accepted map, compiled model, placement
audit and replay helpers are frozen; no runtime files or services are modified.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import struct

from build_entrance_bush_clearance import compiled_mesh, contents
from meadow_surface import SurfaceIndex
from bsp30 import BSP

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
LAB = REPO.parent / 'daragoth-development'
BASE_SHA = '0f8d0e4c429985eda72c8ce17f0480014a687d088f902e50ada1ea9b8c644754'
MODEL_SHA = '17033a6e81b450ddb703a8cdbc0a62d98462db48be3a60e2cb92cf200af29415'
AUDIT_SHA = 'e0f6cda2ed565aba0f011b11902e2a9386b3d2a535294732e80debdf3f00888b'
DENSE_DIAGNOSTIC_SHA = 'd59358dc22b66f4dcb8e2dfb7c2a13a9125456f0b2858ec41d2825fd7672765f'
REPLAY_SHA = '4061185669889b3bc770041313bac8790425c48b83cbbd43c977e6d244a56857'
SURFACE_SHA = 'd44e5b5ac5e2183a2351e469b1f9dfa958aa271ee3a16bf463288166b3946b48'
ENTITY = 304
OLD_ORIGIN = '93.5564 3183.91 3432'
NEW_ORIGIN = '113 3136 3432'
MODEL = 'models/props/arc_bush.mdl'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def posed_geometry(model):
    points, triangles, _, pose_error = compiled_mesh(model)
    yaw = math.radians(27)
    c, s = math.cos(yaw), math.sin(yaw)

    def transform(p):
        return (0.8 * (c*p[0] - s*p[1]),
                0.8 * (s*p[0] + c*p[1]), 0.8*p[2])

    return [transform(p) for p in points], [
        [transform(p) for p in triangle] for triangle in triangles], pose_error


def survey(bsp, points, triangles, origin):
    floor = SurfaceIndex(bsp).at(origin[0], origin[1], max_z=3433)
    require(floor is not None and floor['face'] == 1440 and
            floor['texture'] == 'rock01a' and abs(floor['z'] - 3432) < 0.001,
            'The root must retain its original horizontal ledge')
    require(contents(bsp, (*origin[:2], 3431.99)) == -2 and
            contents(bsp, (*origin[:2], 3432.01)) == -1 and
            contents(bsp, (*origin[:2], 3468.1), 1) == -1,
            'Ledge contact or standing hull clearance differs')
    counts = {'empty': 0, 'solid': 0, 'other': 0}
    examples = []
    for triangle in triangles:
        for i in range(33):
            for j in range(33-i):
                weights = (i/32, j/32, 1-(i+j)/32)
                point = [origin[k] + sum(weights[n]*triangle[n][k]
                         for n in range(3)) for k in range(3)]
                if point[2] <= 3432.1:
                    continue  # The original planted root embedding is intentional.
                value = contents(bsp, point)
                label = 'empty' if value == -1 else 'solid' if value == -2 else 'other'
                counts[label] += 1
                if value != -1 and len(examples) < 6:
                    examples.append({'point': point, 'contents': value})
    bounds = [[origin[k] + operation(p[k] for p in points) for k in range(3)]
              for operation in (min, max)]
    return {'origin': origin, 'rendered_root_floor': floor,
            'standing_hull1_empty': True, 'world_bounds': bounds,
            'root_embedding_units': 3432 - bounds[0][2],
            'barycentric_divisions': 32, 'above_floor_sample_counts': counts,
            'nonempty_examples': examples,
            'scope': 'Finite actual triangle samples, including transparent card areas; root embedding is excluded. Opaque clipping is independently diagnosed in the pinned placement audit.'}


def build(base, model, placement_audit, dense_diagnostic, out):
    out = out.resolve()
    require(out.is_relative_to((LAB/'meadow-next').resolve()),
            'Outputs must stay in the private meadow-next scratch area')
    source = base.read_bytes()
    require(sha(source) == BASE_SHA, 'Accepted map changed')
    require(sha(model.read_bytes()) == MODEL_SHA, 'Compiled bush changed')
    require(sha(placement_audit.read_bytes()) == AUDIT_SHA, 'Placement audit changed')
    require(sha(dense_diagnostic.read_bytes()) == DENSE_DIAGNOSTIC_SHA,
            'Keep the denser placement failures and final selection frozen')
    for name, pin in [('build_entrance_bush_clearance.py', REPLAY_SHA),
                      ('meadow_surface.py', SURFACE_SHA)]:
        require(sha((ROOT/name).read_bytes()) == pin, 'Replay dependency changed')
    before = BSP.load(base)
    entity = before.entities[ENTITY]
    require(len(before.entities) == 1053 and entity.get('origin') == OLD_ORIGIN and
            entity.get('model') == MODEL and entity.classname == 'env_model' and
            entity.get('angles') == '0 27 0' and float(entity.get('scale')) == 0.8 and
            entity.get('dmg') == '0' and entity.get('sequence', '0') == '0',
            'Diagnosed nonsolid static bush configuration changed')
    points, triangles, pose_error = posed_geometry(model)
    old = survey(before, points, triangles, list(map(float, OLD_ORIGIN.split())))
    new = survey(before, points, triangles, list(map(float, NEW_ORIGIN.split())))
    require(old['above_floor_sample_counts']['solid'] > 0,
            'The diagnosed bank intersection was not reproduced')
    require(new['above_floor_sample_counts']['solid'] == 0 and
            new['above_floor_sample_counts']['other'] == 0,
            'The destination intersects solid space or water above the floor')
    require(old['root_embedding_units'] == new['root_embedding_units'],
            'Original root embedding changed')
    offset, length = struct.unpack_from('<2i', source, 4)
    lump = source[offset:offset+length]
    blocks = list(re.finditer(rb'\{([^{}]*)\}', lump))
    require(len(blocks) == 1053, 'Unexpected entity syntax')
    block = blocks[ENTITY]
    origins = list(re.finditer(rb'"origin"\s+"([^"\r\n]*)"', block.group()))
    require(len(origins) == 1 and origins[0].group(1) == OLD_ORIGIN.encode(),
            'Expected exactly one unchanged origin key')
    start, end = origins[0].span(1)
    start, end = block.start()+start, block.start()+end
    changed = lump[:start] + NEW_ORIGIN.encode() + lump[end:]
    output = bytearray(source)
    output.extend(b'\0' * (-len(output) % 4))
    struct.pack_into('<2i', output, 4, len(output), len(changed))
    output.extend(changed)
    require(output[:4] == source[:4] and output[12:len(source)] == source[12:],
            'Source prefix changed outside the entity descriptor')
    out.mkdir(parents=True, exist_ok=True)
    target = out/'daragoth_meadow_north_bank_bush.bsp'
    report_path = out/'north-bank-bush-build-report.json'
    require(not target.exists() and not report_path.exists(), 'Keep prior outputs immutable')
    require(sha(base.read_bytes()) == BASE_SHA and sha(model.read_bytes()) == MODEL_SHA,
            'Inputs changed during construction')
    with target.open('xb') as stream:
        stream.write(output)
    after = BSP.load(target)
    expected = copy.deepcopy([e.pairs for e in before.entities])
    for pair in expected[ENTITY]:
        if pair[0] == 'origin':
            pair[1] = NEW_ORIGIN
    require([e.pairs for e in after.entities] == expected, 'An unrelated entity key changed')
    report = {'schema': 'daragoth-north-bank-bush-build-v1', 'pass': True,
              'source_sha256': BASE_SHA, 'candidate_sha256': sha(bytes(output)),
              'model_sha256': MODEL_SHA, 'placement_audit_sha256': AUDIT_SHA,
              'denser_placement_diagnostic_sha256': DENSE_DIAGNOSTIC_SHA,
              'coarse_selection_scope': 'The opaque audit diagnoses the old canopy and tests origin112. The denser diagnostic rejects that origin and selects113; those failures remain preserved.',
              'builder_sha256': sha(Path(__file__).read_bytes()),
              'entity': ENTITY, 'old_origin': OLD_ORIGIN, 'new_origin': NEW_ORIGIN,
              'yaw': 27, 'scale': 0.8, 'compiled_pose_bounds_error': pose_error,
              'before': old, 'after': new, 'other_entities_unchanged': 1052,
              'all_nonentity_lumps_and_descriptors_unchanged': True,
              'old_prefix_unchanged_except_entity_descriptor': True,
              'collision_visibility_water_doors_grass_and_controls_preserved': True,
              'native_acceptance': 'pending', 'runtime_installation_performed': False}
    with report_path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    return {'pass': True, 'candidate': str(target), 'candidate_sha256': report['candidate_sha256'],
            'build_report_sha256': sha(report_path.read_bytes()),
            'before_solid_samples': old['above_floor_sample_counts']['solid'],
            'after_empty_samples': new['above_floor_sample_counts']['empty']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True, type=Path)
    parser.add_argument('--model', required=True, type=Path)
    parser.add_argument('--placement-audit', required=True, type=Path)
    parser.add_argument('--dense-diagnostic', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.base, args.model, args.placement_audit,
                          args.dense_diagnostic, args.out)))


if __name__ == '__main__':
    main()
