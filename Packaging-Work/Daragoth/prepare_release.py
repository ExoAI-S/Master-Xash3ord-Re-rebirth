"""Overlay a verified, extracted complete base without collecting live user data.

Extract MSR-BigWorld5-Complete-2026-09-27.zip first into an empty staging parent.
This tool accepts that parent's MSR directory, never a running installation.
The base archive SHA256 is pinned below and must be checked before extraction.
Only explicit game artifacts are read from the tested runtime. Source changes
are taken from Git's inventory, including pending changes, and prefix-mapped.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]
BASE_COMMIT = '85fc2db63c59aa2e57a7f36736088c294f5e4c11'
BASE_SHA256 = 'c8773b6da9705b3f287ffa5b54a15e0f7c7ae713c4a9458950d3ac0d34a46098'
TAG = 'v2026.10.03-daragoth-plains'
PINS = {
    'xash.dll': '6b3655350129760f4b2c7dc617c7edcfc918043528c97b843542b16abf24273e',
    'xash.pdb': 'a39bb9d5f750c0f6e994ebfe8cb839f62385309217e6778d48b8d954f8dab979',
    'msr/maps/daragoth.bsp': '67946ff32b0f9ecf1410ca0791c59ded09dfbfd6c34cea6db87be679ff7775b6',
    'msr/scripts.pak': '6af5761670d1d71cf395c224c68d3ae01fadef00b3928295306977a1d39a5ca9',
    'msr/delta.lst': 'd672b06736627abaa325c8dd105a5adaf82ff5e34312e77f83550cd6ca6e496f',
    'msr/dlls/ms.dll': '8a09d371260d33aca883c95239b300c5e23d84ef088e79189b35a71a88221cf7',
    'msr/dlls/ms.pdb': '07233e43397703a7a001a757e30f47827cbfb3487806648d9decdf6dbe4b0cdc',
    'msr/cl_dlls/client.dll': 'c943dfb3c35624471db0f7b5b7d9030d5b109282115c80f9ac908c66fdcf3fe2',
    'msr/cl_dlls/client.pdb': 'df7ec3cdfc82be1c203939f7418424bc818dda91b4aeabce79ff8f2e42c77895',
    'msr/models/mounts/plains_horse.mdl': '7b109d3f5228be595ada6f5f23c4cb941cb24bfcafb3f1db9dabb6311089c014',
}


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def git(*args):
    return subprocess.check_output(['git', *args], cwd=REPO).decode('utf-8')


def inside(root, relative):
    path = (root / relative).resolve()
    if path == root or not path.is_relative_to(root) or path.is_symlink():
        raise ValueError('Unsafe staging path: ' + str(relative))
    return path


def private_path(relative):
    parts = relative.lower().split('/')
    name = parts[-1]
    return (name in {'player-profile.json', '.xash_id', 'host-state.json',
                     'host-settings.json', 'client-state.json', 'test-rcon.key'}
            or name.startswith('private_') and name.endswith('.cfg')
            or name.endswith(('.sqlite', '.sqlite3', '.db', '.dmp', '.pyc'))
            or any(part in {'.host-private', '__pycache__', 'save', 'saves',
                           'savegames', 'scrshots', 'crashdumps'} for part in parts)
            or '/fn/data/' in relative.lower() or '/fn/backups/' in relative.lower())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', type=Path, required=True, help='extracted stage/MSR directory')
    parser.add_argument('--runtime', type=Path, required=True, help='tested game directory (read only)')
    parser.add_argument('--base', type=Path, required=True)
    args = parser.parse_args()
    root, runtime = args.stage.resolve(), args.runtime.resolve()
    if (root.name != 'MSR' or root.parent.name != 'stage' or root == runtime
            or runtime.is_relative_to(root) or root.is_relative_to(runtime)):
        parser.error('Use a separate stage/MSR directory')
    if not (root / 'MSR-Launcher.exe').is_file() or not (root / 'Source').is_dir():
        parser.error('Expected an extracted complete game base')
    if sha(args.base) != BASE_SHA256:
        parser.error('Complete base ZIP hash does not match the approved release')
    for rel, expected in PINS.items():
        if sha(runtime / rel) != expected:
            raise RuntimeError('Tested runtime hash mismatch: ' + rel)

    changed = set(git('diff', '--name-only', '-z', BASE_COMMIT).split('\0'))
    changed.update(git('ls-files', '--others', '--exclude-standard', '-z').split('\0'))
    changed.discard('')
    source_overlay = {}
    for rel in sorted(changed | {'README.md', 'THIRD-PARTY-NOTICES.md',
                                'Packaging-Work/transfer_fn_state.py'}):
        if private_path(rel):
            raise RuntimeError('Refusing private source path: ' + rel)
        if rel.startswith(('Stable-Base/', 'Recovery/')):
            raise RuntimeError('Recovery changes need separate review: ' + rel)
        dst_rel = 'Source/' + rel[len('Full-Source/'):] if rel.startswith('Full-Source/') else rel
        src, dst = REPO / rel, inside(root, dst_rel)
        if src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            source_overlay[rel] = dict(package_path=dst_rel, sha256=sha(src))
        elif dst.is_file():
            dst.unlink()

    assets = set(PINS)
    assets.add('msr/daragoth_plains.wad')
    model_paths = sorted((runtime / 'msr/models/plains').glob('*.mdl'))
    if len(model_paths) != 92:
        raise RuntimeError('Expected all 92 tested plains models')
    assets.update(path.relative_to(runtime).as_posix() for path in model_paths)
    runtime_overlay = {}
    for rel in sorted(assets):
        src, dst = runtime / rel, inside(root, 'Portable-Package/game/' + rel)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        runtime_overlay[rel] = dict(sha256=sha(dst), bytes=dst.stat().st_size)

    # These operations apply solely within the newly extracted, verified stage.
    retired = ['Install-BigWorld.cmd', 'Uninstall-BigWorld.cmd',
               'MSR-BigWorld-20260927-1032', 'BigWorld-Backup',
               'Portable-Package/game/msr/maps/daragoth.ent',
               'Portable-Package/game/msr/console_history.txt']
    for rel in retired:
        target = inside(root, rel)
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
    historical = inside(root, 'Release/Historical')
    historical.mkdir(parents=True, exist_ok=True)
    for name in ('PACKAGE-MANIFEST.json', 'FINAL-MERGE.json', 'DEBUG-BUILD.json'):
        src = inside(root, name)
        dst = historical / ('pre-Daragoth-' + name)
        if src.exists():
            if dst.exists():
                raise RuntimeError('Historical receipt exists unexpectedly: ' + name)
            shutil.move(src, dst)
    (historical / 'README.md').write_text(
        '# Historical receipts\n\nThese describe earlier releases, not the current runtime. '
        'Use RELEASE-MANIFEST.json at the package root for this release.\n', encoding='utf-8')

    portable = root / 'Portable-Package'
    subprocess.run([str(portable / 'runtime/python.exe'), '-B',
                    str(portable / 'FN/fn_server.py'), 'manifest', '--game',
                    str(portable / 'game/msr')], cwd=portable, check=True)
    manifest = json.loads((portable / 'FN/content-manifest.json').read_text(encoding='utf-8'))
    if manifest['scripts_crc32'] != 4199339986 or manifest['maps']['daragoth'] != 1139436697:
        raise RuntimeError('FN content approval does not match tested artifacts')
    subprocess.run([str(portable / 'runtime/python.exe'), '-B',
                    str(portable / 'FN/check_content.py')], cwd=portable, check=True)

    files = {}
    for path in sorted(root.rglob('*')):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if private_path(rel):
            raise RuntimeError('Private/generated state found in stage: ' + rel)
        if rel == 'RELEASE-MANIFEST.json':
            continue
        files[rel] = dict(bytes=path.stat().st_size, sha256=sha(path))
        if len(files) % 5000 == 0:
            print('Hashed %s package files' % len(files), flush=True)
    receipt = dict(release=TAG, base_commit=BASE_COMMIT, base_zip_sha256=BASE_SHA256,
                   source_commit=git('rev-parse', 'HEAD').strip(),
                   source_dirty=bool(git('status', '--porcelain').strip()),
                   source_overlay=source_overlay, runtime_overlay=runtime_overlay,
                   retired=retired, files=files,
                   note='File manifest excludes itself. Original development reports are historical evidence; consult current release notes for test limits.')
    (root / 'RELEASE-MANIFEST.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(release=TAG, files=len(files), runtime_overlay=len(runtime_overlay),
                          source_overlay=len(source_overlay), fn_maps=len(manifest['maps']))))


if __name__ == '__main__':
    main()
