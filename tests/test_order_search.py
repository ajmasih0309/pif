from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from flask import render_template

from test_order_workflow import DatabaseTestCase, app
from utils import fetch_all_orders
from order_search import search_orders


class OrderSearchTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.conn.executescript('''
            INSERT INTO shops VALUES ('R', 'Rogers');
            INSERT INTO contacts VALUES ('Existing Contact', 4795550198, 'other@example.invalid', 21);
            UPDATE orders SET order_type='Public', order_date='2025-12-31', notes='Blue helmet' WHERE order_id=1;
            INSERT INTO recipients (recipient_id, recipient_name, age, height, bike_style_preference)
                VALUES (41, 'Zoë Rider', 12, 'Tall', 'No Preference'),
                       (42, 'Sam Willow', 10, 'Short', 'Female');
            INSERT INTO orders (order_id, contact_id, recipient_id, pedal_partner_id,
                shop_name, order_date, order_type, order_status, bike_tag, notes,
                last_updated_by, last_updated_date, pickup_date, linked_order_id)
            VALUES (2, 20, 41, 60, 'B', '2026-01-02', 'Pedal Partner', 'Completed', 91234,
                    'Cargo basket requested', 'Morgan', '2026-02-03 09:15:00', '2026-02-03', 999),
                   (3, 20, 42, 60, 'B', '2026-01-02', 'Specialty', 'Contacted', NULL,
                    'Adaptive tricycle', NULL, NULL, NULL, NULL),
                   (4, 20, 42, NULL, 'B', '2026-01-02', 'Speciality', 'Open', NULL,
                    'Adaptive seat', NULL, NULL, NULL, NULL),
                   (5, 20, 42, NULL, 'R', '2026-01-02', 'Public', 'Cancelled', NULL,
                    '100% ready', NULL, NULL, NULL, NULL),
                   (6, 21, 42, NULL, 'B', '2026-01-02', 'Public', 'Open', NULL,
                    NULL, NULL, NULL, NULL, NULL),
                   (7, 20, 42, NULL, 'B', '2026-01-02', 'Public', 'Open', NULL,
                    NULL, NULL, NULL, NULL, NULL);
        ''')
        self.settings = patch.dict(app.config, TESTING=True, SECRET_KEY='test-search', DB_PATH=str(self.path))
        self.settings.start()
        self.addCleanup(self.settings.stop)
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session['username'] = 'search-tester'

    def search(self, query='', order_type='all'):
        with app.app_context():
            return search_orders(fetch_all_orders(), query, order_type)

    def ids(self, query='', order_type='all'):
        return {item['order_id'] for item in self.search(query, order_type)[0]}

    def page(self, route='/', **params):
        with patch('app.render_template', wraps=render_template) as rendered:
            response = self.client.get(route, query_string=params)
        self.assertEqual(response.status_code, 200)
        return response, rendered.call_args.kwargs

    def test_searches_all_statuses_and_raw_and_display_fields(self):
        for query, expected in [
            ('ZOE', {2}), ('rider basket', {2}), ('91234', {2}), ('Morgan', {2}),
            ('999', {2}), ('2026-02-03', {2}), ('02/03/2026', {2}),
            ('4795550198', {6}), ('(479) 555-0198', {6}), ('other@example.invalid', {6}),
            ('Rogers', {5}), ('cancelled ready', {5}), ('adaptive', {3, 4}),
            ('#2', {2}), ('#999', set()), ('%', {5}), ('nothing matches', set()),
        ]:
            with self.subTest(query=query):
                self.assertEqual(self.ids(query), expected)

    def test_types_use_order_type_and_combine_speciality_spellings(self):
        self.assertEqual(self.ids(order_type='public'), {1, 5, 6, 7})
        self.assertEqual(self.ids(order_type='pedal-partner'), {2})
        self.assertEqual(self.ids(order_type='speciality'), {3, 4})
        self.assertEqual(self.ids('specialty'), {3, 4})
        self.assertEqual(self.ids('speciality'), {3, 4})
        self.assertEqual(self.ids('adaptive', 'public'), set())
        self.assertEqual(self.ids('adaptive', 'speciality'), {3, 4})
        self.assertEqual(self.ids(order_type='unexpected'), set(range(1, 8)))

    def test_counts_reflect_search_before_type_filter(self):
        items, context = self.search('adaptive', 'public')
        self.assertEqual(items, [])
        self.assertEqual(context['type_counts'], {'all': 2, 'public': 0, 'pedal-partner': 0, 'speciality': 2})
        self.assertEqual(context['total_count'], 7)
        self.assertEqual(context['result_count'], 0)

    def test_both_pages_use_identical_search_and_type_filters(self):
        for params in ({'q': 'adaptive', 'order_type': 'speciality'}, {'q': '#2'}, {'order_type': 'public'}):
            _, desk = self.page(**params)
            _, explorer = self.page('/explorer', **params)
            ids = {r['order_id'] for g in desk['all_orders'] for r in g['recipients']}
            self.assertEqual(ids, {item['order_id'] for item in explorer['items']})
            self.assertEqual(desk['type_counts'], explorer['type_counts'])
            self.assertEqual(desk['active_tab'], 'all')

    def test_groups_do_not_mix_contacts_shops_or_types_and_dates_sort_across_years(self):
        _, context = self.page(status='all')
        self.assertEqual(len(context['all_orders']), 6)
        for group in context['all_orders']:
            self.assertEqual({r['order_type'] for r in group['recipients']}, {group['order_type']})
            self.assertEqual(len({r['contact_id'] for r in group['recipients']}), 1)
            self.assertEqual(len({r['shop_name'] for r in group['recipients']}), 1)
        self.assertEqual(context['all_orders'][-1]['order_date_iso'], '2025-12-31')
        _, context = self.page(status='open')
        self.assertEqual(context['open_orders'][0]['order_date_iso'], '2025-12-31')

    def test_only_active_tab_is_rendered_with_global_counts(self):
        response, context = self.page(status='contacted')
        self.assertEqual(context['all_orders'], [])
        self.assertEqual(context['completed_orders'], [])
        self.assertEqual(context['status_counts'], {'open': 4, 'contacted': 1, 'completed': 1, 'cancelled': 1, 'all': 7})
        self.assertEqual(response.data.count(b'aria-label="View order '), 1)
        self.assertNotIn(b'Cargo basket requested', response.data)

    def test_pagination_keeps_groups_together_and_search_covers_later_pages(self):
        for i in range(30):
            date = f'2026-03-{i + 1:02d}'
            for _ in range(2):
                self.conn.execute('''INSERT INTO orders (contact_id, recipient_id, shop_name,
                    order_date, order_type, order_status, notes)
                    VALUES (20, 42, 'B', ?, 'Public', 'Open', ?)''', (date, 'findlaterpage' if i == 29 else f'pagination-note-{i}'))
        self.conn.commit()
        _, first = self.page(status='open', order_type='public')
        _, second = self.page(status='open', order_type='public', page=2)
        self.assertEqual(first['pagination']['pages'], 2)
        self.assertEqual(len(first['open_orders']), 25)
        ids_first = {r['order_id'] for g in first['open_orders'] for r in g['recipients']}
        ids_second = {r['order_id'] for g in second['open_orders'] for r in g['recipients']}
        self.assertFalse(ids_first & ids_second)
        self.assertEqual(len(ids_first | ids_second), 63)
        self.assertEqual(first['status_counts']['open'], 63)
        self.assertEqual(second['status_counts']['open'], 63)
        _, matched = self.page(q='findlaterpage', order_type='public')
        self.assertEqual(matched['result_count'], 2)
        self.assertEqual(len(matched['all_orders']), 1)
        _, clamped = self.page(status='open', page=9999)
        self.assertEqual(clamped['pagination']['page'], clamped['pagination']['pages'])

    def test_action_preserves_page(self):
        response = self.client.post('/update_status/1', data={
            'new_status': 'Cancelled', 'return_status': 'open', 'return_page': '2',
        })
        self.assertEqual(parse_qs(urlsplit(response.location).query), {'status': ['open'], 'page': ['2']})

    def test_matching_group_has_cards_and_links_to_exact_record(self):
        response, context = self.page(q='#2')
        self.assertEqual(context['active_tab'], 'all')
        self.assertIn(b'class="desk-order-list" data-order-cards', response.data)
        self.assertIn(b'View bikes', response.data)
        self.assertNotIn(b'class="table-responsive', response.data)
        self.assertIn(b'Cargo basket requested', response.data)
        self.assertIn(b'/explorer?q=%232', response.data)
        response, _ = self.page('/explorer', q='#2')
        self.assertIn(b'/?q=%232&amp;status=completed', response.data)
        self.assertIn(b'Morgan', response.data)

    def test_empty_results_and_html_escaping(self):
        for route in ('/', '/explorer'):
            response, context = self.page(route, q='<script>alert(1)</script>')
            self.assertEqual(context['result_count'], 0)
            self.assertIn(b'No matching orders.', response.data)
            self.assertNotIn(b'<script>alert(1)</script>', response.data)
            self.assertIn(b'&lt;script&gt;', response.data)

    def test_active_tab_and_reset_defaults(self):
        _, context = self.page(q='adaptive', status='contacted')
        self.assertEqual(context['active_tab'], 'contacted')
        _, context = self.page(q='adaptive', status='bad')
        self.assertEqual(context['active_tab'], 'all')
        _, context = self.page()
        self.assertEqual(context['active_tab'], 'open')
        self.assertEqual(context['result_count'], 7)
        self.assertFalse(context['filters_active'])

    def test_order_action_preserves_query_type_and_tab(self):
        with patch('app.send_email', return_value=True):
            response = self.client.post('/update_status/1', data={
                'new_status': 'Contacted', 'return_q': '#1',
                'return_order_type': 'public', 'return_status': 'open',
            })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(urlsplit(response.location).path, '/')
        self.assertEqual(parse_qs(urlsplit(response.location).query),
                         {'q': ['#1'], 'order_type': ['public'], 'status': ['open']})

    def test_search_is_read_only(self):
        before = self.snapshot()
        self.page(q='adaptive', order_type='speciality')
        self.page('/explorer', q='4795550198')
        self.assertEqual(self.snapshot(), before)
