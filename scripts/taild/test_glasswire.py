from contextlib import closing
import contextlib
import hashlib
import ipaddress
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

try:
    import glasswire
except ModuleNotFoundError:
    glasswire = None


def varint(value):
    encoded = bytearray()
    while value > 127:
        encoded.append((value & 127) | 128)
        value >>= 7
    encoded.append(value)
    return bytes(encoded)


def integer(field, value):
    return varint(field << 3) + varint(value)


def string(field, value):
    blob = value.encode()
    return varint(field << 3 | 2) + varint(len(blob)) + blob


class GlassWireTest(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(glasswire, 'Read-only GlassWire reader is not implemented')
        self.tmp = tempfile.TemporaryDirectory(prefix='taild-reader-test-',
                                              dir='D:/Temp' if Path('D:/Temp').is_dir() else None)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.main = self.root / 'glasswire.db'
        self.stats = self.root / 'glasswire_stats_1sec_1791331200.db'
        self.address = integer(1, 1) + integer(2, int.from_bytes(ipaddress.ip_address('198.51.100.12').packed, 'little'))
        # Binary field 1 deliberately differs from SQL id. Unknown fields retained/ignored safely.
        self.app = integer(1, 9) + string(4, 'Synthetic app') + string(6, r'C:\Synthetic\example.exe')
        with closing(sqlite3.connect(self.main)) as db:
            db.execute('CREATE TABLE applications(id INTEGER PRIMARY KEY,data BLOB)')
            db.execute('INSERT INTO applications VALUES(?,?)', (42, self.app))
            db.commit()
        self.writer = sqlite3.connect(self.stats)
        self.addCleanup(self.writer.close)
        self.writer.execute('PRAGMA journal_mode=WAL')
        self.writer.execute('CREATE TABLE traffic_stats(timestamp INTEGER,app_id INTEGER,remote_host BLOB,remote_port INTEGER,remote_host_region BLOB,protocol INTEGER,flags INTEGER,inbound_bytes INTEGER,outbound_bytes INTEGER,threat_level INTEGER)')
        self.add_row(1791391001)

    def add_row(self, timestamp, address=None, incoming=100, outgoing=20):
        self.writer.execute('INSERT INTO traffic_stats VALUES(?,?,?,?,?,?,?,?,?,?)',
                            (timestamp, 42, self.address if address is None else address, 443, b'', 97, 3, incoming, outgoing, 0))
        self.writer.commit()

    def read(self, **options):
        return glasswire.read_traffic(self.stats, self.main,
                                      '2026-10-07T16:36:40Z', '2026-10-07T16:36:43Z', **options)

    def test_real_sqlite_wal_row_and_primary_application_identity(self):
        before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in (self.main, self.stats, Path(str(self.stats)+'-wal'))}
        result = self.read()
        row = result['rows'][0]
        self.assertEqual(row['application_id'], 42)
        self.assertEqual(row['application_path'], r'C:\Synthetic\example.exe')
        self.assertEqual(row['destination_ip'], '198.51.100.12')
        self.assertEqual(row['destination_port'], 443)
        self.assertEqual((row['inbound_bytes'], row['outbound_bytes']), (100, 20))
        self.assertEqual(row['protocol_raw'], 97)
        self.assertEqual(row['provenance']['table'], 'traffic_stats')
        self.assertEqual(row['provenance']['rowid'], 1)
        self.assertEqual(row['provenance']['application_blob_sha256'], hashlib.sha256(self.app).hexdigest())
        self.assertEqual(result['byte_attribution'], 'application-destination-time-bucket')
        self.assertFalse(result['truncated'])
        self.assertEqual(before, {p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in before})

    def test_half_open_window_and_explicit_truncation(self):
        self.add_row(1791391002)
        self.add_row(1791391003)
        result = self.read(limit=1)
        self.assertEqual(len(result['rows']), 1)
        self.assertTrue(result['truncated'])
        self.assertEqual(len(self.read()['rows']), 2)

    def test_unsupported_family_remains_explicit_in_output(self):
        self.add_row(1791391002, address=integer(1, 2) + string(3, 'synthetic-ipv6'))
        result = self.read()
        self.assertIsNone(result['rows'][1]['destination_ip'])
        self.assertEqual(result['rows'][1]['destination_status'], 'unsupported-address-family')
        self.assertEqual(result['unsupported_address_rows'], 1)
        self.assertEqual(result['rows'][1]['inbound_bytes'], 100)

    def test_malformed_binary_rejected_without_partial_success(self):
        self.add_row(1791391002, address=b'\x08\x80')
        with self.assertRaises(glasswire.GlassWireError):
            self.read()

    def test_duplicate_known_address_field_rejected(self):
        self.add_row(1791391002, address=self.address + integer(2, 1))
        with self.assertRaises(glasswire.GlassWireError):
            self.read()

    def test_negative_network_counter_rejected(self):
        self.add_row(1791391002, incoming=-1)
        with self.assertRaises(glasswire.GlassWireError):
            self.read()

    def test_observed_nullable_threat_code_is_preserved_not_invented(self):
        self.writer.execute('UPDATE traffic_stats SET threat_level=NULL')
        self.writer.commit()
        self.assertIsNone(self.read()['rows'][0]['threat_level_raw'])

    def test_missing_source_is_not_created(self):
        path = self.root / 'missing.db'
        with self.assertRaises(glasswire.GlassWireError):
            glasswire.read_traffic(path, self.main, '2026-10-07T16:36:40Z','2026-10-07T16:36:43Z')
        self.assertFalse(path.exists())

    def test_different_scale_is_not_silently_combined(self):
        with self.assertRaises(glasswire.GlassWireError):
            glasswire.read_traffic(self.root/'glasswire_stats_30sec_1791331200.db', self.main,
                                   '2026-10-07T16:36:40Z','2026-10-07T16:36:43Z')

    def test_invalid_window_and_limit(self):
        for start,end,limit in [('2026-10-07','2026-10-08',1),
                                ('2026-10-07T16:36:43Z','2026-10-07T16:36:40Z',1),
                                ('2026-10-07T16:36:40Z','2026-10-07T16:36:43Z',0)]:
            with self.subTest(start=start,limit=limit), self.assertRaises(glasswire.GlassWireError):
                glasswire.read_traffic(self.stats,self.main,start,end,limit=limit)

    def test_unknown_schema_is_rejected(self):
        self.writer.execute('ALTER TABLE traffic_stats RENAME COLUMN inbound_bytes TO other_bytes')
        self.writer.commit()
        with self.assertRaises(glasswire.GlassWireError):
            self.read()

    def test_missing_application_identity_is_not_fabricated(self):
        with closing(sqlite3.connect(self.main)) as db:
            db.execute('DELETE FROM applications')
            db.commit()
        row = self.read()['rows'][0]
        self.assertIsNone(row['application_path'])
        self.assertEqual(row['application_status'], 'missing-application-record')

    def test_connection_cannot_write_even_after_query_only_is_disabled(self):
        with closing(glasswire._connect(self.stats)) as connection:
            connection.execute('PRAGMA query_only=OFF')
            with self.assertRaises(sqlite3.OperationalError):
                connection.execute('DELETE FROM traffic_stats')
        self.assertEqual(self.writer.execute('SELECT count(*) FROM traffic_stats').fetchone()[0],1)

    def test_reader_cli_exports_private_records_but_prints_only_summary(self):
        output=self.root/'traffic.json'
        args=['--stats-db',str(self.stats),'--main-db',str(self.main),
              '--start','2026-10-07T16:36:40Z','--end','2026-10-07T16:36:43Z','--output',str(output)]
        stdout=io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(glasswire.main(args),0)
        self.assertEqual(json.loads(stdout.getvalue())['row_count'],1)
        self.assertNotIn('198.51.100.12',stdout.getvalue())
        self.assertNotIn('Synthetic',stdout.getvalue())
        original=output.read_bytes()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(glasswire.main(args),1)
        self.assertEqual(output.read_bytes(),original)


if __name__ == '__main__':
    unittest.main()
