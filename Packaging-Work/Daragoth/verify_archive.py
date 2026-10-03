"""Check a completed Daragoth release ZIP without extracting user state."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

from prepare_release import PINS, TAG, private_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.archive.stat().st_size >= 2 * 1024**3:
        raise RuntimeError('Single asset exceeds the release upload limit')
    with zipfile.ZipFile(args.archive) as archive:
        infos = archive.infolist()
        counts = Counter(info.filename.lower() for info in infos)
        if any(count != 1 for count in counts.values()):
            raise RuntimeError('Duplicate or case-colliding ZIP entries')
        members = {}
        for info in infos:
            name = info.filename
            if not name.startswith('MSR/') or '..' in PurePosixPath(name).parts or '\\' in name:
                raise RuntimeError('Unsafe ZIP path')
            rel = name[4:]
            if private_path(rel):
                raise RuntimeError('Private runtime data in ZIP: ' + rel)
            if not info.is_dir():
                members[rel] = info
        manifest = json.loads(archive.read('MSR/RELEASE-MANIFEST.json'))
        if manifest['release'] != TAG or manifest['source_dirty']:
            raise RuntimeError('Final source commit not recorded in release manifest')
        expected = manifest['files']
        if set(members) != set(expected) | {'RELEASE-MANIFEST.json'}:
            raise RuntimeError('ZIP inventory differs from staged manifest')
        for rel, item in expected.items():
            if members[rel].file_size != item['bytes']:
                raise RuntimeError('ZIP member size differs: ' + rel)
            # Reading through EOF validates the ZIP CRC as well as the pinned
            # stage SHA256; ZIP CRC alone cannot detect stale same-size content.
            with archive.open('MSR/' + rel) as stream:
                actual_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
            if actual_hash != item['sha256']:
                raise RuntimeError('ZIP member SHA256 differs: ' + rel)
        for rel, expected_hash in PINS.items():
            if hashlib.sha256(archive.read('MSR/Portable-Package/game/' + rel)).hexdigest() != expected_hash:
                raise RuntimeError('Runtime pin mismatch: ' + rel)
        for item in manifest['source_overlay'].values():
            if hashlib.sha256(archive.read('MSR/' + item['package_path'])).hexdigest() != item['sha256']:
                # Runtime assets may supersede older tracked development placeholders.
                runtime_rel = item['package_path'].removeprefix('Portable-Package/game/')
                if runtime_rel not in manifest['runtime_overlay']:
                    raise RuntimeError('Source overlay mismatch: ' + item['package_path'])
        required = {'MSR-Launcher.exe', 'Play-MSR.cmd', 'Play-Daragoth.cmd',
                    'Play-Realm-One.cmd', 'Play-Realm-Two.cmd',
                    'Create-Desktop-Shortcuts.cmd', 'Launcher/native_host.py',
                    'Portable-Package/runtime/python.exe',
                    'Portable-Package/game/msr/bigworld.enable',
                    'Portable-Package/game/msr/maps/daragoth_load.cfg',
                    'Design-Source/Mounts/Textured-Horse/LICENSE.txt',
                    'Source/msr_source/src/game/server/msr_encounters.inc',
                    'Source/msr_source/src/game/client/render/scenery_distance.cpp'}
        if not required <= members.keys():
            raise RuntimeError('Required complete-game files missing')
        if 'Portable-Package/game/msr/maps/daragoth.ent' in members:
            raise RuntimeError('Stale entity override in ZIP')
    with args.archive.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    report = dict(release=TAG, archive=args.archive.name, bytes=args.archive.stat().st_size,
                  sha256=digest, source_commit=manifest['source_commit'],
                  entries=len(infos), files=len(members), runtime_pins=len(PINS),
                  source_overlay_files=len(manifest['source_overlay']),
                  full_zip_crc_test='passed', full_manifest_sha256_check='passed',
                  inventory_and_privacy_check='passed',
                  runtime_and_source_hash_check='passed')
    args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    args.archive.with_suffix('.zip.sha256').write_text(
        digest + '  ' + args.archive.name + '\n', encoding='ascii')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
