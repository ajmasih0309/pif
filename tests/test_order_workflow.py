import re
import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.fix_person_ids import TABLES, migrate_person_ids, repair_database
from utils import fetch_all_orders, send_email

# Import routes without starting scheduled jobs or sending mail.
with patch('flask_apscheduler.APScheduler.start'):
    from app import app


def create_legacy_database(path):
    conn = sqlite3.connect(path)
    for table, (_, definition) in TABLES.items():
        conn.execute(f'CREATE TABLE {table} ({definition.replace(" PRIMARY KEY AUTOINCREMENT", "")})')
    conn.executescript('''
        CREATE TABLE shops (shop_name TEXT UNIQUE, shop_location TEXT);
        INSERT INTO shops VALUES ('B', 'Bentonville');
        CREATE TABLE orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT, linked_order_id INTEGER,
            contact_id INTEGER, recipient_id INTEGER, shop_name TEXT,
            pedal_partner_id INTEGER, order_date TEXT, order_type TEXT,
            order_status TEXT DEFAULT 'Open', last_status TEXT, last_updated_date TEXT,
            pickup_date TEXT, age TEXT, height TEXT, bike_style_preference TEXT,
            bike_type_first_choice TEXT, bike_type_second_choice TEXT, bike_tag REAL,
            notes TEXT, last_updated_by TEXT DEFAULT 'System'
        );
        INSERT INTO contacts (contact_name) VALUES ('Unassigned contact');
        INSERT INTO contacts VALUES ('Existing Contact', 4795550100, 'existing@example.invalid', 20);
        INSERT INTO recipients (recipient_name) VALUES ('Unassigned recipient');
        INSERT INTO recipients (recipient_name, recipient_id) VALUES ('Existing recipient', 40);
        INSERT INTO pedal_partners VALUES ('Existing partner', 60);
        INSERT INTO orders (contact_id, recipient_id, pedal_partner_id, shop_name,
            order_date, order_status) VALUES (20, 40, 60, 'B', '2026-01-01', 'Open');
    ''')
    conn.close()


class DatabaseTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'test.db'
        create_legacy_database(self.path)
        self.conn = sqlite3.connect(self.path)
        self.addCleanup(self.conn.close)

    def snapshot(self):
        return {name: self.conn.execute(f'SELECT * FROM {name}').fetchall()
                for name in ['contacts', 'recipients', 'pedal_partners', 'orders', 'shops']}


class PersonMigrationTests(DatabaseTestCase):
    def test_preserves_existing_ids_and_allocates_missing_ids_above_maximum(self):
        before = self.snapshot()
        self.assertEqual(set(migrate_person_ids(self.conn)), set(TABLES))
        for table, (key, _) in TABLES.items():
            names = [col[1] for col in self.conn.execute(f'PRAGMA table_info({table})')]
            position = names.index(key)
            after = self.conn.execute(f'SELECT * FROM {table}').fetchall()
            self.assertEqual(len(before[table]), len(after))
            for row in before[table]:
                if row[position] is not None:
                    self.assertIn(row, after)
                else:
                    match = [new for new in after if new[:position] == row[:position]
                             and new[position + 1:] == row[position + 1:]]
                    self.assertEqual(len(match), 1)
                    self.assertGreater(match[0][position], max(r[position] or 0 for r in before[table]))
            cursor = self.conn.execute(f'INSERT INTO {table} DEFAULT VALUES')
            self.assertIsNotNone(self.conn.execute(
                f'SELECT {key} FROM {table} WHERE {key}=?', (cursor.lastrowid,)).fetchone())
        self.assertEqual(self.snapshot()['orders'], before['orders'])

    def test_duplicate_ids_roll_back_all_tables(self):
        self.conn.execute("INSERT INTO recipients (recipient_name, recipient_id) VALUES ('Duplicate', 40)")
        self.conn.commit()
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'duplicate IDs'):
            migrate_person_ids(self.conn)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(any(c[5] for c in self.conn.execute('PRAGMA table_info(contacts)')))

    def test_orphan_order_link_is_not_assigned_to_unrelated_person(self):
        self.conn.execute('UPDATE orders SET recipient_id=41')
        self.conn.commit()
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'missing recipients references'):
            migrate_person_ids(self.conn)
        self.assertEqual(self.snapshot(), before)

    def test_unknown_columns_are_not_discarded(self):
        self.conn.execute('ALTER TABLE recipients ADD COLUMN extra_notes TEXT')
        self.conn.commit()
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'Unexpected recipients schema'):
            migrate_person_ids(self.conn)
        self.assertEqual(self.snapshot(), before)

    def test_backup_and_repeat_migration(self):
        before = self.snapshot()
        backup_path = repair_database(self.path)
        backup = sqlite3.connect(backup_path)
        try:
            for table, rows in before.items():
                self.assertEqual(backup.execute(f'SELECT * FROM {table}').fetchall(), rows)
        finally:
            backup.close()
        self.assertEqual(migrate_person_ids(self.conn), [])


class OrderWorkflowTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        migrate_person_ids(self.conn)
        self.config = patch.dict(app.config, TESTING=True, SECRET_KEY='test-only', DB_PATH=str(self.path))
        self.config.start()
        self.addCleanup(self.config.stop)
        self.mail_patch = patch('app.send_email', return_value=True)
        self.mail = self.mail_patch.start()
        self.addCleanup(self.mail_patch.stop)
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session['username'] = 'tester'
        self.form = {
            'contact_name': 'New Contact', 'contact_phone_number': '(479) 555-0123',
            'contact_email': 'new@example.invalid', 'pedal_partner_name': 'New partner',
            'order_date': '2026-09-28', 'shop_name': 'B', 'order_type': 'Pedal Partner',
            'recipient_name[]': ['First recipient', 'Second recipient'],
            'bike_style_preference[]': ['', 'No Preference'], 'age[]': ['', '12'],
            'height[]': ['', "5'0\""], 'bike_type_first_choice[]': ['A', 'D'],
            'bike_type_second_choice[]': ['B', 'E'], 'notes[]': ['First note', 'Second note'],
        }

    def fresh_form_token(self):
        response = self.client.get('/add')
        self.assertEqual(response.status_code, 200)
        return re.search(rb'name="form_token" value="([^"]+)"', response.data).group(1).decode()

    def create_order(self):
        self.form['form_token'] = self.fresh_form_token()
        self.assertEqual(self.client.post('/add', data=self.form).status_code, 302)
        return self.conn.execute('SELECT MAX(order_id) FROM orders').fetchone()[0]

    def test_creates_linked_recipients_and_reuses_contact_and_partner(self):
        self.create_order()
        rows = self.conn.execute('''SELECT c.contact_name, r.recipient_name,
            p.pedal_partner_name, o.bike_type_first_choice, o.bike_type_second_choice,
            o.notes, r.age, r.height, r.bike_style_preference FROM orders o
            JOIN contacts c USING (contact_id) JOIN recipients r USING (recipient_id)
            JOIN pedal_partners p USING (pedal_partner_id) WHERE o.order_id > 1
            ORDER BY o.order_id''').fetchall()
        self.assertEqual(rows, [
            ('New Contact', 'First recipient', 'New partner', 'A', 'B', 'First note', None, None, None),
            ('New Contact', 'Second recipient', 'New partner', 'D', 'E', 'Second note', 12, "5'0\"", 'No Preference'),
        ])
        self.create_order()
        for table in ['contacts', 'pedal_partners']:
            self.assertEqual(self.conn.execute(f'SELECT COUNT(DISTINCT o.{TABLES[table][0]}) FROM orders o WHERE order_id > 1').fetchone()[0], 1)
        self.assertEqual(self.conn.execute('SELECT COUNT(DISTINCT recipient_id) FROM orders WHERE order_id > 1').fetchone()[0], 4)
        with app.app_context():
            items = fetch_all_orders()
        self.assertEqual(len(items), 5)
        self.assertEqual(items[-1]['notes'], 'Second note')

    def test_notifications_only_run_after_commit(self):
        def assert_committed(**kwargs):
            with closing(sqlite3.connect(self.path)) as observer:
                self.assertEqual(observer.execute('SELECT COUNT(*) FROM orders').fetchone()[0], 3)
            return True
        self.mail.side_effect = assert_committed
        self.create_order()
        self.assertEqual(self.mail.call_count, 2)

    def test_database_failure_rolls_back_entire_submission(self):
        self.form['form_token'] = self.fresh_form_token()
        self.conn.execute('''CREATE TRIGGER fail_second BEFORE INSERT ON recipients
            WHEN NEW.recipient_name = 'Second recipient'
            BEGIN SELECT RAISE(ABORT, 'test failure'); END''')
        self.conn.commit()
        before = self.snapshot()
        with self.assertRaises(sqlite3.IntegrityError):
            self.client.post('/add', data=self.form)
        self.assertEqual(self.snapshot(), before)
        self.mail.assert_not_called()

    def test_misaligned_fields_and_invalid_shop_do_not_write(self):
        self.form['form_token'] = self.fresh_form_token()
        before = self.snapshot()
        bad = dict(self.form, **{'height[]': ["5'0\""]})
        self.assertEqual(self.client.post('/add', data=bad).status_code, 400)
        bad = dict(self.form, shop_name='Unknown')
        self.assertEqual(self.client.post('/add', data=bad).status_code, 400)
        self.assertEqual(self.snapshot(), before)
        self.mail.assert_not_called()

    def test_contact_and_pickup_status_audit_and_display(self):
        order_id = self.create_order()
        response = self.client.post(f'/update_status/{order_id}', data={'new_status': 'Contacted'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.conn.execute('SELECT order_status,last_status,last_updated_by FROM orders WHERE order_id=?',
            (order_id,)).fetchone(), ('Contacted', 'Open', 'tester'))
        self.mail.reset_mock()
        before = self.conn.execute('SELECT * FROM orders WHERE order_id=?', (order_id,)).fetchone()
        self.client.post(f'/update_status/{order_id}', data={'new_status': 'Contacted'})
        self.assertEqual(self.conn.execute('SELECT * FROM orders WHERE order_id=?', (order_id,)).fetchone(), before)
        self.mail.assert_not_called()
        response = self.client.post(f'/fulfill/{order_id}', data={'date_picked_up': '2026-09-28', 'bike_tag': '12345'})
        self.assertEqual(response.status_code, 302)
        row = self.conn.execute('''SELECT order_status,last_status,last_updated_by,
            pickup_date,bike_tag,last_updated_date FROM orders WHERE order_id=?''', (order_id,)).fetchone()
        self.assertEqual(row[:5], ('Completed', 'Contacted', 'tester', '2026-09-28', 12345))
        self.assertTrue(row[5])
        self.assertIn(b'>Completed</span>', self.client.get('/explorer').data)
        self.assertIn(b'12345', self.client.get('/?status=completed').data)

    def test_invalid_status_pickup_and_missing_order(self):
        before = self.snapshot()
        self.assertEqual(self.client.post('/update_status/1', data={'new_status': 'invalid'}).status_code, 400)
        self.assertEqual(self.client.post('/update_status/999', data={'new_status': 'Contacted'}).status_code, 404)
        self.assertEqual(self.client.post('/fulfill/1', data={'date_picked_up': 'bad', 'bike_tag': '-1'}).status_code, 400)
        self.assertEqual(self.client.post('/fulfill/999', data={'date_picked_up': '2026-09-28', 'bike_tag': '1'}).status_code, 404)
        self.assertEqual(self.snapshot(), before)
        self.mail.assert_not_called()

    def test_full_order_flow_with_empty_workshop_and_no_contact_channels(self):
        # Workshop initialization/data must never become an order prerequisite.
        from admin_tools import initialize
        self.conn.execute('CREATE TABLE users(username TEXT)')
        self.conn.execute("INSERT INTO users VALUES ('tester')")
        self.conn.commit()
        initialize(self.path, 'tester', 'Rehearse orders with empty workshop')
        self.form.update(contact_email='', contact_phone_number='')
        order_id = self.create_order()
        self.assertEqual(self.conn.execute('SELECT order_status FROM orders WHERE order_id=?', (order_id,)).fetchone()[0], 'Open')
        self.assertIn(b'Second recipient', self.client.get(f'/?status=open&q=%23{order_id}').data)
        for status in ('Cancelled','Open','Contacted','Cancelled','Open','Contacted'):
            self.assertEqual(self.client.post(f'/update_status/{order_id}', data={'new_status':status}).status_code,302)
            self.assertEqual(self.conn.execute('SELECT order_status FROM orders WHERE order_id=?',(order_id,)).fetchone()[0],status)
        self.assertEqual(self.client.post(f'/fulfill/{order_id}',data={
            'date_picked_up':'2026-10-08','bike_tag':'987654'}).status_code,302)
        self.assertEqual(self.conn.execute('SELECT order_status,bike_tag FROM orders WHERE order_id=?',(order_id,)).fetchone(),('Completed',987654))
        for table in ('bike_inventory','volunteers','bike_contributions','volunteer_hours'):
            self.assertEqual(self.conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0],0)

    def test_cancel_restore_and_complete_pipeline(self):
        self.assertFalse(self.conn.execute("SELECT 1 FROM sqlite_master WHERE name='bike_inventory'").fetchone())
        order_id = self.create_order()
        for status in ['Contacted', 'Cancelled', 'Open', 'Contacted']:
            self.assertEqual(self.client.post(f'/update_status/{order_id}', data={'new_status': status}).status_code, 302)
            self.assertEqual(self.conn.execute('SELECT order_status FROM orders WHERE order_id=?', (order_id,)).fetchone()[0], status)
        self.assertEqual(self.client.post(f'/fulfill/{order_id}', data={
            'date_picked_up': '2026-09-28', 'bike_tag': '81234',
        }).status_code, 302)
        self.assertEqual(self.conn.execute('SELECT order_status,pickup_date,bike_tag FROM orders WHERE order_id=?',
            (order_id,)).fetchone(), ('Completed', '2026-09-28', 81234))

    def test_stale_actions_cannot_overwrite_completed_order(self):
        order_id = self.create_order()
        self.client.post(f'/update_status/{order_id}', data={'new_status': 'Contacted'})
        pickup = {'date_picked_up': '2026-09-28', 'bike_tag': '81234'}
        self.client.post(f'/fulfill/{order_id}', data=pickup)
        before = self.snapshot()
        self.mail.reset_mock()
        self.assertEqual(self.client.post(f'/fulfill/{order_id}', data=pickup).status_code, 302)
        self.assertEqual(self.client.post(f'/fulfill/{order_id}', data=dict(pickup, bike_tag='99')).status_code, 409)
        for status in ['Open', 'Contacted', 'Cancelled']:
            self.assertEqual(self.client.post(f'/update_status/{order_id}', data={'new_status': status}).status_code, 409)
        self.assertEqual(self.snapshot(), before)
        self.mail.assert_not_called()

    def test_pickup_requires_contacted_and_cancelled_requires_restore(self):
        order_id = self.create_order()
        pickup = {'date_picked_up': '2026-09-28', 'bike_tag': '81234'}
        before = self.snapshot()
        self.assertEqual(self.client.post(f'/fulfill/{order_id}', data=pickup).status_code, 409)
        self.assertEqual(self.snapshot(), before)
        self.client.post(f'/update_status/{order_id}', data={'new_status': 'Cancelled'})
        before = self.snapshot()
        self.assertEqual(self.client.post(f'/fulfill/{order_id}', data=pickup).status_code, 409)
        self.assertEqual(self.client.post(f'/update_status/{order_id}', data={'new_status': 'Contacted'}).status_code, 409)
        self.assertEqual(self.snapshot(), before)

    def test_missing_email_settings_dont_prevent_order_save(self):
        with patch.dict(app.config, MAIL_DEFAULT_SENDER=None, EMAIL_MODE='test', MAIL_TEST_RECIPIENT='test@example.invalid'), patch('app.send_email', wraps=send_email), patch('utils.smtplib.SMTP') as smtp:
            self.create_order()
            smtp.assert_not_called()
        self.assertIn(b'Order saved. Confirmation email could not be sent.', self.client.get('/').data)

    def test_smtp_failure_does_not_prevent_status_save(self):
        settings = dict(EMAIL_MODE='test', MAIL_TEST_RECIPIENT='test@example.invalid',
                        MAIL_DEFAULT_SENDER='test@example.invalid', MAIL_SERVER='example.invalid',
                        MAIL_PORT=587, MAIL_USERNAME='test', MAIL_PASSWORD='test-only')
        with patch.dict(app.config, settings), patch('app.send_email', wraps=send_email), patch('utils.smtplib.SMTP', side_effect=OSError('test SMTP failure')):
            self.assertEqual(self.client.post('/update_status/1', data={'new_status': 'Contacted'}).status_code, 302)
        self.assertEqual(self.conn.execute('SELECT order_status FROM orders WHERE order_id=1').fetchone()[0], 'Contacted')


if __name__ == '__main__':
    unittest.main()
