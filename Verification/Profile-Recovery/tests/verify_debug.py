"""Verify the actual PE CodeView record against native PDB stream 1."""
import json
import math
import pathlib
import struct
import uuid

BASE = pathlib.Path(__file__).resolve().parent.parent

def u32(data, offset):
    return struct.unpack_from('<I', data, offset)[0]

def verify(name):
    exe = BASE / name / 'MSR-Launcher.exe'
    pdb = exe.with_suffix('.pdb')
    data = exe.read_bytes()
    pe = u32(data, 0x3c)
    assert data[pe:pe + 4] == b'PE\0\0'
    section_count = struct.unpack_from('<H', data, pe + 6)[0]
    optional_size = struct.unpack_from('<H', data, pe + 20)[0]
    opt = pe + 24
    magic = struct.unpack_from('<H', data, opt)[0]
    directories = opt + (96 if magic == 0x10b else 112)
    debug_rva, debug_size = struct.unpack_from('<II', data, directories + 6 * 8)
    sections = opt + optional_size
    def raw(rva):
        for index in range(section_count):
            base = sections + index * 40
            virtual_size, va, raw_size, ptr = struct.unpack_from('<IIII', data, base + 8)
            if va <= rva < va + max(virtual_size, raw_size):
                return ptr + rva - va
        raise AssertionError('Unmapped RVA')
    codeview = []
    for offset in range(raw(debug_rva), raw(debug_rva) + debug_size, 28):
        kind, size, address, pointer = struct.unpack_from('<IIII', data, offset + 12)
        if kind == 2:
            record = data[pointer:pointer + size]
            assert record[:4] == b'RSDS'
            codeview.append((record[4:20], u32(record, 20)))
    assert len(codeview) == 1
    p = pdb.read_bytes()
    assert p.startswith(b'Microsoft C/C++ MSF 7.00\r\n\x1aDS\0\0\0')
    block_size, directory_size, block_map = u32(p, 32), u32(p, 44), u32(p, 52)
    blocks = [u32(p, block_map * block_size + i * 4) for i in range(math.ceil(directory_size / block_size))]
    directory = b''.join(p[b * block_size:(b + 1) * block_size] for b in blocks)[:directory_size]
    count = u32(directory, 0)
    sizes = [u32(directory, 4 + 4 * i) for i in range(count)]
    cursor = 4 + 4 * count
    streams = []
    for size in sizes:
        n = 0 if size == 0xffffffff else math.ceil(size / block_size)
        ids = [u32(directory, cursor + 4 * i) for i in range(n)]
        cursor += 4 * n
        streams.append(b''.join(p[b * block_size:(b + 1) * block_size] for b in ids)[:size])
    info = streams[1]
    guid, age = info[12:28], u32(info, 8)
    assert codeview[0] == (guid, age), 'EXE/PDB mismatch'
    return {'build': name, 'status': 'PASS', 'guid': str(uuid.UUID(bytes_le=guid)), 'age': age, 'pe_codeview_matches_pdb_stream_1': True}

if __name__ == '__main__':
    result = {'status': 'PASS', 'pairs': [verify('baseline'), verify('package')]}
    (BASE / 'tests' / 'debug-pair-results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
