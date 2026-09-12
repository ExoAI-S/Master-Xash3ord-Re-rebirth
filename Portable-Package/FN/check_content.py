"""Refuse to start realms if their approved FN content no longer matches."""
import json
from pathlib import Path

from fn_server import crc32_file

def validate(game, manifest, maps):
    errors = []
    if crc32_file(game / 'scripts.pak') != manifest['scripts_crc32']:
        errors.append('scripts.pak differs from the FN approved checksum')
    for name in maps:
        if crc32_file(game / 'maps' / (name + '.bsp')) != manifest['maps'].get(name):
            errors.append(name + ' differs from the FN approved checksum')
    return errors

if __name__ == '__main__':
    root = Path(__file__).resolve().parent.parent
    manifest = json.loads((root / 'FN/content-manifest.json').read_text(encoding='utf-8-sig'))
    settings_path = root / 'host-settings.json'
    maps = {'edana'}
    if settings_path.exists():
        settings = json.loads(settings_path.read_text(encoding='utf-8-sig'))
        maps.update(server['map'] for server in settings.get('servers', []))
    errors = validate(root / 'game/msr', manifest, maps)
    if errors:
        raise SystemExit('; '.join(errors))
    print('FN approved scripts and starting maps match installed content.')
