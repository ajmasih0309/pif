"""Tests for login CSRF, login rate limiting, and POST-only CSRF logout (TASK-202)."""
import re
from unittest.mock import patch
from werkzeug.security import generate_password_hash

import app as portal_app
from test_order_workflow import DatabaseTestCase
from utils import LoginRateLimiter


def _extract_csrf_token(html, action):
    match = re.search(
        rf'<form[^>]*action="{re.escape(action)}"[^>]*>.*?<input[^>]*name="csrf_token"[^>]*value="([^"]+)"',
        html,
        re.S,
    )
    assert match, f'csrf_token not found for action {action}'
    return match.group(1)


class AuthSecurityTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.conn.execute(
            '''CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )'''
        )
        self.conn.execute(
            '''CREATE TABLE IF NOT EXISTS login_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                ip_address TEXT,
                device_info TEXT,
                logged_in_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )'''
        )
        self.conn.execute(
            'INSERT INTO users (username, password_hash) VALUES (?, ?)',
            ('staffer', generate_password_hash('correct-horse-battery')),
        )
        self.conn.commit()
        portal_app.login_limiter.clear()
        config = patch.dict(
            portal_app.app.config,
            TESTING=True,
            SECRET_KEY='auth-security-test',
            DB_PATH=str(self.path),
        )
        config.start()
        self.addCleanup(config.stop)
        self.addCleanup(portal_app.login_limiter.clear)
        self.client = portal_app.app.test_client()

    def test_login_requires_valid_csrf_token(self):
        missing = self.client.post(
            '/login',
            data={'username': 'staffer', 'password': 'correct-horse-battery'},
        )
        self.assertEqual(missing.status_code, 400)

        invalid = self.client.post(
            '/login',
            data={
                'csrf_token': 'tampered-token',
                'username': 'staffer',
                'password': 'correct-horse-battery',
            },
        )
        self.assertEqual(invalid.status_code, 400)

        page = self.client.get('/login')
        self.assertEqual(page.status_code, 200)
        token = _extract_csrf_token(page.get_data(as_text=True), '/login')
        ok = self.client.post(
            '/login',
            data={
                'csrf_token': token,
                'username': 'staffer',
                'password': 'correct-horse-battery',
            },
        )
        self.assertEqual(ok.status_code, 302)
        self.assertEqual(ok.location, '/')

    def test_login_rate_limits_after_repeated_failures_and_resets_on_success(self):
        page = self.client.get('/login')
        token = _extract_csrf_token(page.get_data(as_text=True), '/login')

        for _ in range(5):
            resp = self.client.post(
                '/login',
                data={'csrf_token': token, 'username': 'staffer', 'password': 'wrong'},
                environ_base={'REMOTE_ADDR': '10.0.0.10'},
            )
            self.assertEqual(resp.status_code, 200)

        blocked = self.client.post(
            '/login',
            data={
                'csrf_token': token,
                'username': 'staffer',
                'password': 'correct-horse-battery',
            },
            environ_base={'REMOTE_ADDR': '10.0.0.10'},
        )
        self.assertEqual(blocked.status_code, 429)
        self.assertIn('Too many failed login attempts', blocked.get_data(as_text=True))

        # Different IP is unaffected and resets its own counter on success.
        other_ip = self.client.post(
            '/login',
            data={
                'csrf_token': token,
                'username': 'staffer',
                'password': 'correct-horse-battery',
            },
            environ_base={'REMOTE_ADDR': '10.0.0.11'},
        )
        self.assertEqual(other_ip.status_code, 302)

    def test_rate_limiter_expires_after_window(self):
        now = [100.0]
        limiter = LoginRateLimiter(max_attempts=2, window_seconds=60, clock=lambda: now[0])
        limiter.record_failure('1.2.3.4')
        limiter.record_failure('1.2.3.4')
        limited, retry = limiter.is_limited('1.2.3.4')
        self.assertTrue(limited)
        self.assertEqual(retry, 60)

        now[0] = 161.0
        limited, retry = limiter.is_limited('1.2.3.4')
        self.assertFalse(limited)
        self.assertEqual(retry, 0)

    def test_logout_requires_post_and_valid_csrf_token(self):
        with self.client.session_transaction() as sess:
            sess['username'] = 'staffer'

        get_resp = self.client.get('/logout')
        self.assertEqual(get_resp.status_code, 405)
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get('username'), 'staffer')

        bad_post = self.client.post('/logout', data={'csrf_token': 'invalid'})
        self.assertEqual(bad_post.status_code, 400)
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get('username'), 'staffer')

        desk = self.client.get('/')
        self.assertEqual(desk.status_code, 200)
        logout_token = _extract_csrf_token(desk.get_data(as_text=True), '/logout')

        ok_post = self.client.post('/logout', data={'csrf_token': logout_token})
        self.assertEqual(ok_post.status_code, 302)
        self.assertEqual(ok_post.location, '/login')
        with self.client.session_transaction() as sess:
            self.assertIsNone(sess.get('username'))
