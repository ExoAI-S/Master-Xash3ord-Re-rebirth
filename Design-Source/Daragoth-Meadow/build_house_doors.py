"""Compile a new hinged wooden leaf and append six functional village doors.

The accepted world, water, grass, every old brush hull and entity record remain
unchanged. Only isolated freshly compiled door records are appended to the map.
No live runtime, game DLL, engine, configuration or service is modified.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import struct
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO / 'Packaging-Work/BigWorld/tools'), str(Path(__file__).parent)]
from bsp30 import (BSP, Entity, format_entities, PLANE, VERTEX, NODE, TEXINFO,
                   FACE, CLIPNODE32, LEAF, EDGE, MODEL)
from house_doors import DOOR_IDS, DOOR_SETTINGS, LEAF_MINS, LEAF_MAXS, door_brushes, door_values

BASE_SHA = '8388e76d2653f4acc09abc633b25c8ce94b816a9e99fb10743e8838edb37fdc3'
ALLOWED_OUT = REPO.parent / 'daragoth-development/house-doors'
TOOLS = Path('C:/Users/cptki/Documents/Codex/MSR-BigWorld/src/build-tools/Release/msr/devkit')
HINGES = [(-2893.9527, 5280, 3174), (-2949.9527, 6360, 3174),
          (-1563.9527, 4920, 3174), (-1563.9527, 6820, 3174),
          (-3005.9527, 7160, 3174), (-3159.9527, 4440, 3174)]
CHANGED = (0, 1, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def origin(*point):
    return ' '.join(f'{v:.4f}'.rstrip('0').rstrip('.') if v else '0' for v in point)


def closure(records, root, leaves=None):
    reached, active = set(), set()
    def visit(index):
        if index < 0:
            if leaves is not None:
                leaves.add(-1 - index)
            return
        if index in active or index >= len(records):
            raise ValueError('Invalid or cyclic isolated door hull')
        if index in reached:
            return
        active.add(index)
        for child in records[index].children:
            visit(child)
        active.remove(index); reached.add(index)
    visit(root)
    return reached


def polygon(bsp, face):
    return [bsp.vertexes[bsp.edges[abs(e)][0 if e >= 0 else 1]]
            for e in bsp.surfedges[face.firstedge:face.firstedge + face.numedges]]


def isolated_leaf(base, out, tools):
    """Compile the actual leaf with its own ORIGIN brush in an isolated room."""
    spec = importlib.util.spec_from_file_location('door_source_geometry', REPO / 'Design-Source/Daragoth-Plains/build_daragoth_plains.py')
    geometry = importlib.util.module_from_spec(spec); spec.loader.exec_module(geometry)
    folder = out / 'leaf-source/msr/maps'
    folder.mkdir(parents=True, exist_ok=True)
    (folder.parent / 'liblist.gam').write_text('game "MSR isolated wooden door compiler"\n', encoding='ascii')
    wad = folder.parent / 'house-door.wad'
    wood = next(t.raw for t in base.textures if t.name == 'DPWOOD')
    if wood is None or struct.unpack_from('<I', wood, 24)[0] == 0:
        raise ValueError('Accepted DPWOOD must be embedded')
    textures = [('DPWOOD', wood), ('ORIGIN', b'ORIGIN'.ljust(16, b'\0') + wood[16:])]
    body, directory = bytearray(), bytearray()
    for name, raw in textures:
        directory.extend(struct.pack('<iiiBBBB16s', 12 + len(body), len(raw), len(raw), 0x43, 0, 0, 0, name.encode().ljust(16, b'\0')))
        body.extend(raw)
    wad.write_bytes(struct.pack('<4sii', b'WAD3', len(textures), 12 + len(body)) + body + directory)
    room = [((-272, -272, -144), (272, 272, -128)),
            ((-272, -272, 192), (272, 272, 208)),
            ((-272, -272, -128), (-256, 272, 192)),
            ((256, -272, -128), (272, 272, 192)),
            ((-256, -272, -128), (256, -256, 192)),
            ((-256, 256, -128), (256, 272, 192))]
    values = {'classname': 'worldspawn', 'mapversion': '220', 'wad': str(wad.resolve()).replace('\\', '/'),
              'MaxRange': '1024', '_light': '0'}
    text = geometry.entity(values, [geometry.box(a, b, 'DPWOOD', 1) for a, b in room])
    text += geometry.entity(door_values('isolated_leaf', (0, 0, 0), geometry.origin), door_brushes(geometry.box, (0, 0, 0)))
    for x, y in ((128, 64), (-128, 64), (0, -128), (0, 128)):
        text += geometry.entity({'classname': 'light', 'origin': geometry.origin(x, y, 112), '_light': '255 224 184 180'})
    map_path = folder / 'house-door-leaf.map'
    map_path.write_text(text, encoding='ascii')
    commands = [('pxcsg', ['-threads', '1', '-nowadtextures', str(map_path)]),
                ('pxbsp', ['-threads', '1', str(map_path.with_suffix('.bsp'))]),
                ('pxvis', ['-fast', '-threads', '1', str(map_path.with_suffix('.bsp'))]),
                ('pxrad', ['-threads', '1', '-bounce', '0', '-ambient', '.15', '.15', '.15', str(map_path.with_suffix('.bsp'))])]
    logs = []
    for name, args in commands:
        executable = tools / (name + '.exe')
        result = subprocess.run([str(executable), *args], cwd=folder, capture_output=True, text=True, errors='replace')
        logs.append({'tool': str(executable), 'tool_sha256': sha(executable.read_bytes()), 'args': args,
                     'returncode': result.returncode, 'output': result.stdout + result.stderr})
        (folder / 'compile-log.json').write_text(json.dumps(logs, indent=2) + '\n')
        if result.returncode or any(token in logs[-1]['output'] for token in ('failed to load', "couldn't init game directory", 'LEAK', 'Error:')):
            raise ValueError('Isolated ' + name + ' failed: ' + result.stdout[-3000:] + result.stderr[-3000:])
    compiled_path = map_path.with_suffix('.bsp')
    bsp = BSP.load(compiled_path)
    doors = [e for e in bsp.entities if e.classname == 'func_door_rotating']
    if len(doors) != 1 or len(bsp.models) != 2 or doors[0].get('model') != '*1' or tuple(map(float, doors[0].get('origin').split())) != (0, 0, 0):
        raise ValueError('Compiler did not preserve the isolated ORIGIN pivot')
    model = bsp.models[1]
    points = [p for f in bsp.faces[model.firstface:model.firstface + model.numfaces] for p in polygon(bsp, f)]
    actual_lo = tuple(min(p[k] for p in points) for k in range(3))
    actual_hi = tuple(max(p[k] for p in points) for k in range(3))
    if actual_lo != LEAF_MINS or actual_hi != LEAF_MAXS or model.numfaces != 6:
        raise ValueError('Compiled door leaf differs from the authored 6x72x90 shape')
    return bsp, {'map_path': str(map_path.resolve()), 'map_sha256': sha(map_path.read_bytes()),
                 'wad_path': str(wad.resolve()), 'wad_sha256': sha(wad.read_bytes()),
                 'bsp_path': str(compiled_path.resolve()), 'bsp_sha256': sha(compiled_path.read_bytes()),
                 'entity': doors[0].pairs, 'model_bounds': [model.mins, model.maxs],
                 'model_origin': model.origin, 'vertex_bounds': [actual_lo, actual_hi], 'compiler_commands': logs}


def sample_step(bsp, texinfo):
    index = bsp.texinfo[texinfo].flags >> 16
    extra = bsp.extra_lumps.get(1, b'')
    return struct.unpack_from('<H', extra, index * 22 + 16)[0] if index >= 0 and len(extra) >= (index + 1) * 22 else 16


def build(base, out, tools):
    if out.resolve() != ALLOWED_OUT.resolve():
        raise ValueError('Door build is limited to the isolated house-doors lab directory')
    data = base.read_bytes()
    if sha(data) != BASE_SHA:
        raise ValueError('Use the frozen accepted8388 map as the base')
    target = out / 'daragoth_meadow_house_doors.bsp'
    if target.exists() or target.resolve() == base.resolve():
        raise ValueError('Do not overwrite an accepted map or existing candidate')
    old = BSP.load(base)
    if len(old.entities) != 1047 or len(old.models) != 165 or not old.bsp30ext:
        raise ValueError('Unexpected accepted map inventory')
    if sum(e.classname in ('func_door', 'func_door_rotating') for e in old.entities) != 8:
        raise ValueError('The eight original doors must be preserved')
    source, compiler = isolated_leaf(old, out, tools)
    model = source.models[1]
    faces = list(range(model.firstface, model.firstface + model.numfaces))
    face_set = set(faces)
    leaves = set()
    nodes = sorted(closure(source.nodes, model.headnode[0], leaves))
    leaves = sorted(leaves)
    clips = sorted(set().union(*(closure(source.clipnodes, h) for h in model.headnode[1:])))
    for i in nodes:
        n = source.nodes[i]
        if not set(range(n.firstface, n.firstface + n.numfaces)) <= face_set:
            raise ValueError('Door hull refers to non-door render faces')
    for i in leaves:
        leaf = source.leafs[i]
        marks = source.marksurfaces[leaf.firstmarksurface:leaf.firstmarksurface + leaf.nummarksurfaces]
        # PrimeXT's global solid leaf0 has visofs0; it has no faces/PVS meaning.
        # The new private model leaf stores -1 while retaining its SOLID content.
        if (leaf.contents != -2 and leaf.visofs != -1) or not set(marks) <= face_set:
            raise ValueError('Door leaf has foreign room/PVS data')
    edges = sorted({abs(e) for i in faces for e in source.surfedges[source.faces[i].firstedge:source.faces[i].firstedge + source.faces[i].numedges]})
    vertices = sorted({v for e in edges for v in source.edges[e]})
    textures = sorted({source.faces[i].texinfo for i in faces})
    planes = sorted({source.faces[i].planenum for i in faces} | {source.nodes[i].planenum for i in nodes} | {source.clipnodes[i].planenum for i in clips})
    groups = {'planes': (planes, len(old.planes)), 'vertices': (vertices, len(old.vertexes)),
              'edges': (edges, len(old.edges)), 'texinfos': (textures, len(old.texinfo)),
              'faces': (faces, len(old.faces)), 'nodes': (nodes, len(old.nodes)),
              'leaves': (leaves, len(old.leafs)), 'clipnodes': (clips, len(old.clipnodes))}
    maps = {name: {i: start + k for k, i in enumerate(ids)} for name, (ids, start) in groups.items()}
    pm, vm, em, tm, fm, nm, lm, cm = (maps[name] for name in ('planes', 'vertices', 'edges', 'texinfos', 'faces', 'nodes', 'leaves', 'clipnodes'))
    if any(max(m.values(), default=0) >= (32768 if name in ('nodes', 'leaves', 'texinfos') else 65536)
           for name, m in maps.items() if name != 'clipnodes'):
        raise ValueError('Appended door exceeds BSP30 index budgets')
    directory = [struct.unpack_from('<2i', data, 4 + i * 8) for i in range(15)]
    raw = [data[o:o + n] for o, n in directory]
    if len(raw[9]) != len(old.clipnodes) * CLIPNODE32.size:
        raise ValueError('Accepted map needs the existing32-bit clipnode format')
    payload = {i: bytearray() for i in CHANGED}
    for i in planes:
        p = source.planes[i]; payload[1].extend(PLANE.pack(*p.normal, p.dist, p.type))
    for i in vertices:
        payload[3].extend(VERTEX.pack(*source.vertexes[i]))
    texture_map = {t.name: i for i, t in enumerate(old.textures)}
    light = bytearray()
    lightmaps = []
    for i in textures:
        ti = source.texinfo[i]; name = source.textures[ti.miptex].name
        if name != 'DPWOOD' or source.textures[ti.miptex].raw != old.textures[texture_map[name]].raw:
            raise ValueError('Isolated door texture is not the exact accepted DPWOOD')
        step = sample_step(source, i)
        if step != 16:
            raise ValueError('New door must use ordinary16-unit lightmap samples')
        # Sentinel faceinfo=-1 avoids accidentally reusing base faceinfo0/64.
        flags = (ti.flags & 0xffff) - 65536
        payload[6].extend(TEXINFO.pack(*ti.vecs[0], *ti.vecs[1], texture_map[name], flags))
    for i in edges:
        payload[12].extend(EDGE.pack(*(vm[v] for v in source.edges[i])))
    for i in faces:
        f = source.faces[i]
        if f.styles != [0, 255, 255, 255] or f.lightofs < 0:
            raise ValueError('New wooden door requires ordinary compiled style0 lighting')
        points = polygon(source, f); ti = source.texinfo[f.texinfo]
        ext = [(math.floor(min(sum(p[k] * v[k] for k in range(3)) + v[3] for p in points) / 16),
                math.ceil(max(sum(p[k] * v[k] for k in range(3)) + v[3] for p in points) / 16)) for v in ti.vecs]
        size = (ext[0][1] - ext[0][0] + 1) * (ext[1][1] - ext[1][0] + 1) * 3
        lightofs = len(old.lighting) + len(light)
        samples = source.lighting[f.lightofs:f.lightofs + size]
        if len(samples) != size:
            raise ValueError('Door lightmap range is invalid')
        light.extend(samples)
        lightmaps.append({'source_face': i, 'face': fm[i], 'source_lightofs': f.lightofs,
                          'lightofs': lightofs, 'bytes': size, 'sample_step': 16, 'extents': ext})
        firstedge = len(old.surfedges) + len(payload[13]) // 4
        for e in source.surfedges[f.firstedge:f.firstedge + f.numedges]:
            payload[13].extend(struct.pack('<i', em[abs(e)] * (1 if e >= 0 else -1)))
        payload[7].extend(FACE.pack(pm[f.planenum], f.side, firstedge, f.numedges, tm[f.texinfo], *f.styles, lightofs))
    payload[8].extend(light)
    for i in leaves:
        l = source.leafs[i]; firstmark = len(old.marksurfaces) + len(payload[11]) // 2
        for f in source.marksurfaces[l.firstmarksurface:l.firstmarksurface + l.nummarksurfaces]:
            payload[11].extend(struct.pack('<H', fm[f]))
        if firstmark >= 65536:
            raise ValueError('Door marks exceed leaf index budget')
        payload[10].extend(LEAF.pack(l.contents, -1, *l.mins, *l.maxs, firstmark, l.nummarksurfaces, *l.ambient))
    for i in nodes:
        n = source.nodes[i]; children = [nm[c] if c >= 0 else -1 - lm[-1 - c] for c in n.children]
        firstface = fm[n.firstface] if n.numfaces else len(old.faces)
        payload[5].extend(NODE.pack(pm[n.planenum], *children, *n.mins, *n.maxs, firstface, n.numfaces))
    for i in clips:
        c = source.clipnodes[i]; payload[9].extend(CLIPNODE32.pack(pm[c.planenum], *(cm[ch] if ch >= 0 else ch for ch in c.children)))
    new_model = len(old.models)
    heads = [nm[model.headnode[0]], *(cm[h] if h >= 0 else h for h in model.headnode[1:])]
    payload[14].extend(MODEL.pack(*model.mins, *model.maxs, *model.origin, *heads, model.visleafs, fm[model.firstface], model.numfaces))
    entities = [Entity([pair.copy() for pair in e.pairs]) for e in old.entities]
    placements = []
    for identifier, hinge in zip(DOOR_IDS, HINGES):
        values = door_values(identifier, hinge, origin, f'*{new_model}')
        index = len(entities); entities.append(Entity([[k, v] for k, v in values.items()]))
        placements.append({'identifier': identifier, 'targetname': values['targetname'], 'entity_index': index,
                           'hinge': hinge, 'angles': [0, 0, 0], 'opening_yaws': [-90, 90],
                           'outside_direction': 'east' if identifier not in ('cottage_south', 'cottage_north') else 'west'})
    payload[0] = bytearray(format_entities(entities))
    output = bytearray(data)
    for i in CHANGED:
        output.extend(b'\0' * (-len(output) % 4)); at = len(output)
        blob = bytes(payload[i]) if i == 0 else raw[i] + bytes(payload[i])
        output.extend(blob); struct.pack_into('<2i', output, 4 + i * 8, at, len(blob))
    prefix = bytearray(output[:len(data)])
    for i in CHANGED:
        prefix[4 + i * 8:12 + i * 8] = data[4 + i * 8:12 + i * 8]
    if prefix != data or sha(base.read_bytes()) != BASE_SHA:
        raise ValueError('Accepted source changed during door build')
    for i in range(1, 15):
        at, n = struct.unpack_from('<2i', output, 4 + i * 8)
        if output[at:at + len(raw[i])] != raw[i]:
            raise ValueError('Original geometry/collision prefix was changed')
    target.write_bytes(output)
    result = BSP.load(target)
    if [e.pairs for e in result.entities[:1047]] != [e.pairs for e in old.entities]:
        raise ValueError('An old ordered entity record changed')
    report = {'base_sha256': BASE_SHA, 'output_sha256': sha(output), 'output_path': str(target.resolve()),
              'builder_source_sha256': sha(Path(__file__).read_bytes()),
              'shared_source_sha256': sha((Path(__file__).parent / 'house_doors.py').read_bytes()),
              'village_generator_sha256': sha((Path(__file__).parent / 'village.py').read_bytes()),
              'changed_lumps': list(CHANGED), 'compiler': compiler, 'new_model': new_model,
              'new_model_headnodes': heads, 'model_bounds': [model.mins, model.maxs], 'leaf_vertex_bounds': [LEAF_MINS, LEAF_MAXS],
              'record_mappings': maps, 'appended_record_counts': {name: len(ids) for name, (ids, start) in groups.items()},
              'appended_lump_bytes': {str(i): len(payload[i]) for i in CHANGED if i != 0},
              'lightmaps': lightmaps, 'placements': placements, 'door_settings': DOOR_SETTINGS,
              'old_entities_preserved': 1047, 'new_entities': len(entities), 'existing_doors_preserved': 8,
              'world_model_and_all_old_non_entity_prefixes_preserved': True,
              'source_file_prefix_preserved_except_changed_descriptors': True,
              'native_use_swing_policy': 'DoorGoUp chooses +/-90 away from player; both opening directions need native checks',
              'doorway_side_clearance_units': 4,
              'requires_independent_and_native_verification': True}
    (out / 'house-doors-build-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('output_sha256', 'new_model', 'new_model_headnodes', 'appended_record_counts', 'new_entities')}, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--out', type=Path, default=ALLOWED_OUT)
    parser.add_argument('--tools', type=Path, default=TOOLS)
    args = parser.parse_args()
    build(args.base, args.out, args.tools)
