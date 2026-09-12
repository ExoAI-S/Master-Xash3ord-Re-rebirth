"""Verify the frozen baseline against hashes from the original handoff ZIP."""
import argparse
import hashlib
import json
from pathlib import Path

def verify(all_assets=False):
    root=Path(__file__).resolve().parent.parent
    manifest=json.loads((root/'Packaging-Work/stable-base-manifest.json').read_text())
    critical={'game/xash3d.exe','game/msr/cl_dlls/client.dll','game/msr/dlls/ms.dll','game/msr/scripts.pak'}
    content_extensions={'.dll','.exe','.bsp','.mdl','.wad','.pak','.spr','.tga','.wav','.mp3'}
    checked=0
    for relative,record in manifest['files'].items():
        if relative not in critical and not (all_assets and relative.startswith('game/') and Path(relative).suffix.lower() in content_extensions):
            continue
        path=root/'Stable-Base'/relative
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=record['sha256']:
            raise ValueError(f'Stable base differs from the handoff: {relative}. Restore it from the original ZIP.')
        checked+=1
    print(f'Stable base verified: {checked} original game files match the handoff.')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--all-assets',action='store_true')
    verify(p.parse_args().all_assets)
