"""Independently verify the material-only original meadow join cap repair.

Reads frozen BSPs and the build receipt. Does not import the material builder,
change a map/runtime, or start a game. Optional C checks reuse the established
isolated engine road-trace harness; byte-identical collision is checked always.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'Packaging-Work/BigWorld/tools'))
from bsp30 import BSP, FACE

BASE_SHA = '676afa30a2e050a7dca9d56dfc82e1b40048e11c694d838d8e8b8abbd3224d05'
CANDIDATE_SHA = 'a82d997a153543198f01c2d36199b7d78498f309c6a251fa70891abacbf69f29'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def section():
    return {'failure_count': 0, 'failures': []}


def check(result, condition, message, **details):
    if not condition:
        result['failure_count'] += 1
        if len(result['failures']) < 30:
            result['failures'].append({'message': message, **details})


def finish(result):
    result['pass'] = result['failure_count'] == 0
    return result


def lumps(data):
    return [data[o:o + size] for o, size in
            (struct.unpack_from('<2i', data, 4 + i * 8) for i in range(15))]


def polygon(bsp, face):
    points = []
    for signed in bsp.surfedges[face.firstedge:face.firstedge + face.numedges]:
        edge = bsp.edges[abs(signed)]
        points.append(bsp.vertexes[edge[0 if signed >= 0 else 1]])
    return points


def texture_name(bsp, face):
    return bsp.textures[bsp.texinfo[face.texinfo].miptex].name


def verify(base, candidate, report_path, actual_c=False):
    hashes = {key: digest(path) for key, path in
              {'base': base, 'bsp': candidate, 'report_source': report_path}.items()}
    metadata = section()
    build = json.loads(report_path.read_text())
    check(metadata, hashes['base'] == BASE_SHA, 'Wrong frozen material input')
    check(metadata, hashes['bsp'] == CANDIDATE_SHA, 'Wrong frozen material candidate')
    check(metadata, build.get('base_sha256') == hashes['base'] and build.get('output_sha256') == hashes['bsp'],
          'Build receipt does not identify these inputs')
    builder = REPO / 'Design-Source/Daragoth-Meadow/build_join_material.py'
    check(metadata, build.get('source_builder_sha256') == digest(builder), 'Material builder source changed')
    before_data, after_data = base.read_bytes(), candidate.read_bytes()
    before, after = lumps(before_data), lumps(after_data)
    old, new = BSP.load(base), BSP.load(candidate)
    world = old.models[0]
    targets = [i for i in range(world.firstface, world.firstface + world.numfaces)
               if texture_name(old, old.faces[i]) == 'DPROCK' and
               polygon(old, old.faces[i]) and all(abs(p[1] - 3216) < .001 for p in polygon(old, old.faces[i]))]
    check(metadata, len(targets) == 131 and 17848 in targets, 'Independent cap selection does not match the bounded repair')
    check(metadata, build.get('retextured_faces') == targets and build.get('retextured_face_count') == 131,
          'Reported material targets differ from independently selected caps')
    target_set = set(targets)

    preservation = section()
    immutable = {str(i): before[i] == after[i] for i in range(15) if i not in (7, 8)}
    for i, equal in immutable.items():
        check(preservation, equal, 'Material repair changed an immutable BSP lump', lump=i)
    prefix = bytearray(after_data[:len(before_data)])
    for i in (7, 8):
        prefix[4 + i * 8:12 + i * 8] = before_data[4 + i * 8:12 + i * 8]
    check(preservation, prefix == before_data, 'Old file prefix changed outside face/lighting descriptors')
    check(preservation, len(old.faces) == len(new.faces), 'Material repair changed the number of faces')
    check(preservation, after[8].startswith(before[8]), 'Original lighting bytes were overwritten')
    unchanged_faces = 0
    geometry_count = 0
    for index, (a, b) in enumerate(zip(old.faces, new.faces)):
        geometry_equal = (a.planenum, a.side, a.firstedge, a.numedges) == (b.planenum, b.side, b.firstedge, b.numedges)
        check(preservation, geometry_equal, 'A face geometry/winding reference changed', face=index)
        geometry_count += geometry_equal
        if index not in target_set:
            equal = before[7][index * FACE.size:(index + 1) * FACE.size] == after[7][index * FACE.size:(index + 1) * FACE.size]
            check(preservation, equal, 'A face outside the bounded material targets changed', face=index)
            unchanged_faces += equal
    preservation.update({'immutable_lumps_identical': immutable, 'entities_preserved': len(old.entities),
                         'models_headnodes_preserved': len(old.models), 'faces_geometry_preserved': geometry_count,
                         'non_target_faces_preserved': unchanged_faces,
                         'original_file_prefix_preserved_except_descriptors': prefix == before_data,
                         'original_lighting_prefix_preserved': after[8].startswith(before[8])})

    materials = section()
    lightmaps = section()
    next_light = len(before[8])
    for index in targets:
        f = new.faces[index]
        check(materials, f.texinfo == 14 and texture_name(new, f) == 'rock01a_ewok', 'Cap does not use the original embedded rock', face=index)
        check(lightmaps, f.styles == [0, 255, 255, 255], 'Cap does not have one ordinary light style', face=index)
        points = polygon(new, f)
        vecs = new.texinfo[f.texinfo].vecs
        dimensions = []
        for vec in vecs:
            values = [sum(p[k] * vec[k] for k in range(3)) + vec[3] for p in points]
            dimensions.append(math.ceil(max(values) / 16) - math.floor(min(values) / 16) + 1)
        size = dimensions[0] * dimensions[1] * 3
        check(lightmaps, f.lightofs == next_light and 0 < size and f.lightofs + size <= len(new.lighting),
              'Appended face lightmap layout is invalid', face=index, dimensions=dimensions, offset=f.lightofs)
        block = new.lighting[f.lightofs:f.lightofs + size]
        if len(block) == size:
            colors = set(zip(block[0::3], block[1::3], block[2::3]))
            check(lightmaps, len(colors) == 1 and all(122 <= c <= 146 for rgb in colors for c in rgb),
                  'Material lightmap is not consistent neutral outdoor illumination', face=index)
        next_light += size
    check(lightmaps, next_light == len(new.lighting), 'Unexpected lighting bytes were added outside these caps')
    remaining = [i for i in range(new.models[0].firstface, new.models[0].firstface + new.models[0].numfaces)
                 if texture_name(new, new.faces[i]) == 'DPROCK' and
                 all(abs(p[1] - 3216) < .001 for p in polygon(new, new.faces[i]))]
    check(materials, not remaining, 'Placeholder seam rock remains in the selected world surface', remaining=remaining)
    rock = new.textures[new.texinfo[14].miptex]
    check(materials, rock.raw is not None and not rock.external, 'Original rock texture is not embedded')
    materials.update({'retextured_face_count': len(targets), 'retextured_faces': targets,
                      'remaining_seam_placeholder_faces': remaining, 'material': rock.name,
                      'material_texture_sha256': hashlib.sha256(rock.raw).hexdigest() if rock.raw else None})
    lightmaps.update({'verified_faces': len(targets), 'appended_rgb_bytes': len(after[8]) - len(before[8])})

    if actual_c:
        # This harness compiles the actual engine trace implementation in a temp directory.
        from test_meadow_join_caps import actual_c as actual_c_trace
        c_result = actual_c_trace(candidate)
    else:
        c_result = {'status': 'not_requested', 'pass': None,
                    'scope': 'World collision bytes are identical; no native appearance or lifecycle claim.'}
    unchanged_inputs = all(digest(path) == hashes[key] for key, path in
                           {'base': base, 'bsp': candidate, 'report_source': report_path}.items())
    report = {'input_sha256': hashes, 'checker_source_sha256': digest(Path(__file__)),
              'builder_source_sha256': digest(builder), 'metadata': finish(metadata),
              'preservation': finish(preservation), 'materials': finish(materials),
              'lightmaps': finish(lightmaps), 'actual_c_requested': actual_c, 'actual_c': c_result,
              'inputs_unchanged_during_verification': unchanged_inputs, 'native_visual_acceptance': None}
    report['static_pass'] = all(report[k]['pass'] for k in ('metadata', 'preservation', 'materials', 'lightmaps')) and unchanged_inputs
    report['pass'] = report['static_pass'] and (not actual_c or c_result.get('pass') is True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--bsp', type=Path, required=True)
    parser.add_argument('--build-report', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--actual-c', action='store_true')
    args = parser.parse_args()
    if args.report.exists() or args.report.resolve() in {p.resolve() for p in (args.base, args.bsp, args.build_report)}:
        raise ValueError('Write only a new independent receipt; do not overwrite evidence')
    result = verify(args.base, args.bsp, args.build_report, args.actual_c)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('pass', 'static_pass', 'input_sha256', 'checker_source_sha256')}, indent=2))
    sys.exit(0 if result['pass'] else 1)
