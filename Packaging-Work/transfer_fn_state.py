"""Transfer saves between stopped versions, retaining both prior databases."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sqlite3

def snapshot(source, target):
    with closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)) as src:
        with closing(sqlite3.connect(target)) as dst:
            src.backup(dst)
            if dst.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                raise ValueError('FN database integrity check failed')
            dst.execute('PRAGMA journal_mode=DELETE')

def schema(path):
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as db:
        return db.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()

def transfer(source, destination, backup_root):
    src=(source/'FN/data/FN.sqlite3').resolve()
    dst=(destination/'FN/data/FN.sqlite3').resolve()
    if not src.is_file():
        raise ValueError('Source FN save database is missing; no data transferred')
    if dst.is_file() and schema(src)!=schema(dst):
        raise ValueError('FN database schemas differ. Automatic save transfer refused; backups remain available.')
    backup=backup_root/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup.mkdir(parents=True)
    snapshot(src,backup/'source-FN.sqlite3')
    if dst.is_file(): snapshot(dst,backup/'destination-FN.sqlite3')
    # Write and check an independent file before atomically installing it.
    dst.parent.mkdir(parents=True,exist_ok=True)
    tmp=dst.with_suffix('.switch.tmp')
    if tmp.exists(): raise ValueError('Prior switch temporary file exists; inspect it before retrying')
    snapshot(src,tmp)
    # FN uses WAL. Checkpoint and close the old destination before replacement,
    # otherwise an old -wal file could be replayed into the newly installed DB.
    if dst.is_file():
        with closing(sqlite3.connect(dst)) as old:
            checkpoint=old.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()
            if checkpoint[0]: raise ValueError('Destination FN is still in use; transfer refused')
            if old.execute('PRAGMA journal_mode=DELETE').fetchone()[0]!='delete':
                raise ValueError('Could not close destination WAL safely')
    tmp.replace(dst)
    # Only these identity/connection files follow the player; gameplay assets stay untouched.
    for relative in ['player-profile.json','host-settings.json','public-servers.json']:
        s=source/relative;d=destination/relative
        if not s.exists(): continue
        if d.exists(): shutil.copy2(d,backup/('destination-'+relative))
        shutil.copy2(s,d)
    # The claimed tunnel agent stays private and must only run in one version at a time.
    for name in ['playit-portable.exe','playit-agent.key']:
        s=source/'.host-private/playit'/name;d=destination/'.host-private/playit'/name
        if s.is_file():
            d.parent.mkdir(parents=True,exist_ok=True)
            if not d.exists(): shutil.copy2(s,d)
    (backup/'transfer.json').write_text(json.dumps({'source':str(source),'destination':str(destination)},indent=2))
    print(f'FN save transfer verified. Both prior databases are preserved in {backup}')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path);p.add_argument('destination',type=Path);p.add_argument('backups',type=Path)
    a=p.parse_args();transfer(a.source.resolve(),a.destination.resolve(),a.backups.resolve())
