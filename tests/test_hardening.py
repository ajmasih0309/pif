"""Tests for pre-production hardening (TASK-201, TASK-203, TASK-205, TASK-206, TASK-207)."""
from unittest.mock import patch

import app as portal_app
from migrations import migrate_database
from scripts.send_reminders import run_reminders
from test_order_workflow import DatabaseTestCase


class ProductionHardeningTests(DatabaseTestCase):
    def test_security_headers_and_cookie_defaults_present(self):
        self.assertTrue(portal_app.app.config['SESSION_COOKIE_HTTPONLY'])
        self.assertEqual(portal_app.app.config['SESSION_COOKIE_SAMESITE'], 'Lax')

        with patch.dict(portal_app.app.config, TESTING=True, DB_PATH=str(self.path)):
            client = portal_app.app.test_client()
            resp = client.get('/login')
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.headers.get('X-Content-Type-Options'), 'nosniff')
            self.assertEqual(resp.headers.get('X-Frame-Options'), 'SAMEORIGIN')
            self.assertEqual(resp.headers.get('Referrer-Policy'), 'same-origin')

    def test_client_ip_ignores_untrusted_forwarded_header_by_default(self):
        with portal_app.app.test_request_context(
            '/login',
            headers={'X-Forwarded-For': '203.0.113.99'},
            environ_base={'REMOTE_ADDR': '192.168.1.50'},
        ):
            self.assertEqual(portal_app._client_ip(), '192.168.1.50')

    def test_startup_readiness_requires_strong_secret_in_production(self):
        migrate_database(self.path, backup=False, dry_run=False)
        with patch.dict(portal_app.app.config, DB_PATH=str(self.path), SECRET_KEY='loremipsum'):
            with self.assertRaisesRegex(RuntimeError, 'SECRET_KEY'):
                portal_app.check_startup_readiness(require_secret=True)
        with patch.dict(portal_app.app.config, DB_PATH=str(self.path), SECRET_KEY='short'):
            with self.assertRaisesRegex(RuntimeError, 'SECRET_KEY'):
                portal_app.check_startup_readiness(require_secret=True)
        with patch.dict(portal_app.app.config, DB_PATH=str(self.path), SECRET_KEY='a-strong-production-secret-key-1234'):
            self.assertGreaterEqual(portal_app.check_startup_readiness(require_secret=True), 3)

    def test_single_owner_reminder_runner_respects_safety_gates(self):
        with patch.dict(
            portal_app.app.config,
            DB_PATH=str(self.path),
            EMAIL_MODE='disabled',
            EMAIL_REMINDERS_ENABLED=False,
            EMAIL_LIVE_ENABLED=False,
        ):
            result = run_reminders()
            self.assertFalse(result['ran'])
