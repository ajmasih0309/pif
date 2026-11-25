"""Tests for the versioned schema migration framework (TASK-601)."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from migrations import (
    EXPECTED_SCHEMA_VERSION,
    apply_migrations,
    current_version,
    migrate_database,
    pending_migrations,
    verify_schema_ready,
)


class MigrationFrameworkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db_path = Path(self.tmp.name) / 'legacy.db'
        conn = sqlite3.connect(self.db_path)
        conn.executescript('''
            CREATE TABLE shops (shop_name TEXT UNIQUE, shop_location TEXT);
            INSERT INTO shops VALUES ('B', 'Bentonville');
            CREATE TABLE orders (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                linked_order_id INTEGER, contact_id INTEGER, recipient_id INTEGER,
                shop_name TEXT, pedal_partner_id INTEGER, order_date TEXT,
                order_type TEXT, order_status TEXT DEFAULT 'Open', last_status TEXT,
                last_updated_date TEXT, pickup_date TEXT, age TEXT, height TEXT,
                bike_style_preference TEXT, bike_type_first_choice TEXT,
                bike_type_second_choice TEXT, bike_tag REAL, notes TEXT,
                last_updated_by TEXT DEFAULT 'System'
            );
        ''')
        conn.close()

    def test_dry_run_and_apply_migrates_legacy_db_idempotently(self):
        dry = migrate_database(self.db_path, backup=False, dry_run=True)
        self.assertEqual(dry['current_version'], 0)
        self.assertEqual(dry['expected_version'], EXPECTED_SCHEMA_VERSION)
        self.assertEqual(len(dry['pending']), EXPECTED_SCHEMA_VERSION)

        applied = migrate_database(self.db_path, backup=False, dry_run=False)
        self.assertEqual(applied['current_version'], EXPECTED_SCHEMA_VERSION)
        self.assertEqual(len(applied['applied']), EXPECTED_SCHEMA_VERSION)
        self.assertEqual(applied['fk_errors'], 0)
        self.assertEqual(applied['integrity'], 'ok')

        # Second run is a clean no-op.
        again = migrate_database(self.db_path, backup=False, dry_run=False)
        self.assertEqual(again['applied'], [])
        self.assertEqual(again['current_version'], EXPECTED_SCHEMA_VERSION)

        conn = sqlite3.connect(self.db_path)
        try:
            inv_col = [r for r in conn.execute('PRAGMA table_info(bike_inventory)').fetchall() if r[1] == 'bike_tag'][0]
            ord_col = [r for r in conn.execute('PRAGMA table_info(orders)').fetchall() if r[1] == 'bike_tag'][0]
            self.assertEqual(inv_col[2], 'INTEGER')
            self.assertEqual(ord_col[2], 'INTEGER')
        finally:
            conn.close()

    def test_target_version_applies_incrementally(self):
        conn = sqlite3.connect(self.db_path)
        try:
            apply_migrations(conn, target_version=1)
            self.assertEqual(current_version(conn), 1)
            self.assertEqual(len(pending_migrations(conn)), EXPECTED_SCHEMA_VERSION - 1)
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            self.assertIn('order_submissions', tables)
            self.assertIn('order_pickup_tracking', tables)
            self.assertNotIn('bike_inventory', tables)
        finally:
            conn.close()

    def test_verify_schema_ready_reports_clear_operator_errors(self):
        missing = Path(self.tmp.name) / 'does_not_exist.db'
        with self.assertRaisesRegex(RuntimeError, 'Database file not found'):
            verify_schema_ready(missing)

        with self.assertRaisesRegex(RuntimeError, f'version 0, expected {EXPECTED_SCHEMA_VERSION}.*migrate_db\\.py --apply'):
            verify_schema_ready(self.db_path)

        conn = sqlite3.connect(self.db_path)
        try:
            apply_migrations(conn, target_version=1)
            conn.commit()
        finally:
            conn.close()
        with self.assertRaisesRegex(RuntimeError, f'version 1, expected {EXPECTED_SCHEMA_VERSION}'):
            verify_schema_ready(self.db_path)

        migrate_database(self.db_path, backup=False, dry_run=False)
        self.assertEqual(verify_schema_ready(self.db_path), EXPECTED_SCHEMA_VERSION)
