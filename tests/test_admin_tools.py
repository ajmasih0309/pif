from contextlib import closing
import json
import sqlite3
from unittest.mock import patch

from test_order_workflow import DatabaseTestCase
from admin_tools import (connect, initialize, order_preview, edit_order,
                         add_bike, lookup_bike)


class AdminToolsTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.conn.execute('CREATE TABLE users (username TEXT)')
        self.conn.execute("INSERT INTO users VALUES ('operator')")
        self.conn.commit()

    def initialize(self):
        return initialize(self.path, 'operator', 'Set up lookup')

    def preview(self, changes):
        with closing(connect(self.path)) as conn:
            return order_preview(conn, 1, changes)

    def apply(self, changes, version=None):
        return edit_order(self.path, 1, changes, version or self.preview(changes)['version'],
                          'operator', 'Correct a transcription error')

    def test_initialize_preserves_orders_and_backup_is_before_schema(self):
        before = self.snapshot()
        result = self.initialize()
        self.assertEqual(before, self.snapshot())
        with closing(sqlite3.connect(result['backup'])) as backup:
            self.assertFalse(backup.execute("SELECT 1 FROM sqlite_master WHERE name='bike_inventory'").fetchone())
            self.assertEqual(backup.execute('SELECT COUNT(*) FROM orders').fetchone()[0], 1)
        self.assertFalse(self.initialize()['applied'])

    def test_notes_upgrade_preserves_contributions_and_backs_up_old_schema(self):
        self.initialize()
        self.conn.execute('ALTER TABLE bike_contributions DROP COLUMN notes')
        self.conn.execute("INSERT INTO bike_inventory(inventory_id,bike_tag,shop_name,created_at) VALUES (7,'123','B','2026-10-05T00:00:00+00:00')")
        self.conn.execute("INSERT INTO bike_contributions(contribution_id,inventory_id,recorded_name,source_key) VALUES (9,7,'Original volunteer','original:1')")
        self.conn.commit()
        before=self.conn.execute('SELECT * FROM bike_contributions').fetchall()
        result=self.initialize()
        self.assertTrue(result['applied'])
        self.assertEqual(self.conn.execute('SELECT * FROM bike_contributions').fetchall(),[before[0]+(None,)])
        with closing(sqlite3.connect(result['backup'])) as backup:
            self.assertNotIn('notes',{r[1] for r in backup.execute('PRAGMA table_info(bike_contributions)')})
            self.assertEqual(backup.execute('SELECT * FROM bike_contributions').fetchall(),before)
        self.assertFalse(self.initialize()['applied'])

    def test_notes_upgrade_rolls_back_if_audit_fails(self):
        self.initialize()
        self.conn.execute('ALTER TABLE bike_contributions DROP COLUMN notes')
        self.conn.commit()
        with patch('admin_tools._audit',side_effect=sqlite3.IntegrityError('audit failed')):
            with self.assertRaises(sqlite3.IntegrityError): self.initialize()
        self.assertNotIn('notes',{r[1] for r in self.conn.execute('PRAGMA table_info(bike_contributions)')})

    def test_volunteer_metadata_upgrade_preserves_existing_people_and_defaults(self):
        self.initialize()
        self.conn.execute('ALTER TABLE volunteers DROP COLUMN joined_on')
        self.conn.execute('ALTER TABLE volunteers DROP COLUMN is_active')
        self.conn.execute("INSERT INTO volunteers(volunteer_id,volunteer_name) VALUES (10,'Existing person')")
        self.conn.commit()
        result=self.initialize()
        self.assertEqual(self.conn.execute('SELECT volunteer_id,volunteer_name,joined_on,is_active FROM volunteers').fetchall(),[(10,'Existing person',None,1)])
        with closing(sqlite3.connect(result['backup'])) as backup:
            self.assertNotIn('is_active',{r[1] for r in backup.execute('PRAGMA table_info(volunteers)')})
        self.assertFalse(self.initialize()['applied'])
        with self.assertRaises(sqlite3.IntegrityError): self.conn.execute('UPDATE volunteers SET is_active=2')
        self.conn.rollback()

    def test_volunteer_metadata_upgrade_rolls_back_on_audit_error(self):
        self.initialize()
        self.conn.execute('ALTER TABLE volunteers DROP COLUMN joined_on')
        self.conn.execute('ALTER TABLE volunteers DROP COLUMN is_active')
        self.conn.commit()
        with patch('admin_tools._audit',side_effect=sqlite3.IntegrityError('audit failed')):
            with self.assertRaises(sqlite3.IntegrityError): self.initialize()
        self.assertNotIn('is_active',{r[1] for r in self.conn.execute('PRAGMA table_info(volunteers)')})

    def test_preview_is_read_only_then_apply_audits_and_backs_up(self):
        self.initialize()
        before = self.snapshot()
        changes = {'notes': 'Corrected note', 'shop_name': 'B'}
        preview = self.preview(changes)
        self.assertEqual(before, self.snapshot())
        result = self.apply(changes, preview['version'])
        with closing(sqlite3.connect(result['backup'])) as backup:
            self.assertIsNone(backup.execute('SELECT notes FROM orders').fetchone()[0])
        row = self.conn.execute('SELECT notes,last_updated_by FROM orders').fetchone()
        self.assertEqual(row, ('Corrected note', 'operator'))
        audit = self.conn.execute("SELECT before_json,after_json FROM admin_changes WHERE entity='orders'").fetchone()
        self.assertIsNone(json.loads(audit[0])['notes'])
        self.assertEqual(json.loads(audit[1])['notes'], 'Corrected note')

    def test_stale_preview_rejected(self):
        self.initialize()
        preview = self.preview({'notes': 'mine'})
        self.conn.execute("UPDATE orders SET notes='another edit'")
        self.conn.commit()
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.apply({'notes': 'mine'}, preview['version'])
        self.assertEqual(self.conn.execute('SELECT notes FROM orders').fetchone()[0], 'another edit')

    def test_audit_failure_rolls_back_order(self):
        self.initialize()
        before = self.snapshot()
        with patch('admin_tools._audit', side_effect=sqlite3.IntegrityError('audit failed')):
            with self.assertRaises(sqlite3.IntegrityError):
                self.apply({'notes': 'must roll back'})
        self.assertEqual(before, self.snapshot())

    def test_backup_failure_prevents_edit(self):
        self.initialize()
        before = self.snapshot()
        with patch('admin_tools._backup', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.apply({'notes': 'must not save'})
        self.assertEqual(before, self.snapshot())

    def test_shared_person_and_status_cannot_be_edited(self):
        for field in ['recipient_name', 'recipient_id', 'contact_name', 'order_status', 'order_id']:
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.preview({field: 'changed'})

    def test_validates_dates_tags_choices_and_shop(self):
        for changes in [{'pickup_date': '2026-02-30'}, {'bike_tag': '123.5'},
                        {'bike_tag': '000123'}, {'bike_tag': str(2**53)},
                        {'bike_type_first_choice': 'G'}, {'shop_name': 'missing'}]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.preview(changes)

    def test_completed_order_cannot_lose_pickup_details(self):
        self.conn.execute("UPDATE orders SET order_status='Completed', bike_tag=123, pickup_date='2026-01-02'")
        self.conn.commit()
        with self.assertRaises(ValueError):
            self.preview({'bike_tag': None})
        with self.assertRaises(ValueError):
            self.preview({'pickup_date': ''})

    def test_clearing_choice_does_not_silently_reveal_shared_value(self):
        self.conn.execute("UPDATE recipients SET bike_type_first_choice='A' WHERE recipient_id=40")
        self.conn.commit()
        with self.assertRaisesRegex(ValueError, 'shared recipient fallback'):
            self.preview({'bike_type_first_choice': None})
        self.assertEqual(self.preview({'bike_type_first_choice': 'B'})['changes']['bike_type_first_choice']['after'], 'B')

    def test_unknown_actor_cannot_change_schema(self):
        with self.assertRaises(ValueError):
            initialize(self.path, 'unknown', 'test')
        self.assertFalse(self.conn.execute("SELECT 1 FROM sqlite_master WHERE name='bike_inventory'").fetchone())

    def test_global_tag_unique_preserves_text_and_optional_lookup(self):
        self.initialize()
        result = add_bike(self.path, {'bike_tag': '00123', 'shop_name': 'B', 'wheel_size': '26 inch'},
                          'operator', 'New bike')
        self.assertTrue(result['applied'])
        self.conn.execute("INSERT INTO shops VALUES ('R', 'Rogers')")
        self.conn.commit()
        with self.assertRaisesRegex(ValueError, 'already exists'):
            add_bike(self.path, {'bike_tag': '00123', 'shop_name': 'R'}, 'operator', 'Duplicate')
        with closing(connect(self.path)) as conn:
            self.assertEqual(lookup_bike(conn, '00123')['wheel_size'], '26 inch')
            self.assertEqual(lookup_bike(conn, '123')['bike_tag'], '123')
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0], 1)
        self.apply({'bike_tag': '456'})  # No matching inventory row required.

    def test_foreign_key_and_unique_constraints_enforced(self):
        self.initialize()
        with closing(connect(self.path, writable=True)) as conn, conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("INSERT INTO bike_inventory (bike_tag,shop_name,created_at) VALUES ('1','missing','today')")
            conn.execute("INSERT INTO bike_inventory (bike_tag,shop_name,created_at) VALUES ('1','B','today')")
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("INSERT INTO bike_inventory (bike_tag,shop_name,created_at) VALUES ('1','B','tomorrow')")
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("INSERT INTO bike_inventory (bike_tag,shop_name,created_at) VALUES ('0001','B','tomorrow')")

    def test_backup_includes_committed_wal_changes(self):
        self.conn.execute('PRAGMA journal_mode=WAL')
        self.conn.execute("UPDATE orders SET notes='committed in WAL'")
        self.conn.commit()
        result = self.initialize()
        with closing(sqlite3.connect(result['backup'])) as backup:
            self.assertEqual(backup.execute('SELECT notes FROM orders').fetchone()[0], 'committed in WAL')

    def test_multiple_contributors_link_to_one_bike_without_merging_people(self):
        self.initialize()
        result = add_bike(self.path, {'bike_tag': '123', 'shop_name': 'B', 'volunteer_name': 'Alex & Robin'},
                          'operator', 'Record contributors')
        inventory_id = result['inventory_id']
        with closing(connect(self.path, writable=True)) as conn, conn:
            conn.execute("INSERT INTO volunteers(volunteer_id,volunteer_name) VALUES (10,'Confirmed person')")
            conn.execute('INSERT INTO bike_contributions(inventory_id,volunteer_id,recorded_name) VALUES (?,?,?)',
                         (inventory_id, 10, 'Additional contributor'))
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute('INSERT INTO bike_contributions(inventory_id,volunteer_id) VALUES (?,?)', (inventory_id, 999))
        with closing(connect(self.path)) as conn:
            bike = lookup_bike(conn, '123')
        self.assertEqual(len(bike['contributions']), 2)
        self.assertIsNone(bike['contributions'][0]['volunteer_id'])
        self.assertEqual(bike['contributions'][0]['recorded_name'], 'Alex & Robin')
        self.assertEqual(bike['contributions'][1]['volunteer_name'], 'Confirmed person')
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM bike_inventory').fetchone()[0], 1)

    def test_upgrade_existing_inline_volunteer_preserves_name_once(self):
        self.conn.executescript('''CREATE TABLE bike_inventory (
            inventory_id INTEGER PRIMARY KEY, bike_tag TEXT UNIQUE, shop_name TEXT,
            recorded_at TEXT, volunteer_name TEXT, created_at TEXT);
            INSERT INTO bike_inventory VALUES (7,'123','B','2025-01-01','Legacy name','today');''')
        self.initialize()
        self.assertFalse(self.initialize()['applied'])
        self.assertEqual(self.conn.execute('SELECT inventory_id,recorded_name FROM bike_contributions').fetchall(),
                         [(7, 'Legacy name')])
