from datetime import date
import sqlite3
from unittest.mock import patch

from admin_tools import initialize
from test_order_workflow import DatabaseTestCase, app
from volunteer_impact import yearly_impact


class VolunteerImpactTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.conn.execute('CREATE TABLE users (username TEXT)')
        self.conn.execute("INSERT INTO users VALUES ('tester')")
        self.conn.commit()
        initialize(self.path, 'tester', 'Test volunteer summary')
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("INSERT INTO volunteers(volunteer_id,volunteer_name) VALUES (10,'Same Name'),(20,'Same Name')")
        self.conn.execute("INSERT INTO shops VALUES ('R','Rogers')")
        self.conn.execute("INSERT INTO bike_inventory(inventory_id,bike_tag,shop_name,created_at) VALUES (1,'123','B','2025-01-01'),(2,'456','R','2025-01-01')")
        self.conn.commit()
        config = patch.dict(app.config, TESTING=True, SECRET_KEY='test-only', DB_PATH=str(self.path))
        config.start()
        self.addCleanup(config.stop)

    def hours(self, day, minutes, volunteer=10, shop='B', voided=None):
        self.conn.execute('''INSERT INTO volunteer_hours(volunteer_id,work_date,minutes,shop_name,
            created_at,created_by,updated_at,updated_by,voided_at) VALUES (?,?,?,?,?,?,?,?,?)''',
            (volunteer,day,minutes,shop,'2026-10-05','tester','2026-10-05','tester',voided))

    def bike(self, day, inventory=1, volunteer=10):
        self.conn.execute('INSERT INTO bike_contributions(inventory_id,volunteer_id,recorded_at) VALUES (?,?,?)',
                          (inventory,volunteer,day))

    def test_distinct_bikes_exact_minutes_all_shops_and_union_of_active_weeks(self):
        self.hours('2026-01-05',120)
        self.hours('2026-01-06',17,shop='R')
        self.hours('2026-01-05',400,volunteer=20)
        self.hours('2026-01-12',300,voided='2026-02-01')
        self.hours('2025-12-31',500)
        self.hours('2026-12-31',500)
        self.bike('2026-01-06T18:00:00+00:00')
        self.bike('2026-01-07T18:00:00+00:00')
        self.bike('2026-01-19T18:00:00+00:00',inventory=2)
        stats=yearly_impact(self.conn,10,date(2026,10,5))
        self.assertEqual((stats['minutes'],stats['bikes'],stats['active_weeks']),(137,2,2))
        self.assertEqual(sum(w['state']=='active' for w in stats['weeks']),2)

    def test_chicago_boundary_dates_undated_and_unlinked_work(self):
        self.bike('2026-01-01T05:59:59+00:00')  # Still Dec 31 in Chicago.
        self.bike('2026-01-01T06:00:00+00:00',inventory=2)
        self.bike('2026-01-01T12:00:00',volunteer=None)
        self.bike(None)
        self.bike('not-a-date')
        self.bike('2027-01-02')
        stats=yearly_impact(self.conn,10,date(2026,1,1))
        self.assertEqual((stats['minutes'],stats['bikes'],stats['active_weeks']),(0,1,1))
        self.assertEqual(stats['weeks'][0]['state'],'active')
        self.assertTrue(all(w['state']=='future' for w in stats['weeks'][1:]))

    def test_year_end_and_empty_state_cover_every_calendar_week(self):
        stats=yearly_impact(self.conn,20,date(2012,12,31))
        self.assertEqual(len(stats['weeks']),54)  # Leap year starting Sunday.
        self.assertEqual((stats['minutes'],stats['bikes'],stats['active_weeks']),(0,0,0))
        self.assertTrue(all(w['state']=='empty' for w in stats['weeks']))

    def test_staff_preview_requires_authentication_and_public_endpoint_requires_token(self):
        self.conn.commit()
        client=app.test_client()
        self.assertEqual(client.get('/volunteers/10/impact').status_code,302)
        self.assertEqual(client.post('/volunteer/impact',data={'volunteer_id':'10'}).status_code,400)
        with client.session_transaction() as session: session['username']='tester'
        response=client.get('/volunteers/10/impact')
        self.assertEqual(response.status_code,200)
        self.assertIn(b'Your year so far',response.data)
        self.assertEqual(client.get('/volunteers/999/impact').status_code,404)
