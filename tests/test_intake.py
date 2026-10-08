from concurrent.futures import ThreadPoolExecutor
import re
import sqlite3
from unittest.mock import patch

from scripts.fix_person_ids import migrate_person_ids
from test_order_workflow import DatabaseTestCase, app


def token(response):
    return re.search(rb'name="form_token" value="([^"]+)"', response.data).group(1).decode()


class IntakeTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        migrate_person_ids(self.conn)
        config = patch.dict(app.config, TESTING=True, SECRET_KEY='test-intake', DB_PATH=str(self.path))
        config.start(); self.addCleanup(config.stop)
        mail = patch('app.send_email', return_value=True)
        self.mail = mail.start(); self.addCleanup(mail.stop)
        self.staff = app.test_client()
        with self.staff.session_transaction() as session:
            session['username'] = 'tester'
        self.form = dict(contact_name='Test Contact', contact_phone_number='479-555-0123',
                         contact_email='test@example.invalid', shop_name='B', order_date='2026-09-29',
                         order_type='Public', pedal_partner_name='')
        self.form.update({'recipient_name[]': ['First', 'Second'], 'age[]': ['12', '13'],
                          'height[]': ['', ''], 'bike_style_preference[]': ['Male', ''],
                          'bike_type_first_choice[]': ['A', ''], 'bike_type_second_choice[]': ['', 'F'],
                          'notes[]': ['<careful> & patient', 'Second note']})

    def invite(self):
        key = token(self.staff.get('/request-links'))
        fields = dict(form_token=key, shop_name='B', order_type='Public', days='7', label='Test family', pedal_partner_name='')
        response = self.staff.post('/request-links', data=fields)
        self.assertEqual(response.status_code, 200)
        link = re.search(rb'id="created-link" value="([^"]+)"', response.data).group(1).decode()
        return link, fields

    def requester(self, link):
        client = app.test_client()
        response = client.get(link)
        self.assertEqual(response.status_code, 200)
        return client, dict(self.form, form_token=token(response))

    def test_staff_retry_saves_once_and_notifies_once(self):
        fields = dict(self.form, form_token=token(self.staff.get('/add')))
        for _ in range(2):
            self.assertEqual(self.staff.post('/add', data=fields).status_code, 302)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0], 3)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM order_submissions').fetchone()[0], 1)
        self.assertEqual(self.mail.call_count, 2)

    def test_fresh_forms_allow_legitimate_repeat_requests(self):
        a, b = token(self.staff.get('/add')), token(self.staff.get('/add'))
        for key in (a, b):
            self.assertEqual(self.staff.post('/add', data=dict(self.form, form_token=key)).status_code, 302)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0], 5)

    def test_validation_preserves_all_recipients_and_reuses_token(self):
        fields = dict(self.form, form_token=token(self.staff.get('/add')))
        invalid = dict(fields, contact_email='bad', **{'age[]': ['-5', '13']})
        response = self.staff.post('/add', data=invalid)
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'Enter an email address', response.data)
        self.assertIn(b'value="Second"', response.data)
        self.assertIn(b'&lt;careful&gt; &amp; patient', response.data)
        self.assertEqual(token(response), fields['form_token'])
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0], 1)
        self.assertEqual(self.staff.post('/add', data=fields).status_code, 302)

    def test_invalid_values_do_not_create_rows(self):
        key = token(self.staff.get('/add'))
        for change in [dict(contact_name=''), dict(contact_phone_number='123'), dict(contact_phone_number='abc4795550123'), dict(order_date='2026-02-30'),
                       dict(order_type='Unknown'), dict(order_type='Pedal Partner'), {'bike_type_first_choice[]': ['Z', 'A']},
                       {'height[]': ['invalid', '']}, {'age[]': ['121', '13']}, {'age[]': ['9' * 5000, '13']}, {'recipient_name[]': ['', 'Second']}]:
            with self.subTest(change=change):
                self.assertEqual(self.staff.post('/add', data={**self.form, 'form_token': key, **change}).status_code, 400)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0], 1)
        self.mail.assert_not_called()

    def test_staff_phone_and_email_are_independently_optional(self):
        for email, phone in [('', ''), ('', '4795550123'), ('test@example.invalid', '')]:
            with self.subTest(email=email, phone=phone):
                key = token(self.staff.get('/add'))
                response = self.staff.post('/add', data=dict(self.form, form_token=key,
                    contact_email=email, contact_phone_number=phone))
                self.assertEqual(response.status_code, 302)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0], 7)
        self.assertEqual(self.mail.call_count, 2)  # Only the request with an email.

    def test_age_boundaries_for_staff_and_requester(self):
        link, _ = self.invite()
        client, requester_fields = self.requester(link)
        for browser, url, fields in [(self.staff, '/add', dict(self.form,
                form_token=token(self.staff.get('/add')))), (client, link, requester_fields)]:
            for age in ['0', '81', '-1', '1.5']:
                with self.subTest(url=url, age=age):
                    response = browser.post(url, data={**fields, 'age[]': [age, '']})
                    self.assertEqual(response.status_code, 400)
                    self.assertIn(b'whole-number age from 1 to 80', response.data)
            self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0],
                             1 if url == '/add' else 3)
            response = browser.post(url, data={**fields, 'age[]': ['1', '80']})
            self.assertIn(response.status_code, (302, 303))
        self.assertEqual(self.conn.execute(
            'SELECT age FROM recipients WHERE recipient_name IN (?, ?) ORDER BY recipient_id',
            ('First', 'Second')).fetchall(), [(1,), (80,), (1,), (80,)])

    def test_formatted_phone_saves_only_digits_and_age_can_be_blank(self):
        for phone in ['(479) 555-0123', '+1 (479) 555-0123']:
            with self.subTest(phone=phone):
                response = self.staff.post('/add', data={**self.form,
                    'form_token': token(self.staff.get('/add')),
                    'contact_phone_number': phone, 'age[]': ['', '']})
                self.assertEqual(response.status_code, 302)
        stored = self.conn.execute(
            'SELECT contact_phone_number FROM contacts WHERE contact_name=?',
            ('Test Contact',)).fetchall()
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0][0], 4795550123)
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) FROM recipients WHERE recipient_name IN ('First', 'Second') AND age IS NULL"
        ).fetchone()[0], 4)

    def test_same_name_without_contact_channels_does_not_merge_people(self):
        for _ in range(2):
            self.staff.post('/add', data=dict(self.form, form_token=token(self.staff.get('/add')),
                                             contact_email='', contact_phone_number=''))
        ids = self.conn.execute('SELECT DISTINCT contact_id FROM orders WHERE order_id>1').fetchall()
        self.assertEqual(len(ids), 2)

    def test_requester_form_accepts_missing_phone_and_email(self):
        link, _ = self.invite()
        client, fields = self.requester(link)
        response = client.post(link, data=dict(fields, contact_email='', contact_phone_number=''))
        self.assertEqual(response.status_code, 303)
        self.assertEqual(client.get(response.headers['Location']).status_code, 200)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0], 3)
        self.mail.assert_not_called()

    def test_optional_channels_have_no_html_required_attribute(self):
        page = self.staff.get('/add').data
        for field in ['contact_email', 'contact_phone_number']:
            element = re.search(rb'<input id="' + field.encode() + rb'"[^>]*>', page).group()
            self.assertNotIn(b'required', element)

    def test_staff_tokens_reject_missing_tampered_and_other_browser(self):
        key = token(self.staff.get('/add'))
        self.assertEqual(self.staff.post('/add', data=self.form).status_code, 400)
        self.assertEqual(self.staff.post('/add', data=dict(self.form, form_token=key+'bad')).status_code, 400)
        other = app.test_client()
        with other.session_transaction() as session:
            session['username'] = 'tester'
        self.assertEqual(other.post('/add', data=dict(self.form, form_token=key)).status_code, 400)

    def test_invite_can_be_opened_repeatedly_and_is_private(self):
        link, _ = self.invite()
        client, fields = self.requester(link)
        for browser in (client, self.staff):
            response = browser.get(link)
            self.assertNotIn(b'contact-list', response.data)
            self.assertNotIn(b'Welcome,', response.data)
            self.assertNotIn(b'navbar-toggler', response.data)
            self.assertNotIn(b'href="/explorer"', response.data)
            self.assertIn(b'data-staff="false"', response.data)
            self.assertEqual(response.headers['Referrer-Policy'], 'no-referrer')
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertIsNone(self.conn.execute('SELECT used_at FROM request_invites').fetchone()[0])
        self.assertEqual(client.get('/api/search_contacts?q=Test').status_code, 302)
        self.assertEqual(client.get('/request-links').status_code, 302)
        stored = self.conn.execute('SELECT token_hash FROM request_invites').fetchone()[0]
        self.assertNotEqual(stored, link.rsplit('/', 1)[1])

    def test_invite_validation_keeps_link_and_then_saves_all_recipients(self):
        link, _ = self.invite()
        client, fields = self.requester(link)
        response = client.post(link, data=dict(fields, contact_email='bad'))
        self.assertEqual(response.status_code, 400)
        self.assertIsNone(self.conn.execute('SELECT used_at FROM request_invites').fetchone()[0])
        response = client.post(link, data=fields)
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.location, link)
        self.assertIn(b'Request received', client.get(link).data)
        self.assertIsNotNone(self.conn.execute('SELECT used_at FROM request_invites').fetchone()[0])
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0], 3)
        self.assertEqual(self.conn.execute('SELECT DISTINCT last_updated_by FROM orders WHERE order_id > 1').fetchall(), [('Request link #1',)])
        client.post(link, data=fields)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0], 3)
        self.mail.assert_not_called()

    def test_invite_cannot_override_staff_routing_or_order_date(self):
        link, _ = self.invite()
        client, fields = self.requester(link)
        fields.update(order_type='Pedal Partner', shop_name='Unknown', pedal_partner_name='Untrusted', order_date='1900-01-01')
        self.assertEqual(client.post(link, data=fields).status_code, 303)
        rows = self.conn.execute('SELECT shop_name,order_type,pedal_partner_id,order_date FROM orders WHERE order_id > 1').fetchall()
        self.assertEqual([r[:3] for r in rows], [('B', 'Public', None)] * 2)
        self.assertNotEqual(rows[0][3], '1900-01-01')

    def test_expired_revoked_and_unknown_links_cannot_submit(self):
        link, _ = self.invite()
        client, fields = self.requester(link)
        self.conn.execute('UPDATE request_invites SET expires_at=1'); self.conn.commit()
        self.assertEqual(client.post(link, data=fields).status_code, 410)
        self.assertEqual(client.get('/request/' + 'x' * 43).status_code, 404)
        link, _ = self.invite()
        page = self.staff.get('/request-links')
        revoke_token = re.search(rb'action="/request-links/2/revoke".*?name="form_token" value="([^"]+)"', page.data, re.S).group(1).decode()
        self.assertEqual(self.staff.post('/request-links/2/revoke', data={'form_token': revoke_token}).status_code, 302)
        self.assertEqual(client.get(link).status_code, 410)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0], 1)

    def test_failed_save_does_not_consume_link_or_leave_partial_order(self):
        link, _ = self.invite()
        client, fields = self.requester(link)
        self.conn.executescript("""CREATE TRIGGER fail_second BEFORE INSERT ON recipients
            WHEN NEW.recipient_name='Second' BEGIN SELECT RAISE(ABORT, 'test failure'); END;""")
        with self.assertRaises(sqlite3.IntegrityError):
            client.post(link, data=fields)
        self.assertIsNone(self.conn.execute('SELECT used_at FROM request_invites').fetchone()[0])
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0], 1)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM order_submissions').fetchone()[0], 0)
        self.conn.execute('DROP TRIGGER fail_second'); self.conn.commit()
        self.assertEqual(client.post(link, data=fields).status_code, 303)

    def test_two_browsers_submitting_same_link_create_one_request(self):
        link, _ = self.invite()
        requests = [self.requester(link), self.requester(link)]
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda pair: pair[0].post(link, data=pair[1]).status_code, requests))
        self.assertCountEqual(responses, [303, 200])
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0], 3)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM order_submissions').fetchone()[0], 1)

    def test_invite_issuance_retry_creates_only_one_link(self):
        link, fields = self.invite()
        self.assertEqual(self.staff.post('/request-links', data=fields).status_code, 302)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM request_invites').fetchone()[0], 1)

    def test_wrong_form_token_does_not_consume_invite(self):
        link, _ = self.invite()
        key = token(self.staff.get('/add'))
        self.assertEqual(self.staff.post(link, data=dict(self.form, form_token=key)).status_code, 400)
        self.assertIsNone(self.conn.execute('SELECT used_at FROM request_invites').fetchone()[0])

    def test_title_and_form_labels_render_cleanly(self):
        response = self.staff.get('/')
        self.assertIn(b'<title>Order Desk - PIF Portal</title>', response.data)
        self.assertEqual(response.data.count(b'src="/static/js/order_actions.js"'), 1)
        response = self.staff.get('/add')
        self.assertIn(b'for="recipient-0-recipient_name"', response.data)
        self.assertIn(b'for="contact_email"', response.data)
        self.assertIn(b'<button type="button" class="bike-card', response.data)
