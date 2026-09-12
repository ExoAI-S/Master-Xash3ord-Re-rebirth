from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from transfer_fn_state import transfer

class SaveTransferTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='msr-save-tests-')
        self.root=Path(self.temp.name)
        self.source=self.root/'enhanced';self.destination=self.root/'stable'
        for folder,value in [(self.source,b'latest character'),(self.destination,b'base character')]:
            path=folder/'FN/data/FN.sqlite3';path.parent.mkdir(parents=True)
            with closing(sqlite3.connect(path)) as db:
                db.execute('PRAGMA journal_mode=WAL')
                db.execute('CREATE TABLE characters (data BLOB)')
                db.execute('INSERT INTO characters VALUES (?)',(value,));db.commit()
    def tearDown(self): self.temp.cleanup()
    def value(self,path):
        with closing(sqlite3.connect(path)) as db:
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            return db.execute('SELECT data FROM characters').fetchone()[0]
    def test_round_trip_preserves_both_prior_versions(self):
        transfer(self.source,self.destination,self.root/'backups')
        self.assertEqual(self.value(self.destination/'FN/data/FN.sqlite3'),b'latest character')
        old=next((self.root/'backups').glob('*/destination-FN.sqlite3'))
        self.assertEqual(self.value(old),b'base character')
        transfer(self.destination,self.source,self.root/'backups')
        self.assertEqual(self.value(self.source/'FN/data/FN.sqlite3'),b'latest character')
    def test_schema_mismatch_does_not_overwrite_destination(self):
        with closing(sqlite3.connect(self.source/'FN/data/FN.sqlite3')) as db:
            db.execute('CREATE TABLE future_version (value TEXT)');db.commit()
        with self.assertRaisesRegex(ValueError,'schemas differ'):
            transfer(self.source,self.destination,self.root/'backups')
        self.assertEqual(self.value(self.destination/'FN/data/FN.sqlite3'),b'base character')

if __name__=='__main__': unittest.main()
