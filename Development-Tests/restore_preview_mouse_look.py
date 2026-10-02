"""One-time, backed-up restoration of the missing preview +mlook setting.

Close the interactive preview first. This is an explicit repair, never a
mount/dismount hook. Other bindings/cvars, player identity and saves are untouched.
"""
import argparse, hashlib, json, os, re
from pathlib import Path

def sha(data): return hashlib.sha256(data).hexdigest()

def restore(game, backup):
    path = game.resolve()/'msr/config.cfg'
    original = path.read_bytes()
    if re.search(rb'(?m)^\s*\+mlook\s*\r?$', original):
        return {'changed':False, 'reason':'Mouse look already enabled.', 'sha256':sha(original)}
    if re.search(rb'(?m)^\s*-mlook\s*\r?$', original):
        raise RuntimeError('Config explicitly disables mouse look; leave that preference intact.')
    newline = b'\r\n' if b'\r\n' in original else b'\n'
    match = re.search(rb'(?m)^exec userconfig\.cfg\s*\r?$', original)
    offset = match.start() if match else len(original)
    prefix = original[:offset]
    if prefix and not prefix.endswith(b'\n'): prefix += newline
    replacement = prefix + b'+mlook' + newline + original[offset:]
    backup.mkdir(parents=True, exist_ok=True)
    saved = backup/'config.cfg'
    with saved.open('xb') as stream: stream.write(original)
    temporary = path.with_name('config.cfg.mouse-look-repair')
    with temporary.open('xb') as stream: stream.write(replacement)
    os.replace(temporary,path)
    if path.read_bytes() != replacement: raise RuntimeError('Config repair verification failed')
    return {'changed':True, 'before_sha256':sha(original), 'after_sha256':sha(replacement),
            'backup':str(saved), 'setting_restored':'+mlook', 'other_config_bytes_preserved':True}

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game',type=Path,required=True)
    parser.add_argument('--backup',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(restore(args.game,args.backup),indent=2))
