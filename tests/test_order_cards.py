"""Exercise the actual forms rendered for Order Desk, using disposable orders."""
from html.parser import HTMLParser
import re
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from test_order_workflow import DatabaseTestCase, app


class CardForms(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.forms = []
        self.current = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'form':
            self.current = {'action': attrs['action'], 'fields': {}}
        elif tag == 'input' and self.current is not None and attrs.get('name'):
            self.current['fields'][attrs['name']] = attrs.get('value', '')

    def handle_endtag(self, tag):
        if tag == 'form' and self.current is not None:
            self.forms.append(self.current)
            self.current = None


class OrderCardTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        config = patch.dict(app.config, TESTING=True, SECRET_KEY='card-test', DB_PATH=str(self.path))
        config.start()
        self.addCleanup(config.stop)
        mail = patch('app.send_email')
        mail.start()
        self.addCleanup(mail.stop)
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session['username'] = 'card-tester'

    def card_page(self, status):
        response = self.client.get('/', query_string={'status': status, 'q': '#1', 'order_type': 'all'})
        self.assertEqual(response.status_code, 200)
        section = re.search(
            rf'id="{status}" aria-labelledby="tab-{status}">(.*?)</section>',
            response.get_data(as_text=True), re.S).group(1)
        return section, CardForms(section).forms

    def action(self, status, next_status):
        _, forms = self.card_page(status)
        form = next(form for form in forms if form['fields'].get('new_status') == next_status)
        self.assertEqual(form['action'], '/update_status/1')
        response = self.client.post(form['action'], data=form['fields'])
        self.assertEqual(response.status_code, 302)
        self.assertEqual(parse_qs(urlsplit(response.location).query),
                         {'q': ['#1'], 'order_type': ['all'], 'status': [status], 'page': ['1']})
        self.assertEqual(self.conn.execute('SELECT order_status FROM orders WHERE order_id=1').fetchone()[0], next_status)

    def test_card_contact_cancel_restore_and_pickup_forms(self):
        self.action('open', 'Cancelled')
        self.action('cancelled', 'Open')
        self.action('open', 'Contacted')
        self.action('contacted', 'Cancelled')
        self.action('cancelled', 'Open')
        self.action('open', 'Contacted')
        html, forms = self.card_page('contacted')
        self.assertIn('Pickup date</label>', html)
        self.assertIn('Bike tag</label>', html)
        pickup = next(form for form in forms if form['action'] == '/fulfill/1')
        response = self.client.post(pickup['action'], data={**pickup['fields'],
            'date_picked_up': '2026-10-08', 'bike_tag': '987654'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.conn.execute('SELECT order_status,bike_tag FROM orders WHERE order_id=1').fetchone(),
                         ('Completed', 987654))
        html, forms = self.card_page('completed')
        self.assertIn('987654', html)
        self.assertIn('10/08/2026', html)
        self.assertEqual(forms, [])

    def test_card_all_is_read_only_and_notes_are_escaped(self):
        self.conn.execute('UPDATE orders SET notes=? WHERE order_id=1', ('<script>private note</script>',))
        self.conn.commit()
        html, forms = self.card_page('all')
        self.assertEqual(forms, [])
        self.assertIn('&lt;script&gt;private note&lt;/script&gt;', html)
        self.assertIn('View bikes', html)
        self.assertIn('Has notes', html)
        # Search should not expand every order/bike into a tall page.
        self.assertNotRegex(html, r'<details[^>]*\sopen(?:\s|>)')
