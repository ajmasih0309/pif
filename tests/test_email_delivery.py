from email import message_from_string
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from flask import Flask
from utils import send_email


class EmailDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app = Flask(__name__, template_folder=str(Path(__file__).resolve().parents[1] / 'templates'))
        self.app.config.update(EMAIL_PREVIEW_DIR=self.temp.name,
                               MAIL_DEFAULT_SENDER='sender@example.invalid', MAIL_USERNAME='sender@example.invalid',
                               MAIL_PASSWORD='fake-test-only', MAIL_SERVER='smtp.example.invalid', MAIL_PORT=587,
                               MAIL_TEST_RECIPIENT='controlled@example.invalid')
        self.context = self.app.app_context()
        self.context.push(); self.addCleanup(self.context.pop)
        smtp = patch('utils.smtplib.SMTP')
        self.smtp = smtp.start(); self.addCleanup(smtp.stop)
        self.transport = self.smtp.return_value.__enter__.return_value
        self.transport.sendmail.return_value = {}

    def send(self, **kwargs):
        return send_email('requester@example.invalid', 'Request received', 'order_received', recipient_name='Test Recipient', **kwargs)

    def test_default_mode_previews_without_network_even_with_credentials(self):
        result = self.send()
        self.assertEqual(result.status, 'preview')
        self.assertFalse(result)
        self.smtp.assert_not_called()
        page = Path(result.preview_path).read_text()
        self.assertIn('nothing was sent', page)
        self.assertIn('requester@example.invalid', page)
        self.assertIn('We received your bike request', page)
        self.assertNotIn('Your Bike is Ready!', page)
        self.assertNotIn('https://', page)
        self.assertEqual(Path(result.preview_path).stat().st_mode & 0o777, 0o600)

    def test_missing_optional_email_skips_all_delivery_modes(self):
        for mode in ['preview', 'test', 'live']:
            self.app.config.update(EMAIL_MODE=mode, EMAIL_LIVE_ENABLED=True)
            for recipient in [None, '', '   ']:
                result = send_email(recipient, 'No recipient', 'order_received')
                self.assertEqual(result.status, 'skipped')
        self.smtp.assert_not_called()
        self.assertEqual(list(Path(self.temp.name).iterdir()), [])

    def test_preview_metadata_and_name_are_escaped(self):
        result = send_email('<script>bad</script>', '<script>subject</script>', 'order_received', recipient_name='<script>name</script>')
        page = Path(result.preview_path).read_text()
        self.assertNotIn('<script>', page)
        self.assertIn('sandbox=""', page)
        self.smtp.assert_not_called()

    def test_test_mode_uses_only_the_configured_sink(self):
        self.app.config['EMAIL_MODE'] = 'test'
        result = self.send()
        self.assertEqual(result.status, 'test')
        sender, recipients, raw = self.transport.sendmail.call_args.args
        self.assertEqual(sender, 'sender@example.invalid')
        self.assertEqual(recipients, ['controlled@example.invalid'])
        msg = message_from_string(raw)
        self.assertEqual(msg['To'], 'controlled@example.invalid')
        self.assertEqual(msg['Subject'], '[TEST] Request received')
        self.assertIsNone(msg['Cc']); self.assertIsNone(msg['Bcc'])
        self.assertNotIn('requester@example.invalid', raw)
        self.assertIsNotNone(self.transport.starttls.call_args.kwargs['context'])

    def test_missing_or_multiple_test_recipients_block_delivery(self):
        self.app.config['EMAIL_MODE'] = 'test'
        for sink in [None, '', 'a@example.invalid,b@example.invalid', 'a@example.invalid\r\nBcc: b@example.invalid']:
            self.app.config['MAIL_TEST_RECIPIENT'] = sink
            self.assertEqual(self.send().status, 'failed')
        self.smtp.assert_not_called()

    def test_live_requires_both_switches(self):
        self.app.config['EMAIL_MODE'] = 'live'
        for enabled in [None, False, 'true']:
            self.app.config['EMAIL_LIVE_ENABLED'] = enabled
            self.assertEqual(self.send().status, 'failed')
        self.smtp.assert_not_called()
        self.app.config['EMAIL_LIVE_ENABLED'] = True
        self.assertEqual(self.send().status, 'sent')
        self.assertEqual(self.transport.sendmail.call_args.args[1], ['requester@example.invalid'])

    def test_disabled_and_unknown_modes_never_connect(self):
        for mode, expected in [('disabled', 'disabled'), ('typo', 'failed')]:
            self.app.config['EMAIL_MODE'] = mode
            self.assertEqual(self.send().status, expected)
        self.smtp.assert_not_called()
        self.assertEqual(list(Path(self.temp.name).iterdir()), [])

    def test_missing_credentials_or_smtp_failure_is_reported(self):
        self.app.config.update(EMAIL_MODE='test', MAIL_PASSWORD=None)
        self.assertEqual(self.send().status, 'failed')
        self.smtp.assert_not_called()
        self.app.config['MAIL_PASSWORD'] = 'fake-test-only'
        self.transport.sendmail.side_effect = OSError('mock failure')
        self.assertEqual(self.send().status, 'failed')

    def test_preview_write_failure_does_not_fall_back_to_delivery(self):
        with patch('utils.os.open', side_effect=PermissionError('mock failure')):
            self.assertEqual(self.send().status, 'failed')
        self.smtp.assert_not_called()

    def test_reminders_do_not_read_orders_when_disabled(self):
        from test_order_workflow import app
        from app import check_pickup_deadlines
        with patch.dict(app.config, EMAIL_REMINDERS_ENABLED=False), patch('app.get_db_connection') as db, patch('app.send_email') as send:
            check_pickup_deadlines()
            db.assert_not_called(); send.assert_not_called()

    def test_each_template_renders_the_right_message_without_external_images(self):
        for template, expected in [('order_received', 'We received your bike request'),
                                   ('pickup_ready', 'Your bike is ready for pickup'),
                                   ('pickup_reminder', 'A reminder about your bike pickup')]:
            result = send_email('test@example.invalid', 'Preview', template, recipient_name=None, deadline='10/01/2026')
            self.assertEqual(result.status, 'preview')
            page = Path(result.preview_path).read_text()
            self.assertIn(expected, page)
            self.assertNotIn('placeholder.com', page)
            self.assertNotIn('<strong>None</strong>', page)
        self.smtp.assert_not_called()
