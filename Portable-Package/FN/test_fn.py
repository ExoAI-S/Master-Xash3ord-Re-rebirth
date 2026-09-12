import base64
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
import http.client
import json
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest

from fn_server import API, FNServer, Store, crc32_file, make_manifest


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


if __name__ == '__main__':
    unittest.main(verbosity=2)
