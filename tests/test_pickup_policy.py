from datetime import datetime, timedelta, timezone
import sqlite3
import unittest
from unittest.mock import Mock, patch

from pickup_policy import pickup_window, record_contact, send_due_reminders
from test_order_workflow import DatabaseTestCase, app
from utils import EmailResult, fetch_all_orders, send_email


CONTACT = datetime(2026, 10, 1, 15, tzinfo=timezone.utc)


class PickupWindowTests(unittest.TestCase):
    def test_type_specific_windows_and_no_speciality_deadline(self):
        for kind, days in [('Public', 7), ('Pedal Partner', 28)]:
            window = pickup_window(kind, CONTACT.isoformat(), CONTACT)
            self.assertEqual(window['deadline'].astimezone(timezone.utc), CONTACT + timedelta(days=days))
            self.assertEqual(window['label'], f'{days} days left')
        for kind in ['Speciality', 'Specialty']:
            self.assertIsNone(pickup_window(kind, CONTACT.isoformat(), CONTACT)['deadline'])

    def test_countdown_missing_date_expiry_and_dst(self):
        self.assertIn('24 hour', pickup_window('Public', CONTACT.isoformat(), CONTACT + timedelta(days=6))['label'])
        self.assertTrue(pickup_window('Public', CONTACT.isoformat(), CONTACT + timedelta(days=7))['overdue'])
        self.assertIsNone(pickup_window('Public', 'bad date', CONTACT)['deadline'])
        # One week is the same local clock time even when daylight saving ends.
        window = pickup_window('Public', '2026-10-28T10:00:00-05:00', CONTACT)
        self.assertEqual(window['deadline'].isoformat(), '2026-11-04T10:00:00-06:00')


class PickupReminderTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("UPDATE orders SET order_type='Public',order_status='Contacted',last_updated_date=? WHERE order_id=1",
                          (CONTACT.isoformat(),))
        self.conn.commit()

    def send(self, when, result='sent', mode='live'):
        sender = Mock(return_value=EmailResult(result))
        send_due_reminders(self.conn, sender, mode, when)
        return sender

    def test_final_24_hours_only_once_and_no_repeats_after_expiry(self):
        self.send(CONTACT + timedelta(days=6, seconds=-1)).assert_not_called()
        sent = self.send(CONTACT + timedelta(days=6))
        sent.assert_called_once()
        self.assertIn('10/08/2026', sent.call_args.kwargs['deadline'])
        self.send(CONTACT + timedelta(days=6, minutes=15)).assert_not_called()
        self.send(CONTACT + timedelta(days=7)).assert_not_called()

    def test_partner_reminder_is_day_27_and_speciality_is_excluded(self):
        self.conn.execute("UPDATE orders SET order_type='Pedal Partner'")
        self.conn.commit()
        self.send(CONTACT + timedelta(days=6)).assert_not_called()
        self.send(CONTACT + timedelta(days=27)).assert_called_once()
        self.conn.execute("UPDATE orders SET order_type='Speciality'")
        self.conn.commit()
        self.send(CONTACT + timedelta(days=6)).assert_not_called()

    def test_no_email_invalid_dates_and_finished_orders_are_skipped(self):
        for email in ['', None, '   ']:
            self.conn.execute('UPDATE contacts SET contact_email=?', (email,))
            self.conn.commit()
            self.send(CONTACT + timedelta(days=6)).assert_not_called()
        self.conn.execute("UPDATE contacts SET contact_email='test@example.invalid'")
        self.conn.execute("UPDATE orders SET last_updated_date='not a date'")
        self.conn.commit()
        self.send(CONTACT + timedelta(days=6)).assert_not_called()
        for status in ['Open', 'Cancelled', 'Completed']:
            self.conn.execute('UPDATE orders SET order_status=?,last_updated_date=?', (status, CONTACT.isoformat()))
            self.conn.commit()
            self.send(CONTACT + timedelta(days=6)).assert_not_called()

    def test_failure_retries_without_changing_order_and_test_delivery_does_not_suppress_live(self):
        before = tuple(self.conn.execute('SELECT * FROM orders').fetchone())
        self.send(CONTACT + timedelta(days=6), 'failed').assert_called_once()
        self.send(CONTACT + timedelta(days=6, minutes=15), 'test', 'test').assert_called_once()
        self.send(CONTACT + timedelta(days=6, minutes=30)).assert_called_once()
        self.send(CONTACT + timedelta(days=6, minutes=45)).assert_not_called()
        self.assertEqual(tuple(self.conn.execute('SELECT * FROM orders').fetchone()), before)

    def test_sender_exception_is_retried_and_later_order_still_processed(self):
        self.conn.execute("INSERT INTO orders (contact_id,recipient_id,order_type,order_status,last_updated_date) VALUES (20,40,'Public','Contacted',?)", (CONTACT.isoformat(),))
        self.conn.commit()
        sender = Mock(side_effect=[RuntimeError('mail unavailable'), EmailResult('sent')])
        send_due_reminders(self.conn, sender, 'live', CONTACT + timedelta(days=6))
        self.assertEqual(sender.call_count, 2)
        self.send(CONTACT + timedelta(days=6, minutes=15)).assert_called_once()

    def test_recorded_contact_time_survives_unrelated_order_edit(self):
        record_contact(self.conn, 1, CONTACT.isoformat())
        self.conn.execute('UPDATE orders SET last_updated_date=?', ((CONTACT + timedelta(days=5)).isoformat(),))
        self.conn.commit()
        self.send(CONTACT + timedelta(days=6)).assert_called_once()

    def test_recent_claim_blocks_duplicate_worker_and_expired_claim_can_retry(self):
        sender = self.send(CONTACT + timedelta(days=6), 'failed')
        self.conn.execute('UPDATE pickup_reminder_delivery SET claimed_at=?', ((CONTACT + timedelta(days=6)).isoformat(),))
        self.conn.commit()
        self.send(CONTACT + timedelta(days=6, minutes=15)).assert_not_called()
        self.send(CONTACT + timedelta(days=6, minutes=31)).assert_called_once()


class ContactDeadlineTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        settings = patch.dict(app.config, TESTING=True, SECRET_KEY='deadline-test', DB_PATH=str(self.path), EMAIL_MODE='disabled')
        settings.start(); self.addCleanup(settings.stop)
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session['username'] = 'tester'

    def test_contact_ready_email_uses_type_and_recontact_resets_clock(self):
        for kind, deadline in [('Public', '10/08/2026'), ('Pedal Partner', '10/29/2026'), ('Speciality', None)]:
            self.conn.execute("UPDATE orders SET order_type=?,order_status='Open' WHERE order_id=1", (kind,))
            self.conn.commit()
            with patch('app.now_utc', return_value=CONTACT), patch('app.send_email', return_value=EmailResult('disabled')) as mail:
                self.assertEqual(self.client.post('/update_status/1', data={'new_status': 'Contacted'}).status_code, 302)
                if deadline:
                    self.assertIn(deadline, mail.call_args.kwargs['deadline'])
                else:
                    self.assertIsNone(mail.call_args.kwargs['deadline'])
                self.client.post('/update_status/1', data={'new_status': 'Contacted'})
                self.assertEqual(mail.call_count, 1)
        self.client.post('/update_status/1', data={'new_status': 'Cancelled'})
        self.client.post('/update_status/1', data={'new_status': 'Open'})
        later = CONTACT + timedelta(days=2)
        with patch('app.now_utc', return_value=later):
            self.client.post('/update_status/1', data={'new_status': 'Contacted'})
        self.assertEqual(self.conn.execute('SELECT contacted_at FROM order_pickup_tracking').fetchone()[0], later.isoformat())

    def test_blank_email_and_countdown_do_not_require_mail_or_inventory(self):
        self.conn.execute("UPDATE contacts SET contact_email=NULL")
        self.conn.execute("UPDATE orders SET order_type='Pedal Partner'")
        self.conn.commit()
        with patch('app.now_utc', return_value=CONTACT), patch('app.send_email', wraps=send_email), patch('utils.smtplib.SMTP') as smtp:
            self.assertEqual(self.client.post('/update_status/1', data={'new_status': 'Contacted'}).status_code, 302)
            smtp.assert_not_called()
        with app.app_context(), patch('utils.now_utc', return_value=CONTACT):
            self.assertEqual(fetch_all_orders()[0]['pickup_window']['label'], '28 days left')

    def test_reminder_switches_prevent_database_access_and_smtp(self):
        from app import check_pickup_deadlines
        for settings in [dict(EMAIL_REMINDERS_ENABLED=False, EMAIL_MODE='live', EMAIL_LIVE_ENABLED=True),
                         dict(EMAIL_REMINDERS_ENABLED=True, EMAIL_MODE='preview'),
                         dict(EMAIL_REMINDERS_ENABLED=True, EMAIL_MODE='disabled'),
                         dict(EMAIL_REMINDERS_ENABLED=True, EMAIL_MODE='live', EMAIL_LIVE_ENABLED=False)]:
            with patch.dict(app.config, settings), patch('app.get_db_connection') as db:
                check_pickup_deadlines()
                db.assert_not_called()
