from datetime import datetime
from unittest.mock import patch

from flask import template_rendered

from test_order_workflow import DatabaseTestCase, app


class DashboardTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        config = patch.dict(app.config, TESTING=True, SECRET_KEY='test-only', DB_PATH=str(self.path))
        config.start()
        self.addCleanup(config.stop)
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session['username'] = 'tester'

    def add_order(self, status='Completed', pickup='2026-02-10', shop='B', recipient=40):
        self.conn.execute('''
            INSERT INTO orders (order_status, order_date, pickup_date, shop_name, recipient_id)
            VALUES (?, '2025-12-01', ?, ?, ?)
        ''', (status, pickup, shop, recipient))
        self.conn.commit()

    def dashboard(self, query=None):
        contexts = []

        def capture(sender, template, context, **extra):
            if template.name == 'dashboard.html':
                contexts.append(context)

        with template_rendered.connected_to(capture, app):
            response = self.client.get('/dashboard', query_string=query)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(contexts), 1)
        return contexts[0], response.get_data(as_text=True)

    def test_counts_completed_order_lines_once_by_pickup_date(self):
        self.add_order()
        self.add_order(recipient=None)
        self.add_order(recipient=999)
        for status in ('Open', 'Contacted', 'Cancelled'):
            self.add_order(status=status)
        for pickup in (None, '', 'not-a-date'):
            self.add_order(pickup=pickup)
        # Legacy duplicate person IDs must not inflate the number of bikes.
        self.conn.execute("INSERT INTO recipients (recipient_id, recipient_name) VALUES (40, 'Duplicate')")
        self.conn.commit()
        before = self.snapshot()
        context, html = self.dashboard({'year': '2026', 'shop': 'B', 'month': '2'})
        self.assertEqual(context['monthly_counts'], [0, 3] + [0] * 10)
        self.assertEqual(context['this_year_total'], 3)
        self.assertEqual(context['last_year_total'], 0)
        self.assertIn('Completed bikes by pickup date', html)
        self.assertEqual(self.snapshot(), before)

    def test_multi_bike_order_counts_each_completed_bike_separately(self):
        self.add_order(recipient=40)
        self.add_order(recipient=41)
        self.add_order(status='Contacted', recipient=42)
        self.add_order(status='Cancelled', recipient=43)
        self.conn.execute('''UPDATE orders SET contact_id=20, linked_order_id=2
                             WHERE order_id > 1''')
        self.conn.commit()
        context, html = self.dashboard({'year': '2026', 'shop': 'B', 'month': '2'})
        self.assertEqual(context['this_year_total'], 2)
        self.assertEqual(context['monthly_counts'][1], 2)
        self.assertIn('2 Bikes Completed', html)

    def test_comparison_uses_same_shop_and_month_filters(self):
        for year in ('2025', '2026'):
            self.add_order(pickup=f'{year}-02-10')
            self.add_order(pickup=f'{year}-02-10', shop='R')
            self.add_order(pickup=f'{year}-03-10')
        context, _ = self.dashboard([
            ('year', '2026'), ('shop', 'B'), ('shop', 'B'),
            ('month', '2'), ('month', '02'),
        ])
        self.assertEqual(context['this_year_total'], 1)
        self.assertEqual(context['last_year_total'], 1)
        self.assertEqual(context['selected_months'], [2])

    def test_initial_load_uses_current_year_and_includes_historical_years(self):
        self.add_order(pickup='2020-01-10')
        self.add_order(pickup='2032-02-10')
        with patch('app.datetime') as clock:
            clock.now.return_value = datetime(2032, 5, 1)
            context, html = self.dashboard()
        self.assertEqual(context['selected_year'], '2032')
        self.assertEqual(context['this_year_total'], 1)
        self.assertEqual(context['selected_months'], list(range(1, 13)))
        self.assertIn('2020', context['available_years'])
        self.assertIn('value="2032" selected', html)
        self.assertIn('Reset Filters', html)

    def test_invalid_year_and_month_filters_do_not_crash(self):
        self.add_order()
        for year in ('nonsense', '', '0000', '10000', '２０２６', '9' * 5000):
            with self.subTest(year=year), patch('app.datetime') as clock:
                clock.now.return_value = datetime(2026, 5, 1)
                context, html = self.dashboard([
                    ('year', year), ('shop', 'B'), ('month', '02'),
                    ('month', 'garbage'), ('month', '13'), ('month', '-1'),
                ])
                self.assertEqual(context['selected_year'], '2026')
                self.assertEqual(context['selected_months'], [2])
                self.assertEqual(context['this_year_total'], 1)
                self.assertIn('Invalid year', html)
                self.assertIn('Invalid month', html)

    def test_cleared_or_unknown_filters_return_zero(self):
        self.add_order()
        for query in (
            {'year': '2026'},
            {'year': '2026', 'shop': 'B'},
            {'year': '2026', 'month': '2'},
            {'year': '2026', 'shop': 'unknown', 'month': '2'},
            {'year': '2026', 'shop': 'B', 'month': 'invalid'},
        ):
            with self.subTest(query=query):
                context, _ = self.dashboard(query)
                self.assertEqual(context['monthly_counts'], [0] * 12)
                self.assertEqual(context['this_year_total'], 0)
                self.assertEqual(context['last_year_total'], 0)

    def test_dashboard_requires_login(self):
        with self.client.session_transaction() as session:
            session.clear()
        self.assertEqual(self.client.get('/dashboard').status_code, 302)
