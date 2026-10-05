import csv
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from scripts.fix_person_ids import migrate_person_ids
from scripts.migrate_history import KEYS, run
from test_order_workflow import create_legacy_database


class HistoryMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / 'app.db'
        create_legacy_database(self.db)
        self.conn = sqlite3.connect(self.db)
        self.addCleanup(self.conn.close)
        migrate_person_ids(self.conn)
        self.conn.executescript('''
            UPDATE orders SET order_type='Specialty', age='12.0',
                bike_type_first_choice=' c ', notes=' Legacy note ';
            CREATE TABLE users (username TEXT);
            INSERT INTO users VALUES ('test-admin');
            CREATE TABLE bikes_test (bike_tag INTEGER);
            INSERT INTO bikes_test VALUES (123);
        ''')
        self.source = self.root / 'source'
        self.source.mkdir()
        for table in KEYS:
            cursor = self.conn.execute(f'SELECT * FROM {table}')
            columns = [c[0] for c in cursor.description]
            headers = [{'order_status': 'status', 'last_updated_by': 'handled_by'}.get(c, c)
                       if table == 'orders' else c for c in columns]
            with (self.source / f'{table}.csv').open('w', newline='') as handle:
                writer = csv.writer(handle)
                writer.writerow(headers)
                writer.writerows(cursor)

    def edit_source(self, table, callback):
        path = self.source / f'{table}.csv'
        with path.open(newline='') as handle:
            rows = list(csv.DictReader(handle))
        callback(rows)
        with path.open('w', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    def test_preview_does_not_touch_app_database(self):
        before = self.db.read_bytes()
        report = run(self.db, self.source, self.root / 'preview')
        self.assertEqual(self.db.read_bytes(), before)
        self.assertGreater(len(report['normalizations']), 0)
        with closing(sqlite3.connect(self.root / 'preview' / 'preview.db')) as preview:
            self.assertEqual(preview.execute('SELECT order_type, age, bike_type_first_choice, notes FROM orders').fetchone(),
                             ('Speciality', '12', 'C', 'Legacy note'))

    def test_apply_keeps_updates_new_records_and_unrelated_tables(self):
        self.conn.executescript('''
            UPDATE orders SET order_status='Completed', pickup_date='2026-09-28',
                bike_tag=456, last_status='Contacted', last_updated_by='tester',
                last_updated_date='2026-09-28 12:00:00', notes=NULL;
            INSERT INTO orders (contact_id, recipient_id, shop_name, order_type, order_date)
                VALUES (20, 40, 'B', 'Public', '2026-09-29');
        ''')
        report = run(self.db, self.source, self.root / 'apply', apply=True)
        self.assertEqual(self.conn.execute('SELECT order_status, pickup_date, bike_tag, last_status, last_updated_by, notes FROM orders WHERE order_id=1').fetchone(),
                         ('Completed', '2026-09-28', 456, 'Contacted', 'tester', None))
        self.assertEqual(report['app_only_ids']['orders'], [2])
        self.assertEqual(self.conn.execute('SELECT * FROM users').fetchall(), [('test-admin',)])
        self.assertEqual(self.conn.execute('SELECT * FROM bikes_test').fetchall(), [(123,)])
        with closing(sqlite3.connect(self.root / 'apply' / 'before.db')) as backup:
            self.assertEqual(backup.execute('SELECT order_type, order_status FROM orders WHERE order_id=1').fetchone(), ('Specialty', 'Completed'))
        self.assertTrue((self.root / 'apply' / 'report.json').exists())

    def test_rerun_does_not_overwrite_later_app_edit(self):
        run(self.db, self.source, self.root / 'first', apply=True)
        self.conn.execute("UPDATE orders SET notes='Later edit'")
        self.conn.commit()
        report = run(self.db, self.source, self.root / 'second', apply=True)
        self.assertTrue(report['already_applied'])
        self.assertEqual(self.conn.execute('SELECT notes FROM orders').fetchone()[0], 'Later edit')
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM history_migrations').fetchone()[0], 1)

    def test_different_source_cannot_repeat_completed_migration(self):
        run(self.db, self.source, self.root / 'first', apply=True)
        self.edit_source('orders', lambda rows: rows[0].update(notes='Different source'))
        with self.assertRaisesRegex(ValueError, 'different source'):
            run(self.db, self.source, self.root / 'second', apply=True)
        self.assertEqual(self.conn.execute('SELECT notes FROM orders').fetchone()[0], 'Legacy note')

    def test_duplicate_source_id_is_rejected_before_writes(self):
        self.edit_source('orders', lambda rows: rows.append(dict(rows[0])))
        before = self.db.read_bytes()
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            run(self.db, self.source, self.root / 'bad', apply=True)
        self.assertEqual(self.db.read_bytes(), before)

    def test_broken_reference_rolls_back_changes_and_ledger(self):
        self.conn.execute('UPDATE orders SET recipient_id=999')
        self.conn.commit()
        with self.assertRaisesRegex(ValueError, 'missing recipients'):
            run(self.db, self.source, self.root / 'bad', apply=True)
        self.assertEqual(self.conn.execute('SELECT order_type FROM orders').fetchone()[0], 'Specialty')
        self.assertIsNone(self.conn.execute("SELECT name FROM sqlite_master WHERE name='history_migrations'").fetchone())
        self.assertTrue((self.root / 'bad' / 'before.db').exists())

    def test_missing_facts_and_possible_duplicates_are_preserved(self):
        self.conn.executescript('''
            UPDATE orders SET order_date=NULL, shop_name=NULL;
            INSERT INTO orders (contact_id, recipient_id, pedal_partner_id, order_status,
                order_type, age, bike_type_first_choice, notes)
                SELECT contact_id, recipient_id, pedal_partner_id, order_status,
                    order_type, age, bike_type_first_choice, notes FROM orders;
        ''')
        report = run(self.db, self.source, self.root / 'review', apply=True)
        self.assertEqual(report['after']['possible_duplicate_groups'], [[1, 2]])
        self.assertEqual(report['after']['issue_counts']['missing_order_date'], 2)
        self.assertEqual(self.conn.execute('SELECT order_date, shop_name FROM orders').fetchall(), [(None, None), (None, None)])

    def test_source_only_order_is_imported_with_existing_links(self):
        def add_order(rows):
            rows.append({**rows[0], 'order_id': '100'})
        self.edit_source('orders', add_order)
        report = run(self.db, self.source, self.root / 'import', apply=True)
        self.assertEqual(report['inserted_records'], [{'table': 'orders', 'id': 100}])
        self.assertEqual(self.conn.execute('SELECT contact_id, recipient_id FROM orders WHERE order_id=100').fetchone(), (20, 40))

    def test_report_is_persisted_for_recovery(self):
        report = run(self.db, self.source, self.root / 'apply', apply=True)
        stored = json.loads(self.conn.execute('SELECT report_json FROM history_migrations').fetchone()[0])
        self.assertEqual(stored, report)
        self.assertEqual(set(report['source_files']), {f'{t}.csv' for t in KEYS})


if __name__ == '__main__':
    unittest.main()
