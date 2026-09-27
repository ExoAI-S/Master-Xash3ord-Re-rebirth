import base64
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
import http.client
import json
from pathlib import Path
import socket
import sqlite3
import struct
import subprocess
import sys
import tempfile
import threading
import unittest

from fn_server import API, MAX_BODY, FNServer, Store, crc32_file, make_manifest

# savedata_t from shared/ms/mscharacterheader.h under pack(4), padding written out.
SAVEDATA = struct.Struct('<i32s16s16s32s32s32s32s12sB3xi4h3f3fB3xIh2xff')
# The schema written by the v1 fn_server.py, used to check the in-place migration.
V1_SCHEMA = '''
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
'''


class FNTests(unittest.TestCase):
    def test_private_account_id_roundtrip(self):
        account = '9318648505072287573'
        payload = self.payload(steamid=account)
        status, created = self.request('POST', API + '/character/', payload)
        self.assertEqual(status, 201)
        status, loaded = self.request('GET', API + '/character/' + account + '/0')
        self.assertEqual(status, 200)
        self.assertEqual(loaded['data']['data'], payload['data'])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = Store(self.root / 'FN.sqlite3')
        self.server = FNServer(('127.0.0.1', 0), self.store,
                               {'maps': {'edana': 1234567890}, 'scripts_crc32': 1234})
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_port

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def request(self, method, path, payload=None, headers=None):
        headers = dict(headers or {})
        body = None
        if payload is not None:
            body = json.dumps(payload).encode()
            headers.setdefault('Content-Type', 'application/json; charset=UTF-8')
        client = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        client.request(method, path, body=body, headers=headers)
        response = client.getresponse()
        status, body = response.status, response.read()
        client.close()
        return status, json.loads(body) if body else None

    @staticmethod
    def payload(blob=b'\x00\xff\x01private-character\x00', steamid='76561198000000001', slot=0):
        return dict(steamid=steamid, slot=slot, size=len(blob), data=base64.b64encode(blob).decode())

    def create(self, payload=None):
        status, result = self.request('POST', API + '/character/', payload or self.payload())
        self.assertEqual(status, 201)
        return result['data']['id']

    def test_game_wire_round_trip_restart_delete_and_recover(self):
        route = API + '/character/76561198000000001/0'
        self.assertEqual(self.request('GET', route), (204, None))
        payload = self.payload()
        ident = self.create(payload)
        loaded = self.request('GET', route)[1]['data']
        self.assertEqual(loaded, dict(payload, id=ident, flags=0))
        updated = self.payload(bytes(range(256)) * 100)
        self.assertEqual(self.request('PUT', API + '/character/' + ident, updated)[0], 200)
        reopened = Store(self.store.path)
        self.assertEqual(reopened.get(payload['steamid'], 0)['data'], updated['data'])
        self.assertEqual(self.request('DELETE', API + '/character/' + ident)[0], 200)
        self.assertEqual(self.request('GET', route), (204, None))
        reopened.restore(ident)
        self.assertEqual(reopened.get(payload['steamid'], 0)['data'], updated['data'])
        with reopened.connect() as db:
            seq = db.execute('SELECT MIN(seq) FROM revisions WHERE character_id=?', (ident,)).fetchone()[0]
        reopened.restore(ident, seq)
        self.assertEqual(reopened.get(payload['steamid'], 0)['data'], payload['data'])

    def test_validation_and_health(self):
        for path, expected in [('/ping', True), ('/map/edana/1234567890', True),
                               ('/map/edana/7', False), ('/map/notapproved/1', False),
                               ('/sc/1234', True), ('/sc/1', False)]:
            code, response = self.request('GET', API + path)
            self.assertEqual((code, response['data']), (200, expected))
        self.assertEqual(self.request('GET', '/health')[1]['data']['service'], 'FN')

    def test_reject_malformed_character_without_writing(self):
        changes = [{'size': 0}, {'size': 51201}, {'size': True}, {'size': 5},
                   {'data': '!invalid'}, {'data': 7}, {'steamid': '../../escape'},
                   {'steamid': str(2**64)}, {'steamid': 76561198000000001},
                   {'slot': -1}, {'slot': 3}, {'slot': True}]
        for change in changes:
            with self.subTest(change=change):
                self.assertEqual(self.request('POST', API + '/character/', self.payload() | change)[0], 400)
        self.assertEqual(self.request('POST', API + '/character/', [1, 2])[0], 400)
        self.assertIsNone(self.store.get('76561198000000001', 0))

    def test_owner_check_and_slot_conflict(self):
        ident = self.create()
        route = API + '/character/' + ident
        self.assertEqual(self.request('PUT', route, self.payload(steamid='76561198000000002'))[0], 409)
        self.assertEqual(self.request('PUT', route, self.payload(slot=1))[0], 409)
        self.assertEqual(self.request('POST', API + '/character/', self.payload(b'different'))[0], 409)
        self.assertEqual(self.create(), ident)

    def test_account_flags_and_ban(self):
        ident = self.create()
        with self.store.connect(write=True) as db:
            db.execute('UPDATE users SET flags=7')
        self.assertEqual(self.store.get('76561198000000001', 0)['flags'], 7)
        self.assertEqual(self.request('PUT', API + '/character/' + ident, self.payload())[0], 403)
        self.assertEqual(self.request('POST', API + '/character/', self.payload(slot=1))[0], 403)

    def test_backup_and_occupied_restore(self):
        ident = self.create()
        backup = self.store.backup(self.root / 'backups')
        with closing(sqlite3.connect(backup)) as db:
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            self.assertEqual(db.execute('SELECT COUNT(*) FROM characters').fetchone()[0], 1)
        self.store.delete(ident)
        self.create(self.payload(b'new character'))
        with self.assertRaisesRegex(Exception, 'occupied'):
            self.store.restore(ident)

    def test_concurrent_creates_do_not_duplicate_or_overwrite(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda i: self.request('POST', API + '/character/', self.payload(str(i).encode()))[0], range(8)))
        self.assertEqual(results.count(201), 1)
        self.assertEqual(results.count(409), 7)
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM characters').fetchone()[0], 1)

    def test_reject_browser_untrusted_host_and_remote_ip(self):
        self.assertEqual(self.request('POST', API + '/character/', self.payload(), {'Origin': 'https://example.com'})[0], 403)
        self.assertEqual(self.request('GET', API + '/ping', headers={'Host': 'attacker.example'})[0], 403)
        self.server.allowed_ips.clear()
        self.assertEqual(self.request('GET', API + '/ping', headers={'X-Forwarded-For': '127.0.0.1'})[0], 401)

    def test_request_framing_and_limits(self):
        for headers, expected in [('Content-Length: 999999\r\n', 413),
                                  ('Content-Length: 2\r\nContent-Length: 2\r\n', 411),
                                  ('Transfer-Encoding: chunked\r\n', 400)]:
            with socket.create_connection(('127.0.0.1', self.port), timeout=3) as sock:
                request = f'POST {API}/character/ HTTP/1.1\r\nHost: 127.0.0.1\r\n{headers}Content-Type: application/json\r\n\r\n'
                sock.sendall(request.encode())
                response = sock.recv(4096)
                self.assertIn(f' {expected} '.encode(), response.split(b'\r\n')[0])

    def test_crc_manifest_matches_standard_crc32(self):
        game = self.root / 'game'
        (game / 'maps').mkdir(parents=True)
        (game / 'maps/edana.bsp').write_bytes(b'123456789')
        (game / 'scripts.pak').write_bytes(b'123456789')
        manifest = make_manifest(game, self.root / 'manifest.json')
        self.assertEqual(crc32_file(game / 'scripts.pak'), 0xcbf43926)
        self.assertEqual(manifest['maps']['edana'], 0xcbf43926)

    def test_supplied_character_files_round_trip_without_changes(self):
        saves = list((Path(__file__).resolve().parent.parent / 'game/msr/save').glob('*.char'))
        if not saves:
            self.skipTest('Game archive is not present in this FN-only package')
        for i, file in enumerate(saves):
            blob = file.read_bytes()
            if not 0 < len(blob) <= 51200:
                continue
            steamid = str(76561198000000010 + i)
            payload = self.payload(blob, steamid=steamid)
            self.create(payload)
            response = self.request('GET', API + '/character/' + steamid + '/0')[1]['data']
            self.assertEqual(base64.b64decode(response['data']), blob)

    def test_cli_import_export_and_flags(self):
        config = self.root / 'config.json'
        config.write_text(json.dumps(dict(database=str(self.store.path), backups='backups', manifest='manifest.json')))
        original = self.root / 'source.char'
        original.write_bytes(b'\x00\x0c\x00\x00\x00example local save')
        script = Path(__file__).with_name('fn_server.py')

        def cli(*arguments):
            return subprocess.run([sys.executable, str(script), '--config', str(config), *arguments],
                                  capture_output=True, text=True, timeout=10)

        result = cli('import', str(original), '--steamid', '76561198000000001', '--slot', '0')
        self.assertEqual(result.returncode, 0, result.stderr)
        ident = self.store.get('76561198000000001', 0)['id']
        output = self.root / 'export.char'
        self.assertEqual(cli('export', ident, str(output)).returncode, 0)
        self.assertEqual(original.read_bytes(), output.read_bytes())
        self.assertNotEqual(cli('export', ident, str(output)).returncode, 0)
        self.assertEqual(cli('flags', '76561198000000001', '4').returncode, 0)
        self.assertEqual(self.store.get('76561198000000001', 0)['flags'], 4)

    # --- Character revision masking -------------------------------------------------

    @staticmethod
    def character(origin=(0.0, 0.0, 0.0), angles=(0.0, 0.0, 0.0), hp=15, gender=0):
        header = SAVEDATA.pack(12, b'Tester', b'Human', b'edana', b'', b'', b'', b'', b'', 0, 10,
                               20, 20, hp, 20, *origin, *angles, gender, 0, 0, 0.0, 0.0)
        # CHARDATA_HEADER1, savedata_t, then a CHARDATA_MAPSVISITED1 chunk and filler.
        return b'\x00' + header + b'\x01\x01\x00\x00\x00edana\x00' + b'\x02more chunks'

    def revisions(self, ident):
        with self.store.connect() as db:
            return db.execute('SELECT COUNT(*) FROM revisions WHERE character_id=?', (ident,)).fetchone()[0]

    def test_position_only_saves_do_not_add_revisions(self):
        self.assertEqual(SAVEDATA.size, 268)
        base = self.character()
        ident = self.create(self.payload(base))
        route = API + '/character/' + ident

        def put(blob, expected):
            self.assertEqual(self.request('PUT', route, self.payload(bytes(blob)))[0], 200)
            self.assertEqual(self.store.get('76561198000000001', 0)['data'], self.payload(bytes(blob))['data'])
            self.assertEqual(self.revisions(ident), expected)

        moved = self.character(origin=(100.5, -2048.0, 64.25), angles=(-10.0, 270.0, 3.0))
        self.assertEqual(struct.unpack_from('<3f', moved, 225), (100.5, -2048.0, 64.25))
        self.assertEqual(struct.unpack_from('<3f', moved, 237), (-10.0, 270.0, 3.0))
        changed = [i for i in range(len(base)) if base[i] != moved[i]]
        self.assertTrue(changed and 225 <= min(changed) and max(changed) <= 248)
        put(moved, 0)
        current = bytearray(moved)
        for index in (225, 236, 237, 248):  # First/last bytes of Origin and Angles.
            current[index] ^= 0x40
            put(current, 0)
        # Anything else is a real change: Version, the MP byte before Origin, Gender after
        # Angles, the chunk data and the length.
        for expected, index in enumerate((1, 224, 249, len(current) - 1), 1):
            current[index] ^= 0x40
            put(current, expected)
        put(current + b'!', 5)
        # Without a full CHARDATA_HEADER1 + savedata_t the offsets mean nothing: keep history.
        for slot, blob in ((1, bytearray(b'\x07' * 400)), (2, bytearray(SAVEDATA.size))):
            other = self.create(self.payload(bytes(blob), slot=slot))
            blob[230] ^= 1
            self.assertEqual(self.request('PUT', API + '/character/' + other,
                                          self.payload(bytes(blob), slot=slot))[0], 200)
            self.assertEqual(self.revisions(other), 1)

    # --- World state ----------------------------------------------------------------

    def world(self, method='GET', payload=None, realm='sandbox', map_name='edana'):
        return self.request(method, f'{API}/world/{realm}/{map_name}', payload)

    def fake_clock(self, start):
        clock = [start]
        self.store.clock = lambda: clock[0]
        return clock

    def world_rows(self):
        with self.store.connect() as db:
            return db.execute('SELECT COUNT(*) FROM world_state').fetchone()[0]

    def test_world_round_trip_revisions_and_isolation(self):
        clock = self.fake_clock(1_000_000.0)
        self.assertEqual(self.world(), (200, dict(status=True, code=200, data=dict(now=1_000_000.0, keys={}))))
        batch = {'set': {'boss.thornlands.queen': {'value': '1000000', 'ttl': 1800},
                         'quest.edana:gate-open': {'value': 'yes'},
                         'counter': {'value': 'Grüße €', 'ttl': None}}}
        self.assertEqual(self.world('POST', batch),
                         (200, dict(status=True, code=200, data=dict(applied=3, now=1_000_000.0))))
        clock[0] += 100.5
        self.assertEqual(self.world()[1]['data'], dict(now=1_000_100.5, keys={
            'boss.thornlands.queen': dict(value='1000000', expires_in=1699.5, rev=1),
            'counter': dict(value='Grüße €', expires_in=None, rev=1),
            'quest.edana:gate-open': dict(value='yes', expires_in=None, rev=1)}))
        # Every write bumps rev, even an unchanged value; a null ttl makes a timer permanent.
        rewrite = {'set': {'counter': {'value': 'Grüße €'},
                           'boss.thornlands.queen': {'value': 'x', 'ttl': None}}}
        self.assertEqual(self.world('POST', rewrite)[0], 200)
        keys = self.world()[1]['data']['keys']
        self.assertEqual(keys['counter']['rev'], 2)
        self.assertEqual(keys['boss.thornlands.queen'], dict(value='x', expires_in=None, rev=2))
        self.assertEqual(keys['quest.edana:gate-open']['rev'], 1)
        # Map names are stored lowercased; each (realm, map) is its own world.
        self.assertEqual(self.world(map_name='EDANA')[1]['data']['keys'], keys)
        self.assertEqual(self.world(realm='realm-one')[1]['data']['keys'], {})
        self.assertEqual(self.world(map_name='thornlands')[1]['data']['keys'], {})
        self.assertEqual(self.world('POST', {'set': {'counter': {'value': 'other'}}},
                                    realm='realm-one', map_name='Edana')[0], 200)
        self.assertEqual(self.world()[1]['data']['keys']['counter']['value'], 'Grüße €')
        self.assertEqual(self.world(realm='realm-one')[1]['data']['keys']['counter']['rev'], 1)
        with self.store.connect() as db:
            self.assertEqual({row[0] for row in db.execute('SELECT map FROM world_state')}, {'edana'})
        self.assertEqual(Store(self.store.path).world_get('sandbox', 'edana')['keys'], keys)

    def test_world_ttl_expiry_uses_the_server_clock(self):
        clock = self.fake_clock(5000.0)
        self.world('POST', {'set': {'boss.a': {'value': '1', 'ttl': 60}, 'boss.b': {'value': '2', 'ttl': 0.5},
                                    'keep': {'value': '3'}}})
        clock[0] += 59.75
        keys = self.world()[1]['data']['keys']
        self.assertEqual(sorted(keys), ['boss.a', 'keep'])
        self.assertEqual(keys['boss.a']['expires_in'], 0.25)
        clock[0] += 0.25  # Reaching the deadline counts as expired.
        self.assertEqual(sorted(self.world()[1]['data']['keys']), ['keep'])
        self.assertEqual(self.world_rows(), 3)  # GET only hides expired rows ...
        self.assertEqual(self.world('POST', {'del': ['keep']})[0], 200)
        self.assertEqual(self.world_rows(), 0)  # ... the next write to that world prunes them.
        self.assertEqual(self.world('POST', {'set': {'boss.a': {'value': '9', 'ttl': 10}}})[0], 200)
        self.assertEqual(self.world()[1]['data']['keys'], {'boss.a': dict(value='9', expires_in=10.0, rev=1)})

    def test_world_del(self):
        self.world('POST', {'set': {'a': {'value': '1'}, 'b': {'value': '2', 'ttl': 100}, 'c': {'value': '3'}}})
        # Duplicates collapse; deleting an absent key is an idempotent no-op.
        code, reply = self.world('POST', {'del': ['a', 'b', 'a', 'missing']})
        self.assertEqual((code, reply['data']['applied']), (200, 3))
        self.assertEqual(list(self.world()[1]['data']['keys']), ['c'])
        self.assertEqual(self.world('POST', {'set': {'a': {'value': 'again'}}})[0], 200)
        self.assertEqual(self.world()[1]['data']['keys']['a'], dict(value='again', expires_in=None, rev=1))
        self.assertEqual(self.world('POST', {})[1]['data']['applied'], 0)

    def test_world_rejects_bad_input_without_writing(self):
        good = {'value': 'v'}
        for route in ('Sandbox/edana', '-x/edana', 'a' * 33 + '/edana', 'sand.box/edana',
                      'sandbox/' + 'm' * 33, 'sandbox/ed.ana', 'sandbox/ed%20ana'):
            with self.subTest(route=route):
                self.assertEqual(self.request('GET', f'{API}/world/{route}')[0], 400)
                self.assertEqual(self.request('POST', f'{API}/world/{route}', {'set': {'k': good}})[0], 400)
        bodies = [[1], 'text', {'set': []},{'del': {}}, {'del': 'k'}, {'other': 1},
                  {'set': {'k': good}, 'extra': 1},
                  {'set': {'Upper': good}}, {'set': {'.lead': good}}, {'set': {'k' * 65: good}},
                  {'set': {'sp ace': good}}, {'set': {'': good}}, {'set': {'sl/ash': good}},
                  {'set': {'k': 'v'}}, {'set': {'k': {}}}, {'set': {'k': {'ttl': 5}}},
                  {'set': {'k': {'value': 'v', 'other': 1}}}, {'set': {'k': {'value': 5}}},
                  {'set': {'k': {'value': None}}}, {'set': {'k': {'value': 'x' * 256}}},
                  {'set': {'k': {'value': 'é' * 128}}},  # 128 characters, 256 UTF-8 bytes.
                  {'set': {'k': {'value': '\ud800'}}},  # Valid JSON escape, not encodable text.
                  {'set': {'k': {'value': 'v', 'ttl': 0}}}, {'set': {'k': {'value': 'v', 'ttl': -1}}},
                  {'set': {'k': {'value': 'v', 'ttl': 30 * 86400 + 1}}},
                  {'set': {'k': {'value': 'v', 'ttl': True}}}, {'set': {'k': {'value': 'v', 'ttl': '60'}}},
                  {'set': {'k': {'value': 'v', 'ttl': float('nan')}}},
                  {'set': {'k': {'value': 'v', 'ttl': float('inf')}}},
                  {'del': [5]}, {'del': ['Bad']}, {'del': [['k']]}, {'del': [None]},
                  # Names the game never loads (script variable prefixes).
                  {'set': {'global.x': good}}, {'set': {'local.x': good}}, {'set': {'game.x': good}},
                  {'set': {'const.x': good}}, {'del': ['game.x']},
                  {'set': {'k': good}, 'del': ['k']},
                  # One bad operation rejects the whole batch.
                  {'set': {'fine': good, 'also.fine': good, 'BAD': good}},
                  {'set': {'fine': good}, 'del': ['ok', 'NOT OK']}]
        for body in bodies:
            with self.subTest(body=body):
                code, reply = self.world('POST', body)
                self.assertEqual((code, reply['status'], 'error' in reply), (400, False, True))
        self.assertEqual(self.world_rows(), 0)
        # The accepted boundaries (a frozen clock keeps the 1 ms timer alive for the read back).
        self.fake_clock(1000.0)
        edge = {'set': {'k' * 64: good, '0': {'value': ''},
                        'a.b:c-d_e': {'value': 'x' * 255, 'ttl': 30 * 86400},
                        'euro': {'value': '€' * 85, 'ttl': 0.001}}}
        self.assertEqual(self.world('POST', edge, realm='r' * 32, map_name='M' * 32)[0], 200)
        self.assertEqual(len(self.world(realm='r' * 32, map_name='m' * 32)[1]['data']['keys']), 4)

    def test_world_limits_are_413_and_batches_are_atomic(self):
        clock = self.fake_clock(1000.0)
        too_many = {'set': {f'k{i}': {'value': 'v'} for i in range(200)}, 'del': [f'd{i}' for i in range(57)]}
        self.assertEqual(self.world('POST', too_many)[0], 413)
        self.assertEqual(self.world('POST', {'del': [f'd{i}' for i in range(256)]})[0], 200)
        huge = {'set': {f'big{i:03}': {'value': 'x' * 255, 'ttl': 30 * 86400} for i in range(256)}}
        self.assertGreater(len(json.dumps(huge)), MAX_BODY)
        self.assertEqual(self.world('POST', huge)[0], 413)
        self.assertEqual(self.world_rows(), 0)
        # Exactly 4096 live keys: 4000 permanent plus 96 that expire later.
        for start in range(0, 4096, 256):
            batch = {f'k{i:04}': {'value': 'v', 'ttl': 60 if i >= 4000 else None} for i in range(start, start + 256)}
            self.assertEqual(self.store.world_write('sandbox', 'edana', {'set': batch})['applied'], 256)
        full = self.world()[1]['data']['keys']
        self.assertEqual(len(full), 4096)
        # One key too many rejects the batch after it was applied inside the transaction,
        # so the update that would have fitted is rolled back too.
        code, reply = self.world('POST', {'set': {'k0000': {'value': 'changed'}, 'extra': {'value': 'v'}}})
        self.assertEqual((code, reply['status']), (413, False))
        self.assertEqual(self.world()[1]['data']['keys'], full)
        # The limit is checked after applying, so deletes in the same batch make room.
        self.assertEqual(self.world('POST', {'set': {'extra': {'value': 'v'}}, 'del': ['k0001']})[0], 200)
        self.assertEqual(self.world('POST', {'set': {'extra': {'value': 'v'}}}, map_name='helena')[0], 200)
        # Expired keys are not live and do not count.
        clock[0] += 61
        self.assertEqual(self.world('POST', {'set': {f'n{i}': {'value': 'v'} for i in range(96)}})[0], 200)
        self.assertEqual(len(self.world()[1]['data']['keys']), 4096)
        self.assertEqual(self.world('POST', {'set': {'one.more': {'value': 'v'}}})[0], 413)

    def test_world_uses_the_same_access_policy_and_unknown_routes_still_404(self):
        route = API + '/world/sandbox/edana'
        self.assertEqual(self.request('GET', route, headers={'Origin': 'https://example.com'})[0], 403)
        self.assertEqual(self.request('POST', route, {'set': {}}, {'Sec-Fetch-Site': 'cross-site'})[0], 403)
        self.assertEqual(self.request('GET', route, headers={'Host': 'attacker.example'})[0], 403)
        for method, path in [('GET', API + '/nope'), ('GET', API + '/world'), ('GET', API + '/world/sandbox'),
                             ('GET', API + '/world/sandbox/'), ('GET', route + '/extra'), ('GET', route + '?x=1'),
                             ('PUT', route), ('DELETE', route), ('GET', '/api/v1/internal/world/sandbox/edana'),
                             ('POST', API + '/ping'), ('GET', API + '/character/1')]:
            with self.subTest(method=method, path=path):
                self.assertEqual(self.request(method, path),
                                 (404, dict(status=False, code=404, error='Unknown FN endpoint')))
        self.server.allowed_ips.clear()
        self.assertEqual(self.request('GET', route)[0], 401)

    def test_v1_database_migrates_in_place(self):
        path = self.root / 'v1.sqlite3'
        ident, blob = '11111111-2222-3333-4444-555555555555', b'\x00\x0c\x00\x00\x00old save'
        with closing(sqlite3.connect(path)) as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript(V1_SCHEMA)
            db.execute("INSERT INTO users VALUES('76561198000000001',2)")
            db.execute("INSERT INTO characters VALUES(?,'76561198000000001',0,?,'c','u',0)", (ident, blob))
            db.execute("INSERT INTO revisions(character_id,blob,saved,reason) VALUES(?,?,'s','save')",
                       (ident, b'older'))
            db.commit()
        store = Store(path)
        with closing(sqlite3.connect(path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 2)
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            self.assertEqual(db.execute('SELECT COUNT(*) FROM revisions').fetchone()[0], 1)
            self.assertIn('WITHOUT ROWID', db.execute(
                "SELECT sql FROM sqlite_master WHERE name='world_state'").fetchone()[0])
            self.assertEqual(db.execute("SELECT tbl_name FROM sqlite_master WHERE name='world_expiry'").fetchone()[0],
                             'world_state')
        loaded = store.get('76561198000000001', 0)
        self.assertEqual((loaded['id'], base64.b64decode(loaded['data']), loaded['flags']), (ident, blob, 2))
        store.world_write('sandbox', 'edana', {'set': {'k': {'value': 'v'}}})
        again = Store(path)  # Re-opening a v2 file changes nothing.
        self.assertEqual(again.world_get('sandbox', 'edana')['keys']['k']['value'], 'v')
        self.assertEqual(again.get('76561198000000001', 0), loaded)
        # A file from a newer fn_server.py is refused rather than relabelled as v2.
        with closing(sqlite3.connect(path)) as db:
            db.execute('PRAGMA user_version=3')
        with self.assertRaisesRegex(ValueError, 'newer'):
            Store(path)

    def test_cli_world_commands(self):
        config = self.root / 'config.json'
        config.write_text(json.dumps(dict(database=str(self.store.path), backups='backups', manifest='manifest.json')))
        script = Path(__file__).with_name('fn_server.py')

        def cli(*arguments):
            return subprocess.run([sys.executable, str(script), '--config', str(config), 'world', *arguments],
                                  capture_output=True, text=True, timeout=10)

        for arguments in (('set', 'sandbox', 'Edana', 'boss.thornlands.queen', '1700000000', '1800'),
                          ('set', 'sandbox', 'edana', 'gate', 'open'), ('set', 'sandbox', 'helena', 'x', '1')):
            result = cli(*arguments)
            self.assertEqual(result.returncode, 0, result.stderr)
        listed = json.loads(cli('list', 'sandbox', 'edana').stdout)
        self.assertEqual([(row['key'], row['value'], row['expires_in'] is None) for row in listed],
                         [('boss.thornlands.queen', '1700000000', False), ('gate', 'open', True)])
        self.assertTrue(0 < listed[0]['expires_in'] <= 1800)
        self.assertEqual(len(json.loads(cli('list', 'sandbox').stdout)), 3)
        for arguments in (('set', 'sandbox', 'edana', 'Bad Key', 'v'), ('set', 'sandbox', 'edana', 'k', 'v', '0'),
                          ('list', 'Bad Realm'), ('del', 'sandbox', 'ed.ana', 'gate')):
            result = cli(*arguments)
            self.assertNotEqual(result.returncode, 0, arguments)
            self.assertIn('FN:', result.stderr)
        self.assertEqual(cli('del', 'sandbox', 'edana', 'gate').returncode, 0)
        result = cli('clear', 'sandbox', 'edana')
        self.assertIn('World keys removed: 1', result.stdout)
        self.assertTrue(list((self.root / 'backups').glob('FN-*.sqlite3')))
        self.assertEqual([(row['map'], row['key']) for row in json.loads(cli('list', 'sandbox').stdout)],
                         [('helena', 'x')])


if __name__ == '__main__':
    unittest.main(verbosity=2)
