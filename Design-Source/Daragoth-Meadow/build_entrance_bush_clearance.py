"""Move one original entrance bush away from the rendered rock wall.

The frozen entrance candidate and compiled bush are required. Only entity460's
origin value changes; preserve entity formatting and append the new entity lump.
No compiler, game process, runtime map, controls or core files are touched.
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
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'Packaging-Work/BigWorld/tools'))
from bsp30 import BSP
from meadow_surface import SurfaceIndex

BASE_SHA = '77611d302aa1cf309550a517bed2c169388986341ff3bd02f06b5e1e8acdb4d7'
MODEL_SHA = '17033a6e81b450ddb703a8cdbc0a62d98462db48be3a60e2cb92cf200af29415'
ENTITY = 460
OLD_ORIGIN = '2164.87 3015.32 3072'
NEW_ORIGIN = '2164.87 2983.32 3072'
MODEL = 'models/props/arc_bush.mdl'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def contents(bsp, point, hull=0):
    head = bsp.models[0].headnode[hull]
    while head >= 0:
        node = bsp.nodes[head] if hull == 0 else bsp.clipnodes[head]
        plane = bsp.planes[node.planenum]
        distance = sum(point[k] * plane.normal[k] for k in range(3)) - plane.dist
        head = node.children[0 if distance >= 0 else 1]
    return bsp.leafs[-head - 1].contents if hull == 0 else head


def compiled_mesh(path):
    """Replay the one-frame static bush, including its compressed bone pose."""
    data = path.read_bytes()
    if sha(data) != MODEL_SHA:
        raise ValueError('The diagnosed original bush model changed')
    if data[:4] != b'IDST' or struct.unpack_from('<i', data, 4)[0] != 10:
        raise ValueError('Expected the original studio v10 model')
    bones, bone_at = struct.unpack_from('<2i', data, 140)
    sequences, sequence_at = struct.unpack_from('<2i', data, 164)
    if bones != 1 or sequences != 1 or struct.unpack_from('<i', data, sequence_at + 56)[0] != 1:
        raise ValueError('The bush must have one bone and one static frame')
    if struct.unpack_from('<6i', data, bone_at + 40) != (-1,) * 6:
        raise ValueError('The bush must have no bone controllers')
    pose = list(struct.unpack_from('<6f', data, bone_at + 64))
    scale = struct.unpack_from('<6f', data, bone_at + 88)
    animation = struct.unpack_from('<i', data, sequence_at + 124)[0]
    for k, offset in enumerate(struct.unpack_from('<6H', data, animation)):
        if offset:
            valid, total, value = struct.unpack_from('<BBh', data, animation + offset)
            if valid != 1 or total != 1:
                raise ValueError('Expected a single compressed pose value')
            pose[k] += value * scale[k]
    rx, ry, rz = pose[3:]
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)

    def transform(vertex):
        x, y, z = vertex
        y, z = cx * y - sx * z, sx * y + cx * z
        x, z = cy * x + sy * z, -sy * x + cy * z
        x, y = cz * x - sz * y, sz * x + cz * y
        return (x + pose[0], y + pose[1], z + pose[2])

    parts, part_at = struct.unpack_from('<2i', data, 204)
    if parts != 1:
        raise ValueError('Expected one permanent bush bodypart')
    models, _, model_at = struct.unpack_from('<3i', data, part_at + 64)
    if models != 1:
        raise ValueError('Expected one bush submodel')
    record = struct.unpack_from('<64sif10i', data, model_at)
    meshes, mesh_at, vertices, vertex_bones, vertex_at = record[3:8]
    if any(data[vertex_bones:vertex_bones + vertices]):
        raise ValueError('A vertex uses a different bone')
    points = [transform(struct.unpack_from('<3f', data, vertex_at + 12 * i)) for i in range(vertices)]
    bounds = [[min(p[k] for p in points) for k in range(3)], [max(p[k] for p in points) for k in range(3)]]
    expected = struct.unpack_from('<6f', data, sequence_at + 96)
    error = max(abs(bounds[j][k] - expected[k + 3 * j]) for j in range(2) for k in range(3))
    if error > .01:
        raise ValueError('Replayed mesh does not match compiled idle bounds')
    triangles = []
    for i in range(meshes):
        count, at, _, _, _ = struct.unpack_from('<5i', data, mesh_at + 20 * i)
        start = len(triangles)
        while True:
            number = struct.unpack_from('<h', data, at)[0]
            at += 2
            if not number:
                break
            commands = list(struct.iter_unpack('<4h', data[at:at + abs(number) * 8]))
            at += abs(number) * 8
            for j in range(abs(number) - 2):
                order = ([j, j + 1, j + 2] if j % 2 == 0 else [j + 1, j, j + 2]) if number > 0 else [0, j + 1, j + 2]
                triangles.append([points[commands[k][0]] for k in order])
        if len(triangles) - start != count:
            raise ValueError('Compiled mesh command triangle count changed')
    return points, triangles, bounds, error


def placement_check(bsp, points, triangles):
    origin = list(map(float, NEW_ORIGIN.split()))
    translated = [[p[k] + origin[k] for k in range(3)] for p in points]
    bounds = [[min(p[k] for p in translated) for k in range(3)], [max(p[k] for p in translated) for k in range(3)]]
    if 3088 - bounds[1][1] < 24:
        raise ValueError('The bush still reaches the entrance wall')
    index = SurfaceIndex(bsp)
    ground = index.at(origin[0], origin[1], max_z=3100)
    if not ground or ground['z'] != 3072 or ground['texture'] != 'medgrass2_ewoks':
        raise ValueError('The destination is not on the original grass floor')
    floor_points = 0
    nonflat_floor = 0
    missing_floor = 0
    solid_box_points = 0
    box_examples = []
    for x in [bounds[0][0], *range(math.ceil(bounds[0][0] / 16) * 16, math.floor(bounds[1][0]) + 1, 16), bounds[1][0]]:
        for y in [bounds[0][1], *range(math.ceil(bounds[0][1] / 16) * 16, math.floor(bounds[1][1]) + 1, 16), bounds[1][1]]:
            floor = index.at(x, y, max_z=3100)
            point_contents = contents(bsp, [x, y, 3072.1])
            floor_nonflat = not floor or abs(floor['z'] - 3072) > .01
            missing_floor += not floor
            nonflat_floor += floor_nonflat
            solid_box_points += point_contents == -2
            if (floor_nonflat or point_contents != -1) and len(box_examples) < 8:
                box_examples.append({'x': x, 'y': y, 'surface_below_3100': floor,
                                     'hull0_at_floor_plus_point1': point_contents})
            floor_points += 1
    samples = 0
    previous_solid_samples = 0
    for triangle in triangles:
        for i in range(33):
            for j in range(33 - i):
                weights = (i / 32, j / 32, 1 - (i + j) / 32)
                point = [origin[k] + sum(weights[n] * triangle[n][k] for n in range(3)) for k in range(3)]
                if point[2] <= ground['z'] + .1:
                    continue  # Preserve the model's intentional root embedding.
                if contents(bsp, point) != -1:
                    raise ValueError(f'Above-floor bush geometry intersects the world: {point}')
                previous_solid_samples += contents(bsp, [point[0], point[1] + 32, point[2]]) == -2
                samples += 1
    if contents(bsp, [*origin[:2], 3071.99]) != -2 or contents(bsp, [*origin[:2], 3072.01]) != -1 or contents(bsp, [*origin[:2], 3108], 1) != -1:
        raise ValueError('Destination floor/body clearance changed')
    return {'origin': origin, 'compiled_world_bounds': bounds, 'wall_clearance': 3088 - bounds[1][1],
            'rendered_ground': ground, 'bounds_footprint_floor_samples': floor_points,
            'conservative_box_missing_rendered_floor_samples': missing_floor,
            'conservative_box_nonflat_floor_samples': nonflat_floor,
            'conservative_box_solid_samples': solid_box_points, 'conservative_box_examples': box_examples,
            'conservative_box_scope': 'The rectangle includes unused model-space corners on an original grass bank up to3.075 units higher than the root floor; it is not a claim that the whole box is empty. Actual above-floor triangle samples are checked separately.',
            'triangle_barycentric_divisions': 32, 'above_floor_mesh_samples_empty': samples,
            'previous_above_floor_mesh_samples_solid': previous_solid_samples,
            'root_embedding_preserved': True, 'standing_hull1_contents': -1}


def build(base, model, out):
    source = base.read_bytes()
    if sha(source) != BASE_SHA:
        raise ValueError('Use the frozen entrance-closure candidate')
    before = BSP.load(base)
    entity = before.entities[ENTITY]
    if len(before.entities) != 1053 or entity.get('model') != MODEL or entity.get('origin') != OLD_ORIGIN:
        raise ValueError('The diagnosed original bush entity changed')
    if any(entity.get(key) != value for key, value in {'classname': 'env_model', 'angles': '0 0 0', 'dmg': '0'}.items()) or entity.get('sequence', '0') != '0':
        raise ValueError('The bush pose or nonsolid configuration changed')
    points, triangles, local_bounds, pose_error = compiled_mesh(model)
    placement = placement_check(before, points, triangles)
    offset, length = struct.unpack_from('<2i', source, 4)
    old_lump = source[offset:offset + length]
    blocks = list(re.finditer(rb'\{([^{}]*)\}', old_lump))
    if len(blocks) != 1053:
        raise ValueError('Unexpected entity-lump syntax')
    block = blocks[ENTITY]
    origins = list(re.finditer(rb'"origin"\s+"([^"\r\n]*)"', block.group()))
    if len(origins) != 1 or origins[0].group(1) != OLD_ORIGIN.encode():
        raise ValueError('Expected exactly one original origin key')
    start, end = origins[0].span(1)
    start, end = block.start() + start, block.start() + end
    new_lump = old_lump[:start] + NEW_ORIGIN.encode() + old_lump[end:]
    output = bytearray(source)
    output.extend(b'\0' * (-len(output) % 4))
    new_offset = len(output)
    output.extend(new_lump)
    struct.pack_into('<2i', output, 4, new_offset, len(new_lump))
    if output[:4] != source[:4] or output[12:len(source)] != source[12:]:
        raise ValueError('Source prefix changed outside the entity descriptor')
    target = out / 'daragoth_meadow_bush_clearance.bsp'
    report_path = out / 'entrance-bush-clearance-build-report.json'
    if target.exists() or report_path.exists() or target.resolve() == base.resolve():
        raise ValueError('Keep frozen maps/reports immutable')
    if sha(base.read_bytes()) != BASE_SHA or sha(model.read_bytes()) != MODEL_SHA:
        raise ValueError('An input changed during construction')
    out.mkdir(parents=True, exist_ok=True)
    target.write_bytes(output)
    after = BSP.load(target)
    expected = copy.deepcopy([e.pairs for e in before.entities])
    for pair in expected[ENTITY]:
        if pair[0] == 'origin':
            pair[1] = NEW_ORIGIN
    if [e.pairs for e in after.entities] != expected:
        raise ValueError('Reloaded ordered entities differ beyond the one origin')
    if any(struct.unpack_from('<2i', output, 4 + i * 8) != struct.unpack_from('<2i', source, 4 + i * 8) for i in range(1, 15)):
        raise ValueError('A nonentity descriptor changed')
    if after.extra_lumps != before.extra_lumps or after.models != before.models:
        raise ValueError('Extra data or world/water/door model geometry changed')
    report = {'base_path': str(base), 'base_sha256': BASE_SHA, 'output_path': str(target), 'output_sha256': sha(output),
              'source_builder_sha256': sha(Path(__file__).read_bytes()), 'model_path': str(model), 'model_sha256': MODEL_SHA,
              'changed_lumps': [0], 'entity_index': ENTITY, 'old_origin': OLD_ORIGIN, 'new_origin': NEW_ORIGIN,
              'total_entities': len(after.entities), 'preserved_other_ordered_entities': 1052,
              'changed_entity_other_ordered_keys_preserved': True, 'entity_lump_other_bytes_preserved': True,
              'original_entity_value_span': [start, end], 'new_entity_lump_descriptor': [new_offset, len(new_lump)],
              'all_14_nonentity_lumps_and_descriptors_identical': True, 'xash_extras_identical': True,
              'source_prefix_identical_except_entity_descriptor': True, 'all_world_water_bed_door_grass_geometry_preserved': True,
              'compiled_local_bounds': local_bounds, 'frame0_to_sequence_bounds_max_error': pose_error, 'placement': placement,
              'scope': 'One original nonsolid bush origin moved south32. Frozen compiled one-frame mesh replay, finite footprint floor and barycentric above-floor checks; no new terrain or core behavior. Native visual attribution and acceptance remain pending.',
              'native_visual_accepted': False, 'runtime_mutated': False, 'requires_independent_review_and_native_visual_acceptance': True}
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'output_path': str(target), 'output_sha256': report['output_sha256'], 'report_path': str(report_path),
                      'report_sha256': sha(report_path.read_bytes()), 'source_builder_sha256': report['source_builder_sha256'],
                      'placement': placement}, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    build(args.base.resolve(), args.model.resolve(), args.out.resolve())
