"""Isolated lifecycle tests: fake process/network inventory, real temporary state files."""
import contextlib
import importlib.util
import io
import json
import hashlib
from pathlib import Path
import shutil
import sqlite3
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).parent / 'friend-support/Launcher/native_host.py'
SPEC = importlib.util.spec_from_file_location('native_host', SCRIPT)
host_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(host_module)


class FakeWindows:
    def __init__(self):
        self.processes, self.endpoints, self.effects = {}, [], []
        self.locks = []
        self.k = SimpleNamespace(CloseHandle=self.unlock)

    def lock(self, path):
        self.locks.append(str(path))
        return str(path)

    def unlock(self, handle):
        self.locks.remove(handle)

    def game_processes(self):
        return [p for p in self.processes.values() if p['path'].endswith('xash3d.exe')]

    def record(self, pid):
        return self.processes.get(pid)

    def owned(self, record):
        return bool(record and record == self.record(record['id']))

    def udp(self):
        return list(self.endpoints)

    def terminate(self, record):
        if not self.owned(record):
            raise RuntimeError('Unowned termination')
        self.effects.append('terminate-fn')
        del self.processes[record['id']]


class Lifecycle(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='MSR native host test ')
        self.addCleanup(self.temporary.cleanup)
        bundle = Path(self.temporary.name)
        self.root = bundle / 'Portable-Package'
        (self.root / 'FN').mkdir(parents=True)
        (self.root / 'game/msr/maps').mkdir(parents=True)
        (self.root / 'game/msr/maps/edana.bsp').write_bytes(b'test')
        host_module.write_json(self.root / 'FN/config.json', dict(bind='127.0.0.1', port=15720, database='data/FN.sqlite3'))
        host_module.write_json(self.root / 'FN/content-manifest.json', dict(scripts_crc32=1234))
        # The module import is real; test query functions are installed below.
        (self.root / 'FN/game_query.py').write_text('# isolated test query fixture\n')
        self.win = FakeWindows()
        self.host = host_module.Host(bundle, 'enhanced', first_port=28945, bind='127.0.0.1', windows=self.win)
        self.host.health = lambda: any(p['path'].endswith('python.exe') for p in self.win.processes.values())
        self.host.run_python = lambda script, *args: self.win.effects.append((script, args))
        self.host.spawn = self.spawn
        self.host.query.info = lambda port, timeout=0.5: dict(folder='msr', map='edana', players=0, maxplayers=10)
        self.host.query.rcon = self.rcon
        self.output = io.StringIO()
        self.redirect = contextlib.redirect_stdout(self.output)
        self.redirect.__enter__()
        self.addCleanup(self.redirect.__exit__, None, None, None)

    def spawn(self, args, label, cwd):
        pid = 100 + len(self.win.processes)
        record = dict(id=pid, path=str(args[0]), startTicks=str(639248000000000000 + pid))
        self.win.processes[pid] = record
        if '-port' in args:
            port = int(args[args.index('-port') + 1])
            self.win.endpoints.append((port, pid))
        return dict(record)

    def rcon(self, port, password, command):
        if command == 'quit':
            pid = next(pid for endpoint, pid in self.win.endpoints if endpoint == port)
            del self.win.processes[pid]
            self.win.endpoints = [(p, i) for p, i in self.win.endpoints if i != pid]
            self.win.effects.append('quit-realm')
            return ''
        return 'map     : edana\n'

    def start(self):
        with patch.object(host_module.urllib.request, 'urlopen', return_value=io.BytesIO(b'{"data":true}')):
            self.host.start()

    def test_full_lifecycle_saves_state_and_backs_up_before_fn_exit(self):
        self.start()
        state = host_module.read_json(self.host.state_path)
        self.assertEqual([r['port'] for r in state['games']], [28945, 28955])
        self.assertEqual(len(self.win.processes), 3)
        self.start()  # Existing owned host is not duplicated.
        self.assertEqual(len(self.win.processes), 3)
        self.host.stop()
        self.assertFalse(self.win.processes)
        self.assertFalse(self.host.state_path.exists())
        effects = self.win.effects
        self.assertLess(effects.index(('fn_server.py', ('backup',))), effects.index('terminate-fn'))
        self.assertEqual(effects.count('quit-realm'), 2)
        listen = (self.root / 'game/msr/private_fn_listen.cfg').read_text()
        self.assertIn('ms_central_enabled 0', listen)
        self.assertNotIn('ms_central_enabled 1', listen)
        for server in host_module.read_json(self.host.settings_path)['servers']:
            self.assertNotIn(server['rcon_password'], self.output.getvalue())

    def test_stop_retains_fn_and_state_for_changed_ownership(self):
        self.start()
        self.host.state['games'][0]['process']['startTicks'] = '1'
        self.host.save_state()
        with self.assertRaisesRegex(RuntimeError, 'Realms are still running'):
            self.host.stop()
        self.assertTrue(self.host.state_path.exists())
        self.assertTrue(self.host.health())
        self.assertNotIn('terminate-fn', self.win.effects)

    def test_start_refuses_live_realm_after_state_was_lost(self):
        self.start()
        self.host.state = {}
        with self.assertRaisesRegex(RuntimeError, 'ownership could not be verified'):
            self.host.start()
        self.assertEqual(len(self.win.processes), 3)

    def test_occupied_udp_port_is_not_taken_from_other_install(self):
        self.host.settings(create=True)
        self.win.processes[777] = dict(id=777, path='C:\\Another Game\\xash3d.exe', startTicks='1')
        self.win.endpoints = [(28945, 777)]
        with self.assertRaisesRegex(RuntimeError, 'port is occupied'):
            self.host.start()
        self.assertEqual(list(self.win.processes), [777])

    def test_dm_commands_are_allowlisted_and_require_owned_realm(self):
        self.start()
        for command in ['status', 'ms_dm_grant 0', 'ms_dm_grant 31', 'ms_dm_revoke', 'ms_event orcs']:
            self.host.rcon('realm-one', command)
        for command in ['quit', 'ms_dm_grant 32', 'status;quit', 'status\nquit', 'exec server.cfg']:
            with self.assertRaises(ValueError):
                self.host.rcon('realm-one', command)
        self.host.state['games'][0]['process']['startTicks'] = '1'
        with self.assertRaisesRegex(RuntimeError, 'Start this local realm'):
            self.host.rcon('realm-one', 'ms_event orcs')

    def test_invalid_settings_do_not_write_engine_command_file(self):
        self.host.settings(create=True)
        settings = host_module.read_json(self.host.settings_path)
        settings['servers'][0]['hostname'] = 'test";quit'
        host_module.write_json(self.host.settings_path, settings)
        with self.assertRaises(ValueError):
            self.host.start()
        self.assertFalse(list((self.root / 'game/msr').glob('server_public_*.cfg')))

    def test_stop_never_overwrites_a_manual_listen_configuration(self):
        self.start()
        listen = self.root / 'game/msr/private_fn_listen.cfg'
        manual = '// Hand-maintained local config\nms_central_enabled 0\n'
        listen.write_text(manual)
        self.host.stop()
        self.assertEqual(listen.read_text(), manual)


class VersionSwitch(unittest.TestCase):
    spawn = Lifecycle.spawn
    rcon = Lifecycle.rcon

    def setUp(self):
        Lifecycle.setUp(self)
        stable = self.root.parent / 'Stable-Base'
        shutil.copytree(self.root, stable)
        self.packaging = self.root.parent / 'Packaging-Work'
        self.packaging.mkdir()
        manifest = {'files': {}}
        for relative in ('game/xash3d.exe', 'game/msr/cl_dlls/client.dll', 'game/msr/dlls/ms.dll', 'game/msr/scripts.pak'):
            path = stable / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(('original ' + relative).encode())
            manifest['files'][relative] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        host_module.write_json(self.packaging / 'stable-base-manifest.json', manifest)
        shutil.copy2(Path(__file__).parent / 'transfer_fn_state.py', self.packaging / 'transfer_fn_state.py')
        self.manager = host_module.Versions(self.host)
        for host in self.manager.hosts.values():
            host.health = lambda: False
            host.run_python = lambda script, *args, host=host: self.initialize_db(host)
        self.host.start = lambda: self.win.effects.append('start-selected')
        self.host.launch_client = lambda: self.win.effects.append('launch-client')
        self.transfer_spec = importlib.util.spec_from_file_location('transfer_fn_state_test', self.packaging / 'transfer_fn_state.py')
        self.transfer_module = importlib.util.module_from_spec(self.transfer_spec)
        self.transfer_spec.loader.exec_module(self.transfer_module)

    def initialize_db(self, host):
        database = host.root / 'FN/data/FN.sqlite3'
        database.parent.mkdir(parents=True, exist_ok=True)
        with contextlib.closing(sqlite3.connect(database)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS characters (name TEXT)')

    def set_character(self, host, name):
        self.initialize_db(host)
        with contextlib.closing(sqlite3.connect(host.root / 'FN/data/FN.sqlite3')) as db, db:
            db.execute('INSERT INTO characters VALUES (?)', (name,))

    def read_characters(self, host):
        with contextlib.closing(sqlite3.connect(host.root / 'FN/data/FN.sqlite3')) as db:
            return db.execute('SELECT name FROM characters ORDER BY name').fetchall()

    def subprocess_transfer(self, args, **kwargs):
        self.assertIn(str(self.root.parent / '.player-profile.lock'), self.win.locks)
        self.transfer_module.transfer(Path(args[2]), Path(args[3]), Path(args[4]))

    def select(self, version, play=False):
        self.manager.selected = self.manager.hosts[version]
        self.manager.selected.start = lambda: self.win.effects.append('start-' + version)
        def launch():
            self.assertNotIn(str(self.root.parent / '.player-profile.lock'), self.win.locks)
            self.win.effects.append('launch-' + version)
        self.manager.selected.launch_client = launch
        with patch.object(host_module.subprocess, 'run', side_effect=self.subprocess_transfer):
            self.manager.start(play=play)

    def test_first_switch_initializes_and_preserves_both_database_backups(self):
        self.select('stable', play=True)
        self.assertEqual(self.read_characters(self.manager.hosts['stable']), [])
        backups = list((self.root.parent / 'Version-Backups').glob('*'))
        self.assertEqual(len(backups), 1)
        self.assertTrue((backups[0] / 'source-FN.sqlite3').exists())
        self.assertTrue((backups[0] / 'destination-FN.sqlite3').exists())
        self.assertIn('launch-stable', self.win.effects)

    def test_round_trip_carries_progress_and_keeps_original_assets(self):
        self.set_character(self.host, 'before switch')
        self.select('stable')
        stable = self.manager.hosts['stable']
        self.set_character(stable, 'played stable')
        self.select('enhanced')
        self.assertEqual(self.read_characters(self.host), [('before switch',), ('played stable',)])
        self.manager.verify_stable()
        self.assertEqual(len(list((self.root.parent / 'Version-Backups').glob('*'))), 2)

    def test_missing_source_never_overwrites_existing_destination(self):
        stable = self.manager.hosts['stable']
        self.set_character(stable, 'existing save')
        with self.assertRaisesRegex(RuntimeError, 'selected version has saves'):
            self.select('stable')
        self.assertEqual(self.read_characters(stable), [('existing save',)])
        self.assertNotIn('start-stable', self.win.effects)

    def test_open_client_refuses_switch_before_database_transfer(self):
        self.win.processes[777] = dict(id=777, path=str(self.host.exe), startTicks='1')
        with self.assertRaisesRegex(RuntimeError, 'Close the game'):
            self.select('stable')
        self.assertFalse((self.root.parent / 'Version-Backups').exists())

    def test_modified_stable_binary_refuses_before_stopping_or_transfer(self):
        (self.manager.hosts['stable'].game / 'msr/dlls/ms.dll').write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError, 'differs from its preserved original'):
            self.select('stable')
        self.assertFalse((self.root.parent / 'Version-Backups').exists())

    def test_conflicting_profiles_preserve_both_databases_and_identity_files(self):
        stable = self.manager.hosts['stable']
        self.set_character(self.host, 'enhanced save')
        self.set_character(stable, 'stable save')
        host_module.write_json(self.host.root / 'player-profile.json', {'profile_key': 'a' * 32})
        host_module.write_json(stable.root / 'player-profile.json', {'profile_key': 'b' * 32})
        paths = [host.root / relative for host in (self.host, stable)
                 for relative in ('FN/data/FN.sqlite3', 'player-profile.json')]
        originals = [path.read_bytes() for path in paths]
        with self.assertRaisesRegex(RuntimeError, 'different player identities'):
            self.select('stable')
        self.assertEqual([path.read_bytes() for path in paths], originals)
        self.assertFalse((self.root.parent / 'Version-Backups').exists())
        self.assertEqual(self.win.locks, [])
        self.assertNotIn('start-stable', self.win.effects)

    def test_malformed_or_duplicate_profile_keys_refuse_before_database_creation(self):
        profile = self.host.root / 'player-profile.json'
        for content in ('{}', '[]', '{"profile_key":123}', '{"profile_key":"bad"}',
                        '{"profile_key":"' + 'a' * 32 + '","profile_key":"' + 'a' * 32 + '"}'):
            with self.subTest(content=content):
                profile.write_text(content)
                with self.assertRaisesRegex(RuntimeError, 'invalid player-profile.json'):
                    self.select('stable')
                self.assertFalse((self.root / 'FN/data/FN.sqlite3').exists())
                self.assertEqual(profile.read_text(), content)
                self.assertEqual(self.win.locks, [])


if __name__ == '__main__':
    unittest.main()
