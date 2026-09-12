"""Show the private FN account number without exposing its profile key."""
import json
from pathlib import Path
import re

def account_id(key):
    if not isinstance(key, str) or not re.fullmatch('[0-9a-f]{32}', key):
        raise ValueError('Invalid profile key; restore player-profile.json from backup.')
    value = 14695981039346656037
    for char in key.encode('ascii'):
        value = ((value ^ char) * 1099511628211) & (2**64 - 1)
    return value | 2**63

if __name__ == '__main__':
    path = Path(__file__).resolve().parent.parent / 'player-profile.json'
    if not path.exists():
        raise SystemExit('Use Play-Local.cmd or Join-Server.cmd once to create your profile.')
    profile = json.loads(path.read_text(encoding='utf-8-sig'))
    print('Private FN account:', account_id(profile['profile_key']))
    print('Back up player-profile.json together with FN/data. Keep the profile key private.')
