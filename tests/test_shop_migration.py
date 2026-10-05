import sqlite3
import tempfile
import unittest
from pathlib import Path

from flask import Flask

from scripts.fix_duplicate_shops import migrate_shops, repair_database
from utils import fetch_all_orders


class ShopMigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'test.db'
        self.conn = sqlite3.connect(self.path)
        self.addCleanup(self.conn.close)
        self.conn.executescript('''
            CREATE TABLE shops (shop_name TEXT, shop_location TEXT);
            INSERT INTO shops VALUES ('B', NULL), ('B', 'Bentonville'),
                ('R', 'Rogers'), (NULL, NULL);
            CREATE TABLE contacts (contact_id INTEGER, contact_name TEXT,
                contact_email TEXT, contact_phone_number TEXT);
            CREATE TABLE recipients (recipient_id INTEGER, recipient_name TEXT,
                age INTEGER, height TEXT, bike_style_preference TEXT,
                bike_type_first_choice TEXT, bike_type_second_choice TEXT);
            CREATE TABLE pedal_partners (pedal_partner_id INTEGER, pedal_partner_name TEXT);
            CREATE TABLE orders (order_id INTEGER PRIMARY KEY, linked_order_id INTEGER,
                contact_id INTEGER, recipient_id INTEGER, shop_name TEXT,
                pedal_partner_id INTEGER, age INTEGER, height TEXT,
                bike_style_preference TEXT, order_date TEXT, order_status TEXT,
                pickup_date TEXT, order_type TEXT, bike_type_first_choice TEXT,
                bike_type_second_choice TEXT, notes TEXT, bike_tag REAL);
            INSERT INTO orders (order_id, shop_name) VALUES (1, 'B'), (2, 'B'),
                (3, 'R'), (4, NULL), (5, 'unknown');
        ''')

    def fetch_orders(self):
        app = Flask(__name__)
        app.config['DB_PATH'] = str(self.path)
        with app.app_context():
            return fetch_all_orders()

    def test_join_returns_each_order_once_and_preserves_data(self):
        before = self.conn.execute('SELECT * FROM orders').fetchall()
        self.assertEqual(len(self.fetch_orders()), 7)
        self.assertEqual(migrate_shops(self.conn), 1)
        items = self.fetch_orders()
        self.assertCountEqual([item['order_id'] for item in items], [1, 2, 3, 4, 5])
        self.assertEqual({i['shop_location'] for i in items if i['shop_name'] == 'B'}, {'Bentonville'})
        self.assertEqual(self.conn.execute('SELECT * FROM orders').fetchall(), before)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM shops WHERE shop_name IS NULL').fetchone()[0], 1)

    def test_repeated_inserts_cannot_recreate_duplicate(self):
        migrate_shops(self.conn)
        for _ in range(3):
            self.conn.execute("INSERT OR IGNORE INTO shops (shop_name) VALUES ('B')")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM shops WHERE shop_name='B'").fetchone()[0], 1)
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("INSERT INTO shops (shop_name) VALUES ('B')")

    def test_repeat_migration_is_safe(self):
        migrate_shops(self.conn)
        self.assertEqual(migrate_shops(self.conn), 0)
        self.assertEqual(len(self.fetch_orders()), 5)

    def test_conflict_rolls_back_all_cleanup(self):
        self.conn.execute("INSERT INTO shops VALUES ('R', 'Different location')")
        self.conn.commit()
        before = self.conn.execute('SELECT rowid, * FROM shops').fetchall()
        with self.assertRaisesRegex(ValueError, 'Conflicting locations'):
            migrate_shops(self.conn)
        self.assertEqual(self.conn.execute('SELECT rowid, * FROM shops').fetchall(), before)
        self.assertEqual(self.conn.execute('PRAGMA index_list(shops)').fetchall(), [])

    def test_backup_preserves_original_database(self):
        backup_path = repair_database(self.path)
        backup = sqlite3.connect(backup_path)
        try:
            self.assertEqual(backup.execute("SELECT COUNT(*) FROM shops WHERE shop_name='B'").fetchone()[0], 2)
            self.assertEqual(backup.execute('SELECT COUNT(*) FROM orders').fetchone()[0], 5)
        finally:
            backup.close()
        self.assertEqual(len(self.fetch_orders()), 5)


if __name__ == '__main__':
    unittest.main()
