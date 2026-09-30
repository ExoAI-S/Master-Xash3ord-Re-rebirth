"""Add original plains scripts to a copy of MSR's custom script library.

MSR's scripts.pak uses a 12-byte PACK header whose final integer is an entry
count, followed by 264-byte name/offset/length records. It is not a Quake PAK.
The input is read-only; every existing entry's content is preserved exactly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def read_library(path):
    data = path.read_bytes()
    magic, directory, count = struct.unpack_from('<4sii', data)
    if magic != b'PACK' or count < 1 or directory < 12 or directory + count * 264 > len(data):
        raise ValueError('Invalid MSR script library header')
    entries = []
    seen = set()
    for i in range(count):
        raw_name, offset, size = struct.unpack_from('<256sii', data, directory + i * 264)
        name = raw_name.split(b'\0', 1)[0].decode('ascii')
        if not name or name in seen or offset < 12 or size < 0 or offset + size > len(data):
            raise ValueError(f'Invalid or duplicate script record: {name}')
        seen.add(name)
        entries.append((name, data[offset:offset + size]))
    return entries


def build_library(base, destination):
    original = read_library(base)
    additions = {p.relative_to(ROOT / 'Scripts').as_posix(): p.read_bytes()
                 for p in sorted((ROOT / 'Scripts').rglob('*.script'))}
    if any(name in additions for name, _ in original):
        raise ValueError('The base already contains plains scripts; supply the unmodified base library')
    records = original + list(additions.items())
    offset = 12 + len(records) * 264
    directory = bytearray()
    payload = bytearray()
    for name, content in records:
        encoded = name.encode('ascii')
        if len(encoded) >= 256:
            raise ValueError(f'Script name too long: {name}')
        directory.extend(struct.pack('<256sii', encoded, offset + len(payload), len(content)))
        payload.extend(content)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(struct.pack('<4sii', b'PACK', 12, len(records)) + directory + payload)
    rebuilt = dict(read_library(destination))
    assert all(rebuilt[name] == content for name, content in original)
    assert all(rebuilt[name] == content for name, content in additions.items())
    report = {'base_library_sha256': hashlib.sha256(base.read_bytes()).hexdigest(),
              'output_library_sha256': hashlib.sha256(destination.read_bytes()).hexdigest(),
              'original_entries': len(original), 'original_entries_preserved': True,
              'added_scripts': {name: hashlib.sha256(content).hexdigest() for name, content in additions.items()},
              'output_entries': len(records), 'output_bytes': destination.stat().st_size}
    destination.with_name('daragoth_plains-script-report.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--out', type=Path, default=ROOT / 'generated' / 'msr' / 'scripts.pak')
    args = parser.parse_args()
    if args.base.resolve() == args.out.resolve():
        parser.error('The output must differ from the base script library')
    print(json.dumps(build_library(args.base, args.out), indent=2))


if __name__ == '__main__':
    main()
