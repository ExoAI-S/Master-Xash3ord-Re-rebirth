"""Match all original solid join caps to the restored embedded entrance rock.

This material-only follow-up preserves every face's geometry, winding and
references, all collision/PVS/entities, and the accepted animated water clone.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'Packaging-Work/BigWorld/tools'))
from bsp30 import BSP, FACE
spec = importlib.util.spec_from_file_location('boundary_material', Path(__file__).with_name('build_boundary_closure.py'))
boundary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boundary)
BASE_SHA = '676afa30a2e050a7dca9d56dfc82e1b40048e11c694d838d8e8b8abbd3224d05'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def build(base, out):
    data = base.read_bytes()
    if sha(data) != BASE_SHA:
        raise ValueError('Use the frozen boundary candidate')
    target = out / 'daragoth_meadow_material.bsp'
    if target.exists() or target.resolve() == base.resolve():
        raise ValueError('Do not overwrite frozen evidence')
    bsp = BSP.load(base)
    root = bsp.nodes[bsp.models[0].headnode[0]]
    ids = [i for i in range(root.firstface, root.firstface + root.numfaces)
           if bsp.textures[bsp.texinfo[bsp.faces[i].texinfo].miptex].name == 'DPROCK']
    if len(ids) != 131 or 17848 not in ids:
        raise ValueError('Expected all 131 original rock caps including the visible road edge')
    light = bytearray(bsp.lighting)
    for i in ids:
        face = bsp.faces[i]
        points = boundary.geometry.polygon(bsp, face)
        if not all(abs(p[1] - 3216) < .001 for p in points):
            raise ValueError('Unexpected non-seam placeholder material')
        face.texinfo = 14
        boundary.light_face(bsp, face, light)
    changed = {7: b''.join(FACE.pack(f.planenum, f.side, f.firstedge, f.numedges,
                                   f.texinfo, *f.styles, f.lightofs) for f in bsp.faces),
               8: bytes(light)}
    output = bytearray(data)
    for i, blob in changed.items():
        output.extend(b'\0' * (-len(output) % 4))
        offset = len(output)
        output.extend(blob)
        struct.pack_into('<2i', output, 4 + 8 * i, offset, len(blob))
    if sha(base.read_bytes()) != BASE_SHA:
        raise ValueError('Frozen input changed during construction')
    out.mkdir(parents=True, exist_ok=True)
    target.write_bytes(output)
    report = {'base_sha256': BASE_SHA, 'output_sha256': sha(output),
              'source_builder_sha256': sha(Path(__file__).read_bytes()),
              'retextured_faces': ids, 'retextured_face_count': len(ids),
              'changed_lumps': [7, 8], 'material': 'rock01a_ewok',
              'geometry_entities_collision_and_visibility_preserved': True,
              'water_preserved': True, 'requires_native_verification': True}
    (out / 'join-material-build-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('output_sha256', 'retextured_face_count')}, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    build(args.base, args.out)
