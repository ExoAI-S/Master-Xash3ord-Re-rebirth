"""Build shorter, irregular CC0 grass using the existing authored card texture.

Only geometry changes. The supplied indexed bitmap is copied byte-for-byte.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import random
import shutil
import struct
import subprocess

ROOT = Path(__file__).resolve().parent


def build(source, bitmap, out, compiler):
    out.mkdir(parents=True, exist_ok=True)
    lines = (source / 'plains_grass_reference.smd').read_text().splitlines()
    start = lines.index('triangles') + 1
    cards = lines[start:start + 32]
    assert len(cards) == 32 and all(len(cards[i].split()) == 9 for i in range(32) if i % 4)
    rng = random.Random(202610012)
    centers = []
    for _ in range(10000):
        angle = rng.uniform(0, math.tau)
        distance = 122 * math.sqrt(rng.random())
        point = (math.cos(angle) * distance, math.sin(angle) * distance)
        if all(math.dist(point, other) >= 25 for other in centers):
            centers.append(point)
        if len(centers) == 42:
            break
    assert len(centers) == 42, 'Irregular tuft budget not fulfilled'
    output = lines[:start]
    vertices = []
    for ox, oy in centers:
        angle = rng.uniform(0, math.tau)
        width = rng.uniform(.82, 1.12)
        height = rng.uniform(.47, .82)
        c, s = math.cos(angle), math.sin(angle)
        for i in range(0, 32, 4):
            output.append('meadow_grass_blades.bmp')
            for line in cards[i + 1:i + 4]:
                values = line.split()
                x, y, z, nx, ny, nz, u, v = map(float, values[1:9])
                x -= 10
                p = (ox + width * (x*c - y*s), oy + width * (x*s + y*c), z*height)
                n = ((nx*c - ny*s)/width, (nx*s + ny*c)/width, nz/height)
                length = math.sqrt(sum(value*value for value in n))
                n = tuple(value/length for value in n)
                vertices.append(p)
                output.append('0 ' + ' '.join(f'{value:.6f}' for value in (*p, *n, u, v)))
    output.append('end')
    (out / 'meadow_grass_patch_reference.smd').write_text('\n'.join(output) + '\n')
    shutil.copyfile(source / 'plains_grass_idle.smd', out / 'meadow_grass_patch_idle.smd')
    shutil.copyfile(bitmap, out / 'meadow_grass_blades.bmp')
    lo = [min(p[k] for p in vertices) for k in range(3)]
    hi = [max(p[k] for p in vertices) for k in range(3)]
    bounds = ' '.join(f'{value:.6f}' for value in (*lo, *hi))
    qc = f'''// Original CC0 crossed cards; irregular short meadow grass.
$modelname "meadow_grass_patch.mdl"
$cd "."
$cdtexture "."
$scale 1
$gamma 1.8
$origin 0 0 0 -90
$body "prop" "meadow_grass_patch_reference"
$sequence "idle" "meadow_grass_patch_idle" fps 12 loop
$bbox {bounds}
$cbox {bounds}
$texrendermode "meadow_grass_blades.bmp" masked
'''
    (out / 'meadow_grass_patch.qc').write_text(qc)
    result = subprocess.run([str(compiler.resolve()), 'meadow_grass_patch.qc'], cwd=out,
                            capture_output=True, text=True)
    (out / 'compile.log').write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError('Grass compiler failed; see compile.log')
    path = out / 'meadow_grass_patch.mdl'
    mdl = bytearray(path.read_bytes())
    assert mdl[:4] == b'IDST' and struct.unpack_from('<i', mdl, 4)[0] == 10
    count, offset = struct.unpack_from('<2i', mdl, 180)
    assert count == 1
    flags, width, height, pixels = struct.unpack_from('<4i', mdl, offset + 64)
    assert flags & 64 and not flags & 4 and 255 in mdl[pixels:pixels + width*height]
    struct.pack_into('<i', mdl, offset + 64, flags | 1)
    path.write_bytes(mdl)
    report = {'tufts':len(centers), 'triangles':len(vertices)//3, 'bounds':[lo, hi],
              'radius':max(math.hypot(p[0], p[1]) for p in vertices),
              'maximum_height':hi[2], 'masked_scene_lit':True,
              'source_bitmap_sha256':hashlib.sha256(bitmap.read_bytes()).hexdigest(),
              'copied_bitmap_sha256':hashlib.sha256((out/'meadow_grass_blades.bmp').read_bytes()).hexdigest(),
              'sha256':hashlib.sha256(mdl).hexdigest(), 'license':'CC0-1.0'}
    assert report['source_bitmap_sha256'] == report['copied_bitmap_sha256']
    (out/'grass-patch-report.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT/'SourceAssets')
    parser.add_argument('--bitmap', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--compiler', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.bitmap, args.out, args.compiler), indent=2))
