"""Audit the compiled replacement against the real v10 renderer/mount contract.

Reads the compiled command streams and animation RLE, not generator counters.
Native visual inspection is still required for skinning, saddle fit and motion.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct


def rotation(a):
    x, y, z = a
    cx, sx, cy, sy, cz, sz = math.cos(x), math.sin(x), math.cos(y), math.sin(y), math.cos(z), math.sin(z)
    return [[cz*cy, cz*sy*sx-sz*cx, cz*sy*cx+sz*sx],
            [sz*cy, sz*sy*sx+cz*cx, sz*sy*cx-cz*sx], [-sy, cy*sx, cy*cx]]


def mul(a, b):
    return [[sum(a[i][k]*b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def vec(a, b):
    return [sum(a[i][k]*b[k] for k in range(3)) for i in range(3)]


def audit(path, textures):
    data = path.read_bytes()
    def unpack(fmt, offset):
        size = struct.calcsize(fmt)
        assert 0 <= offset <= len(data)-size, ('Out-of-file field', offset, fmt)
        return struct.unpack_from(fmt, data, offset)
    def label(offset, size=32):
        return data[offset:offset+size].split(b'\0', 1)[0].decode('ascii')
    assert data[:4] == b'IDST' and unpack('<i', 4)[0] == 10
    assert unpack('<i', 72)[0] == len(data)
    assert not unpack('<I', 136)[0] & ((1 << 31) | (1 << 29)), 'No weighted/static extensions'
    bones_n, bones_at = unpack('<2i', 140)
    assert 1 <= bones_n <= 128
    bones, world = [], []
    for i in range(bones_n):
        base = bones_at + 112*i
        parent = unpack('<i', base+32)[0]
        assert -1 <= parent < i
        values = unpack('<6f', base+64)
        scales = unpack('<6f', base+88)
        assert all(math.isfinite(v) for v in (*values, *scales))
        matrix, position = rotation(values[3:]), list(values[:3])
        if parent >= 0:
            prior, origin = world[parent]
            position = [a+b for a, b in zip(vec(prior, position), origin)]
            matrix = mul(prior, matrix)
        bones.append({'name': label(base), 'parent': parent, 'values': values, 'scales': scales})
        world.append((matrix, position))
    attach_n, attach_at = unpack('<2i', 212)
    assert attach_n == 1
    attach_bone = unpack('<i', attach_at+36)[0]
    assert 0 <= attach_bone < bones_n
    matrix, position = world[attach_bone]
    seat = [a+b for a, b in zip(vec(matrix, unpack('<3f', attach_at+40)), position)]
    assert max(abs(a-b) for a,b in zip(seat, (-1.8, 0, 64.6))) < .02, ('Saddle contract', seat)

    seq_n, seq_at = unpack('<2i', 164)
    assert seq_n == 3 and unpack('<i', 172)[0] == 1, 'All animations embedded'
    sequences = []
    for si, expected in enumerate(('idle', 'walk', 'gallop')):
        base = seq_at+si*176
        name = label(base)
        fps, flags = unpack('<fI', base+32)
        frames = unpack('<i', base+56)[0]
        blends, anim_at = unpack('<2i', base+120)
        assert name == expected and flags & 1 and frames >= 3 and fps > 0
        assert blends == 1 and unpack('<i', base+156)[0] == 0
        all_frames = []
        for frame in range(frames):
            pose = []
            for bi, bone in enumerate(bones):
                entry = anim_at+bi*12
                offsets = unpack('<6H', entry)
                values = []
                for channel, offset in enumerate(offsets):
                    sample = 0
                    if offset:
                        stream, remaining = entry+offset, frame
                        while True:
                            valid, total = unpack('<2B', stream)
                            assert 0 < valid <= total, ('Malformed RLE', stream, valid, total)
                            if remaining < total:
                                sample = unpack('<h', stream+2*(min(remaining, valid-1)+1))[0]
                                break
                            remaining -= total
                            stream += 2*(valid+1)
                    values.append(bone['values'][channel]+sample*bone['scales'][channel])
                pose.extend(values)
            all_frames.append(pose)
        closure = max(abs(a-b) for a,b in zip(all_frames[0], all_frames[-1]))
        motion = max(abs(a-b) for pose in all_frames for a,b in zip(all_frames[0], pose))
        assert closure < .005, ('Loop discontinuity', name, closure)
        assert motion > .001, ('Static animation', name)
        sequences.append({'index': si, 'name': name, 'frames': frames, 'fps': fps,
                          'loop': True, 'max_loop_component_error': closure, 'max_animated_component_range': motion})

    texture_n, texture_at = unpack('<2i', 180)
    assert texture_n >= 2, 'Expected separate authored diffuse materials'
    texture_results = []
    for ti in range(texture_n):
        base = texture_at+ti*80
        name = label(base, 64)
        flags, width, height, pixels_at = unpack('<I3i', base+64)
        # pxstudiomdl crops unused source UV areas. Native texture extents are
        # consequently not required to retain the source power-of-two size.
        assert 0 < width <= 2048 and 0 < height <= 2048
        assert not flags & (4 | 32 | (1 << 31)), 'No fullbright/additive/extended UV materials'
        assert pixels_at+width*height+768 <= len(data)
        bmp = (textures/name).read_bytes()
        assert bmp[:2] == b'BM' and struct.unpack_from('<H', bmp,28)[0] == 8
        palette_at = 14+struct.unpack_from('<I', bmp,14)[0]
        assert struct.unpack_from('<I',bmp,10)[0] >= palette_at+1024, 'Full indexed palette required'
        palette = bytes(c for i in range(256) for c in bmp[palette_at+i*4:palette_at+i*4+3][::-1])
        assert palette == data[pixels_at+width*height:pixels_at+width*height+768], ('Palette modified', name)
        texture_results.append({'name': name, 'width': width, 'height': height, 'masked': bool(flags & 64)})

    body_n, body_at = unpack('<2i', 204)
    parts = []
    for pi in range(body_n):
        base = body_at+pi*76
        models_n, body_base, model_at = unpack('<3i', base+64)
        assert models_n == 1 and body_base > 0, 'All components visible at body=0'
        meshes_n, meshes_at, verts_n, vertbone_at, verts_at, normals_n, normalbone_at = unpack('<7i', model_at+72)
        assert 0 < verts_n <= 16384 and 0 < normals_n <= 16384
        assert all(b < bones_n for b in data[vertbone_at:vertbone_at+verts_n])
        assert all(b < bones_n for b in data[normalbone_at:normalbone_at+normals_n])
        submitted, triangles = 0, 0
        for mi in range(meshes_n):
            mesh_at = meshes_at+20*mi
            numtris, commands_at, skinref = unpack('<3i', mesh_at)
            mesh_submitted, mesh_triangles = 0, 0
            assert 0 <= skinref < unpack('<i', 192)[0]
            while True:
                count = unpack('<h', commands_at)[0]
                commands_at += 2
                if not count:
                    break
                count = abs(count)
                assert count >= 3
                mesh_submitted += count
                mesh_triangles += count-2
                for vi in range(count):
                    vertex, normal, _, _ = unpack('<4h', commands_at+vi*8)
                    assert 0 <= vertex < verts_n and 0 <= normal < normals_n
                commands_at += count*8
            assert numtris == mesh_triangles
            submitted += mesh_submitted
            triangles += mesh_triangles
        assert submitted <= 16384, ('ref_gl submitted vertex array overflow', label(base,64), submitted)
        assert triangles*3 <= 16384*6
        parts.append({'name': label(base,64), 'vertices': verts_n, 'normals': normals_n,
                      'meshes': meshes_n, 'triangles': triangles, 'submitted_vertices': submitted})
    assert 'head' in [b['name'] for b in bones]
    assert 'neck' in [b['name'] for b in bones]
    head = world[[b['name'] for b in bones].index('head')][1]
    neck = world[[b['name'] for b in bones].index('neck')][1]
    assert head[0] > neck[0], ('Compiled forward direction', head, neck)
    return {'pass': True, 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data),
            'version': 10, 'bones': bones_n, 'saddle_attachment': seat,
            'forward_axis': '+X', 'sequences': sequences, 'textures': texture_results,
            'bodyparts': parts, 'triangles': sum(p['triangles'] for p in parts),
            'scope': 'Compiled native format, renderer arrays, palette, direction, seat and looping motion. Skin deformation and rider fit require native visual tests.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mdl', type=Path, required=True)
    parser.add_argument('--textures', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.mdl, args.textures)
    args.report.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
