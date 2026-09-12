"""Private FN v2 character service for Master Sword: Rebirth. Python stdlib only."""
from __future__ import annotations

import argparse
import base64
import binascii
from contextlib import closing, contextmanager
from datetime import datetime, timezone
import ipaddress
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import re
import socket
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import uuid
import zlib

ROOT = Path(__file__).resolve().parent
MAX_BLOB = 50 * 1024
MAX_BODY = 72 * 1024
API = '/api/v2/internal'
LOG = logging.getLogger('FN')


class RequestError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message
        super().__init__(message)


def now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


def identity(steamid, slot):
    if not isinstance(steamid, str) or not re.fullmatch(r'[1-9][0-9]{0,19}', steamid):
        raise RequestError(400, 'steamid must be a decimal SteamID64 string')
    if int(steamid) > 2**64 - 1:
        raise RequestError(400, 'SteamID64 is out of range')
    if type(slot) is not int or not 0 <= slot < 3:
        raise RequestError(400, 'slot must be 0, 1 or 2')
    return steamid, slot


def decode_character(payload):
    if not isinstance(payload, dict):
        raise RequestError(400, 'Expected a JSON object')
    steamid, slot = identity(payload.get('steamid'), payload.get('slot'))
    size, encoded = payload.get('size'), payload.get('data')
    if type(size) is not int or not 0 < size <= MAX_BLOB:
        raise RequestError(400, 'Character size must be 1..51200 bytes')
    if not isinstance(encoded, str):
        raise RequestError(400, 'data must be base64 text')
    try:
        blob = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        raise RequestError(400, 'Invalid base64 data') from None
    if len(blob) != size:
        raise RequestError(400, 'Declared size does not match decoded data')
    return steamid, slot, blob


class Store:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS users (
                    steamid TEXT PRIMARY KEY, flags INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS characters (
                    id TEXT PRIMARY KEY, steamid TEXT NOT NULL, slot INTEGER NOT NULL,
                    blob BLOB NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL,
                    deleted INTEGER NOT NULL DEFAULT 0);
                CREATE UNIQUE INDEX IF NOT EXISTS active_slot
                    ON characters(steamid,slot) WHERE deleted=0;
                CREATE TABLE IF NOT EXISTS revisions (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, character_id TEXT NOT NULL,
                    blob BLOB NOT NULL, saved TEXT NOT NULL, reason TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS revision_character
                    ON revisions(character_id,seq);
                PRAGMA user_version=1;
            ''')

    @contextmanager
    def connect(self, write=False):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA synchronous=FULL')
        try:
            if write:
                db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def flags(db, steamid):
        row = db.execute('SELECT flags FROM users WHERE steamid=?', (steamid,)).fetchone()
        return row['flags'] if row else 0

    @staticmethod
    def revision(db, row, reason):
        db.execute('INSERT INTO revisions(character_id,blob,saved,reason) VALUES(?,?,?,?)',
                   (row['id'], row['blob'], now(), reason))
        db.execute('''DELETE FROM revisions WHERE character_id=? AND seq NOT IN
                   (SELECT seq FROM revisions WHERE character_id=? ORDER BY seq DESC LIMIT 100)''',
                   (row['id'], row['id']))

    def get(self, steamid, slot):
        identity(steamid, slot)
        with self.connect() as db:
            row = db.execute('SELECT * FROM characters WHERE steamid=? AND slot=? AND deleted=0',
                             (steamid, slot)).fetchone()
            if not row:
                return None
            return dict(id=row['id'], steamid=steamid, slot=slot, size=len(row['blob']),
                        data=base64.b64encode(row['blob']).decode('ascii'),
                        flags=self.flags(db, steamid))

    def create(self, payload):
        steamid, slot, blob = decode_character(payload)
        with self.connect(write=True) as db:
            flags = self.flags(db, steamid)
            if flags & 1:
                raise RequestError(403, 'Account is banned from this private FN')
            old = db.execute('SELECT * FROM characters WHERE steamid=? AND slot=? AND deleted=0',
                             (steamid, slot)).fetchone()
            if old:
                if old['blob'] == blob:  # A retry after a lost create response.
                    return dict(id=old['id'], flags=flags)
                raise RequestError(409, 'Character slot is already occupied')
            ident, stamp = str(uuid.uuid4()), now()
            db.execute('INSERT OR IGNORE INTO users(steamid) VALUES(?)', (steamid,))
            db.execute('INSERT INTO characters VALUES(?,?,?,?,?,?,0)',
                       (ident, steamid, slot, blob, stamp, stamp))
            return dict(id=ident, flags=flags)

    def update(self, ident, payload):
        steamid, slot, blob = decode_character(payload)
        with self.connect(write=True) as db:
            row = db.execute('SELECT * FROM characters WHERE id=? AND deleted=0', (ident,)).fetchone()
            if not row:
                raise RequestError(404, 'Character not found')
            if (row['steamid'], row['slot']) != (steamid, slot):
                raise RequestError(409, 'Character owner/slot does not match')
            if self.flags(db, steamid) & 1:
                raise RequestError(403, 'Account is banned from this private FN')
            if row['blob'] != blob:
                self.revision(db, row, 'save')
                db.execute('UPDATE characters SET blob=?,updated=? WHERE id=?', (blob, now(), ident))
        return ident

    def delete(self, ident):
        with self.connect(write=True) as db:
            row = db.execute('SELECT * FROM characters WHERE id=?', (ident,)).fetchone()
            if not row:
                raise RequestError(404, 'Character not found')
            if not row['deleted']:
                self.revision(db, row, 'delete')
                db.execute('UPDATE characters SET deleted=1,updated=? WHERE id=?', (now(), ident))
        return ident

    def backup(self, folder):
        folder = Path(folder).resolve()
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / ('FN-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.sqlite3')
        temporary = target.with_suffix('.sqlite3.tmp')
        with self.connect() as source, closing(sqlite3.connect(temporary)) as dest:
            source.backup(dest)
        temporary.replace(target)
        return target

    def restore(self, ident, revision=None):
        with self.connect(write=True) as db:
            row = db.execute('SELECT * FROM characters WHERE id=?', (ident,)).fetchone()
            if not row:
                raise RequestError(404, 'Character not found')
            occupied = db.execute('''SELECT id FROM characters WHERE steamid=? AND slot=?
                                 AND deleted=0 AND id<>?''', (row['steamid'], row['slot'], ident)).fetchone()
            if occupied:
                raise RequestError(409, 'The slot is occupied; restore will not overwrite it')
            blob = row['blob']
            if revision is not None:
                saved = db.execute('SELECT blob FROM revisions WHERE seq=? AND character_id=?',
                                   (revision, ident)).fetchone()
                if not saved:
                    raise RequestError(404, 'Revision not found for this character')
                blob = saved['blob']
            self.revision(db, row, 'before-restore')
            db.execute('UPDATE characters SET blob=?,deleted=0,updated=? WHERE id=?', (blob, now(), ident))


def crc32_file(path):
    crc = 0
    with Path(path).open('rb') as src:
        for chunk in iter(lambda: src.read(1024 * 1024), b''):
            crc = zlib.crc32(chunk, crc)
    return crc & 0xffffffff


def make_manifest(game_dir, target):
    game_dir = Path(game_dir).resolve()
    maps = {p.stem: crc32_file(p) for p in sorted((game_dir / 'maps').glob('*.bsp'))}
    if not maps or 'edana' not in maps:
        raise ValueError('Game directory must contain maps/edana.bsp')
    manifest = dict(created=now(), scripts_crc32=crc32_file(game_dir / 'scripts.pak'), maps=maps)
    target = Path(target)
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    temporary.replace(target)
    return manifest


class FNServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, address, store, manifest, allowed_ips=('127.0.0.1',)):
        self.store, self.manifest = store, manifest
        self.allowed_ips = {ipaddress.ip_address(ip) for ip in allowed_ips}
        self.slots = threading.BoundedSemaphore(32)
        super().__init__(address, Handler)

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()


class Handler(BaseHTTPRequestHandler):
    server_version = 'FN-Private/1.0'
    sys_version = ''
    protocol_version = 'HTTP/1.1'

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, fmt, *args):
        LOG.info('%s %s', self.client_address[0], (fmt % args).replace('\r', '').replace('\n', ''))

    def reply(self, status, data=None, error=None):
        payload = dict(status=status < 400, code=status)
        if error:
            payload['error'] = error
        else:
            payload['data'] = data
        body = b'' if status == 204 else (json.dumps(payload, separators=(',', ':')) + '\n').encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        # One request per connection also bounds slow/idle clients and unread bad bodies.
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def read_body(self):
        if self.headers.get('Transfer-Encoding'):
            raise RequestError(400, 'Chunked requests are not supported')
        values = self.headers.get_all('Content-Length', [])
        if len(values) != 1 or not re.fullmatch(r'[0-9]+', values[0]):
            raise RequestError(411, 'One valid Content-Length is required')
        length = int(values[0])
        if length > MAX_BODY:
            raise RequestError(413, 'Request is too large')
        if self.headers.get_content_type() != 'application/json':
            raise RequestError(415, 'Expected application/json')
        raw = self.rfile.read(length)
        if len(raw) != length:
            raise RequestError(400, 'Incomplete body')
        try:
            return json.loads(raw)
        except (ValueError, UnicodeError):
            raise RequestError(400, 'Malformed JSON') from None

    def dispatch(self):
        try:
            if ipaddress.ip_address(self.client_address[0]) not in self.server.allowed_ips:
                raise RequestError(401, 'Game server IP is not allowed')
            # The unmodified game sends no browser headers. Reject browser-origin requests.
            if self.headers.get('Origin') or self.headers.get('Sec-Fetch-Site'):
                raise RequestError(403, 'Browser requests are not accepted by the FN game API')
            host = self.headers.get('Host', '').split(':', 1)[0].lower()
            valid_hosts = {str(ip) for ip in self.server.allowed_ips} | {'localhost', self.server.server_address[0]}
            if host not in valid_hosts:
                raise RequestError(403, 'Unrecognized Host header')
            path = self.path
            store = self.server.store
            if self.command == 'GET' and path == '/health':
                with store.connect() as db:
                    db.execute('SELECT 1').fetchone()
                self.reply(200, dict(service='FN', private=True, api=2, maps=len(self.server.manifest['maps'])))
                return
            if self.command == 'GET' and path == API + '/ping':
                self.reply(200, True)
                return
            match = re.fullmatch(API + r'/map/([A-Za-z0-9_-]+)/([0-9]{1,10})', path)
            if self.command == 'GET' and match:
                name, crc = match.groups()
                self.reply(200, self.server.manifest['maps'].get(name) == int(crc))
                return
            match = re.fullmatch(API + r'/sc/([0-9]{1,10})', path)
            if self.command == 'GET' and match:
                self.reply(200, self.server.manifest['scripts_crc32'] == int(match[1]))
                return
            match = re.fullmatch(API + r'/character/([0-9]{1,20})/([0-9])', path)
            if self.command == 'GET' and match:
                data = store.get(match[1], int(match[2]))
                self.reply(200 if data else 204, data)
                return
            if self.command == 'POST' and path in (API + '/character', API + '/character/'):
                self.reply(201, store.create(self.read_body()))
                return
            match = re.fullmatch(API + r'/character/([0-9a-fA-F-]{36})', path)
            if match and self.command in ('PUT', 'DELETE'):
                try:
                    ident = str(uuid.UUID(match[1]))
                except ValueError:
                    raise RequestError(400, 'Invalid character UUID') from None
                data = store.update(ident, self.read_body()) if self.command == 'PUT' else store.delete(ident)
                self.reply(200, data)
                return
            raise RequestError(404, 'Unknown FN endpoint')
        except RequestError as exc:
            self.reply(exc.status, error=exc.message)
        except (socket.timeout, TimeoutError):
            self.close_connection = True
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True
        except Exception:
            LOG.exception('FN request failed')
            self.reply(500, error='FN storage/service error; check the local log')

    do_GET = do_POST = do_PUT = do_DELETE = dispatch


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT / 'config.json')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('serve')
    manifest = sub.add_parser('manifest', help='Approve installed maps and scripts by CRC32')
    manifest.add_argument('--game', type=Path, default=ROOT.parent / 'game/msr')
    sub.add_parser('backup')
    sub.add_parser('list')
    history = sub.add_parser('history')
    history.add_argument('id')
    restore = sub.add_parser('restore')
    restore.add_argument('id')
    restore.add_argument('--revision', type=int)
    flags = sub.add_parser('flags')
    flags.add_argument('steamid')
    flags.add_argument('value', type=int, choices=range(8))
    importing = sub.add_parser('import', help='Copy one local .char into an empty FN slot')
    importing.add_argument('file', type=Path)
    importing.add_argument('--steamid', required=True)
    importing.add_argument('--slot', type=int, choices=range(3), required=True)
    exporting = sub.add_parser('export', help='Export one character as a raw .char file')
    exporting.add_argument('id')
    exporting.add_argument('file', type=Path)
    args = parser.parse_args(argv)
    cfg = json.loads(args.config.read_text(encoding='utf-8-sig'))
    directory = args.config.resolve().parent
    manifest_path = directory / cfg['manifest']
    if args.command == 'manifest':
        data = make_manifest(args.game, manifest_path)
        print(f"Approved {len(data['maps'])} maps; scripts CRC32={data['scripts_crc32']}")
        return
    store = Store(directory / cfg['database'])
    backups = directory / cfg['backups']
    if args.command == 'backup':
        print(store.backup(backups))
    elif args.command in ('list', 'history'):
        with store.connect() as db:
            if args.command == 'list':
                rows = db.execute('SELECT id,steamid,slot,length(blob) AS bytes,updated,deleted FROM characters ORDER BY steamid,slot')
            else:
                rows = db.execute('SELECT seq,saved,reason,length(blob) AS bytes FROM revisions WHERE character_id=? ORDER BY seq DESC', (args.id,))
            print(json.dumps([dict(row) for row in rows], indent=2))
    elif args.command == 'flags':
        identity(args.steamid, 0)
        with store.connect(write=True) as db:
            db.execute('INSERT INTO users VALUES(?,?) ON CONFLICT(steamid) DO UPDATE SET flags=excluded.flags', (args.steamid, args.value))
        print('FN account flags updated')
    elif args.command == 'restore':
        print('Pre-restore backup:', store.backup(backups))
        store.restore(args.id, args.revision)
        print('Character restored. Reconnect to the game to load it.')
    elif args.command == 'import':
        blob = args.file.read_bytes()
        # Current saves start with CHARDATA_HEADER1 and a little-endian version.
        if len(blob) < 5 or blob[0] != 0 or int.from_bytes(blob[1:5], 'little') not in (11, 12):
            raise ValueError('Not a recognized MSR/MS:C character header')
        print('Pre-import backup:', store.backup(backups))
        result = store.create(dict(steamid=args.steamid, slot=args.slot, size=len(blob),
                                   data=base64.b64encode(blob).decode('ascii')))
        print(json.dumps(result))
    elif args.command == 'export':
        with store.connect() as db:
            row = db.execute('SELECT blob FROM characters WHERE id=?', (args.id,)).fetchone()
            if not row:
                raise RequestError(404, 'Character not found')
            # Exclusive creation prevents accidentally overwriting an existing save.
            with args.file.open('xb') as target:
                target.write(row['blob'])
        print('Exported:', args.file.resolve())
    elif args.command == 'serve':
        logs = directory / 'logs'
        logs.mkdir(exist_ok=True)
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',
                            handlers=[logging.StreamHandler(), RotatingFileHandler(logs / 'FN.log', maxBytes=2_000_000, backupCount=5)])
        content = json.loads(manifest_path.read_text(encoding='utf-8'))
        if not content.get('maps') or type(content.get('scripts_crc32')) is not int:
            raise ValueError('Invalid content manifest; run FN-Admin.cmd manifest')
        server = FNServer((cfg['bind'], cfg['port']), store, content, cfg['allowed_ips'])
        LOG.info('Startup backup: %s', store.backup(backups))
        # Keep the latest 30 automatic/startup/manual database snapshots.
        for old in sorted(backups.glob('FN-*.sqlite3'))[:-30]:
            old.unlink()
        stop = threading.Event()

        def periodic_backup():
            while not stop.wait(3600):
                try:
                    LOG.info('Hourly backup: %s', store.backup(backups))
                    for old in sorted(backups.glob('FN-*.sqlite3'))[:-30]:
                        old.unlink()
                except Exception:
                    LOG.exception('Hourly backup failed')

        worker = threading.Thread(target=periodic_backup, daemon=True)
        worker.start()
        LOG.info('Private FN listening on %s:%s', *server.server_address)
        try:
            server.serve_forever(poll_interval=0.25)
        except KeyboardInterrupt:
            pass
        finally:
            stop.set()
            server.server_close()


if __name__ == '__main__':
    try:
        main()
    except (RequestError, OSError, ValueError, sqlite3.Error) as exc:
        raise SystemExit(f'FN: {exc}') from exc
