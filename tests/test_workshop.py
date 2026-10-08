import json
import re
import sqlite3
from unittest.mock import patch

from flask import template_rendered
from test_order_workflow import DatabaseTestCase, app
from admin_tools import initialize


class WorkshopTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.conn.execute('CREATE TABLE users (username TEXT)')
        self.conn.execute("INSERT INTO users VALUES ('tester')")
        self.conn.commit()
        initialize(self.path, 'tester', 'Enable workshop testing')
        self.conn.execute("INSERT INTO volunteers (volunteer_id,volunteer_name) VALUES (10,'Alex'),(20,'Jordan')")
        self.conn.commit()
        config = patch.dict(app.config, TESTING=True, SECRET_KEY='test-only', DB_PATH=str(self.path))
        config.start()
        self.addCleanup(config.stop)
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session['username'] = 'tester'

    def token(self, route):
        response = self.client.get(route)
        self.assertEqual(response.status_code, 200)
        return re.search(r'name="form_token" value="([^"]+)"', response.get_data(as_text=True)).group(1)

    def bike_form(self, **changes):
        values = {'form_token': self.token('/inventory/new'), 'bike_tag': '00123', 'shop_name': 'B',
                  'recorded_at': '2025-06-01T10:30', 'make': 'Trek', 'model': 'Example', 'colour': 'Blue',
                  'wheel_size': '26 inch', 'bike_type': 'Mountain', 'volunteer_ids': ['10', '20']}
        values.update(changes)
        return values

    def hours_form(self, **changes):
        values = {'form_token': self.token('/volunteer-hours/new'), 'volunteer_id': '10',
                  'work_date': '2025-06-01', 'hours': '1.5', 'shop_name': 'B', 'activity': 'Repairs', 'notes': 'Workshop'}
        values.update(changes)
        return values

    def get_context(self, route):
        results = []
        def capture(sender, template, context, **kwargs):
            results.append(context)
        with template_rendered.connected_to(capture, app):
            response = self.client.get(route)
        self.assertEqual(response.status_code, 200)
        return results[-1]

    def test_inventory_multiple_volunteers_and_retry_are_one_atomic_save(self):
        before = self.snapshot()
        form = self.bike_form()
        for _ in range(2):
            self.assertEqual(self.client.post('/inventory/new', data=form).status_code, 303)
        self.assertEqual(self.conn.execute('SELECT bike_tag,make,model,colour FROM bike_inventory').fetchall(),
                         [('123', 'Trek', 'Example', 'Blue')])
        self.assertEqual(self.conn.execute('SELECT volunteer_id FROM bike_contributions ORDER BY volunteer_id').fetchall(), [(10,), (20,)])
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM volunteer_hours').fetchone()[0], 0)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.client.get('/inventory/1').status_code, 200)

    def test_duplicate_tag_refuses_overwrite_and_add_contribution_preserves_details(self):
        self.client.post('/inventory/new', data=self.bike_form())
        response = self.client.post('/inventory/new', data=self.bike_form(bike_tag='123', make='Changed'))
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'Open tag 123', response.data)
        form = {'form_token': self.token('/inventory/1'), 'volunteer_ids': ['10']}
        for _ in range(2):
            self.assertEqual(self.client.post('/inventory/1', data=form).status_code, 303)
        self.assertEqual(self.conn.execute('SELECT make FROM bike_inventory').fetchone()[0], 'Trek')
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM bike_contributions').fetchone()[0], 3)
        self.assertEqual(len(self.get_context('/inventory?q=000123')['rows']), 1)

    def test_repeated_ids_with_different_spelling_do_not_duplicate_contributor(self):
        form = self.bike_form(volunteer_ids=['10', '010', '10'])
        self.assertEqual(self.client.post('/inventory/new', data=form).status_code, 303)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM bike_contributions').fetchone()[0], 1)

    def test_invalid_bike_fields_do_not_save_partial_records(self):
        for changes in [{'bike_tag': ''}, {'bike_tag': '000'}, {'bike_tag': 'TEST2'}, {'shop_name': 'missing'},
                        {'volunteer_ids': ['999']}, {'volunteer_ids': []}, {'recorded_at': '2999-01-01T12:00'}]:
            with self.subTest(changes=changes):
                response = self.client.post('/inventory/new', data=self.bike_form(**changes))
                self.assertEqual(response.status_code, 400)
                self.assertIn(b'Trek', response.data)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM bike_inventory').fetchone()[0], 0)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM bike_contributions').fetchone()[0], 0)

    def test_volunteer_profiles_are_explicit_not_merged_by_name(self):
        form = {'form_token': self.token('/volunteers'), 'volunteer_name': 'Alex'}
        response = self.client.post('/volunteers', data=form)
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'different person', response.data)
        form['different_person'] = 'yes'
        for _ in range(2):
            self.assertEqual(self.client.post('/volunteers', data=form).status_code, 303)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM volunteers WHERE volunteer_name='Alex'").fetchone()[0], 2)
        choices = self.client.get('/api/workshop/volunteers').get_json()
        self.assertEqual(len(choices), 3)
        self.assertEqual(set(choices[0]), {'volunteer_name', 'volunteer_id'})

    def profile_form(self, volunteer_id=10, **changes):
        page=self.client.get(f'/volunteers/{volunteer_id}/edit').get_data(as_text=True)
        fields={field:re.search(f'name="{field}" value="([^"]*)"',page).group(1)
                for field in ('form_token','version')}
        fields.update(joined_on='2025-06-01',is_active='0')
        fields.update(changes)
        return fields

    def test_volunteer_date_status_create_update_retry_and_history_preserved(self):
        form={'form_token':self.token('/volunteers'),'volunteer_name':'New volunteer',
              'joined_on':'2025-04-03','is_active':'0'}
        self.assertEqual(self.client.post('/volunteers',data=form).status_code,303)
        self.assertEqual(self.conn.execute("SELECT joined_on,is_active FROM volunteers WHERE volunteer_name='New volunteer'").fetchone(),('2025-04-03',0))
        self.client.post('/volunteer-hours/new',data=self.hours_form())
        self.client.post('/inventory/new',data=self.bike_form())
        before={t:self.conn.execute(f'SELECT * FROM {t}').fetchall() for t in ('volunteer_hours','bike_contributions')}
        values=self.profile_form()
        for _ in range(2): self.assertEqual(self.client.post('/volunteers/10/edit',data=values).status_code,303)
        self.assertEqual(self.conn.execute('SELECT joined_on,is_active FROM volunteers WHERE volunteer_id=10').fetchone(),('2025-06-01',0))
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM admin_changes WHERE entity='volunteers' AND entity_id='10'").fetchone()[0],1)
        self.assertEqual(before,{t:self.conn.execute(f'SELECT * FROM {t}').fetchall() for t in before})
        self.assertIn(b'Inactive',self.client.get('/volunteers?q=10').data)
        self.assertEqual(self.client.post('/volunteers/10/edit',data=self.profile_form(joined_on='',is_active='1')).status_code,303)
        self.assertEqual(self.conn.execute('SELECT joined_on,is_active FROM volunteers WHERE volunteer_id=10').fetchone(),(None,1))

    def test_profile_validation_authentication_and_stale_edit(self):
        anonymous=app.test_client()
        self.assertEqual(anonymous.post('/volunteers/10/edit',data={}).status_code,302)
        self.assertEqual(self.client.post('/volunteers/10/edit',data={}).status_code,400)
        for changes in ({'joined_on':'2025-02-30'},{'joined_on':'2999-01-01'},{'is_active':'yes'}):
            self.assertEqual(self.client.post('/volunteers/10/edit',data=self.profile_form(**changes)).status_code,400)
        stale=self.profile_form()
        self.conn.execute("UPDATE volunteers SET joined_on='2024-01-01' WHERE volunteer_id=10")
        self.conn.commit()
        response=self.client.post('/volunteers/10/edit',data=stale)
        self.assertEqual(response.status_code,409)
        self.assertIn(b'Reload current profile',response.data)
        self.assertEqual(self.conn.execute('SELECT joined_on,is_active FROM volunteers WHERE volunteer_id=10').fetchone(),('2024-01-01',1))

    def test_profile_audit_failure_rolls_back_metadata(self):
        values=self.profile_form()
        with patch('workshop._audit',side_effect=sqlite3.IntegrityError('audit failed')):
            with self.assertRaises(sqlite3.IntegrityError): self.client.post('/volunteers/10/edit',data=values)
        self.assertEqual(self.conn.execute('SELECT joined_on,is_active FROM volunteers WHERE volunteer_id=10').fetchone(),(None,1))

    def test_manual_hours_are_independent_and_retry_does_not_duplicate(self):
        before = self.snapshot()
        form = self.hours_form(shop_name='', volunteer_id='10.0')
        for _ in range(2):
            self.assertEqual(self.client.post('/volunteer-hours/new', data=form).status_code, 303)
        self.assertEqual(self.conn.execute('SELECT volunteer_id,minutes,shop_name FROM volunteer_hours').fetchall(), [(10,90,None)])
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM bike_inventory').fetchone()[0], 0)
        self.assertEqual(self.snapshot(), before)
        context = self.get_context('/volunteer-hours?volunteer_id=10')
        self.assertEqual(context['total_minutes'], 90)

    def test_invalid_durations_people_dates_and_daily_total_are_rejected(self):
        for changes in [{'hours':'NaN'}, {'hours':'Infinity'}, {'hours':'1e999999'}, {'hours':'0'}, {'hours':'-1'}, {'hours':'25'},
                        {'hours':'1.001'}, {'work_date':'2025-02-30'}, {'work_date':'2999-01-01'},
                        {'volunteer_id':'999'}, {'shop_name':'missing'}]:
            with self.subTest(changes=changes):
                self.assertEqual(self.client.post('/volunteer-hours/new', data=self.hours_form(**changes)).status_code,400)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM volunteer_hours').fetchone()[0],0)
        self.assertEqual(self.client.post('/volunteer-hours/new', data=self.hours_form(hours='20')).status_code,303)
        self.assertEqual(self.client.post('/volunteer-hours/new', data=self.hours_form(hours='5')).status_code,400)

    def test_edit_and_void_are_versioned_and_audited(self):
        self.client.post('/volunteer-hours/new', data=self.hours_form())
        token = self.token('/volunteer-hours/1/edit')
        stale = self.token('/volunteer-hours/1/edit')
        values = self.hours_form(form_token=token, hours='2', reason='Correct duration', version='1')
        self.assertEqual(self.client.post('/volunteer-hours/1/edit',data=values).status_code,303)
        self.assertEqual(self.client.post('/volunteer-hours/1/edit',data=values).status_code,303)
        values['form_token']=stale
        self.assertEqual(self.client.post('/volunteer-hours/1/edit',data=values).status_code,409)
        context = self.get_context('/volunteer-hours/1/edit')
        form = {'form_token': context['void_token'], 'version':'2', 'reason':'Duplicate handwritten log'}
        self.assertEqual(self.client.post('/volunteer-hours/1/void',data=form).status_code,303)
        self.assertEqual(self.get_context('/volunteer-hours')['total_minutes'],0)
        audit = self.conn.execute("SELECT before_json,after_json FROM admin_changes WHERE entity='volunteer_hours' ORDER BY change_id").fetchall()
        self.assertEqual(len(audit),3)
        self.assertEqual(json.loads(audit[1][0])['minutes'],90)
        self.assertEqual(json.loads(audit[1][1])['minutes'],120)
        self.assertIsNotNone(json.loads(audit[2][1])['voided_at'])

    def test_one_minute_time_entry_round_trips_edit(self):
        self.assertEqual(self.client.post('/volunteer-hours/new',data=self.hours_form(hours='0.0166666667')).status_code,303)
        context=self.get_context('/volunteer-hours/1/edit')
        values={**context['values'],'form_token':context['form_token'],'version':'1','reason':'Keep the entered minute'}
        self.assertEqual(self.client.post('/volunteer-hours/1/edit',data=values).status_code,303)
        self.assertEqual(self.conn.execute('SELECT minutes FROM volunteer_hours').fetchone()[0],1)

    def test_totals_cover_all_pages_and_filters_apply_before_totals(self):
        for day in range(1,29):
            self.conn.execute('''INSERT INTO volunteer_hours(volunteer_id,work_date,minutes,shop_name,created_at,created_by,updated_at,updated_by)
                VALUES(10,?,90,'B','today','tester','today','tester')''',(f'2025-02-{day:02d}',))
        self.conn.commit()
        context=self.get_context('/volunteer-hours')
        self.assertEqual(len(context['rows']),25)
        self.assertEqual(context['pagination']['pages'],2)
        self.assertEqual(context['total_minutes'],28*90)
        context=self.get_context('/volunteer-hours?from_date=2025-02-10&to_date=2025-02-11')
        self.assertEqual(context['total_minutes'],180)
        self.assertEqual(self.get_context('/volunteer-hours?volunteer_id=20')['total_minutes'],0)
        self.assertEqual(self.client.get('/volunteer-hours?from_date=bad').status_code,400)

    def test_audit_failure_rolls_back_bike_and_contributors(self):
        form=self.bike_form()
        with patch('workshop._audit',side_effect=sqlite3.IntegrityError('audit failed')):
            with self.assertRaises(sqlite3.IntegrityError):
                self.client.post('/inventory/new',data=form)
        for table in ('bike_inventory','bike_contributions','workshop_submissions'):
            self.assertEqual(self.conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0],0)

    def test_auth_and_tokens_protect_all_writes(self):
        self.assertEqual(self.client.post('/inventory/new',data={'bike_tag':'77'}).status_code,400)
        self.assertEqual(self.client.post('/volunteer-hours/new',data={'hours':'1'}).status_code,400)
        with self.client.session_transaction() as session:
            session.clear()
        for route in ('/inventory','/inventory/new','/inventory/1','/volunteers','/volunteer-hours',
                      '/volunteer-hours/new','/api/workshop/volunteers'):
            self.assertEqual(self.client.get(route).status_code,302)

    def test_get_does_not_create_missing_schema_and_cli_upgrade_is_additive(self):
        self.conn.execute('DROP TABLE volunteer_hours')
        self.conn.execute('DROP TABLE workshop_submissions')
        self.conn.commit()
        before=self.snapshot()
        self.assertEqual(self.client.get('/inventory').status_code,503)
        self.assertFalse(self.conn.execute("SELECT 1 FROM sqlite_master WHERE name='volunteer_hours'").fetchone())
        self.assertTrue(initialize(self.path,'tester','Upgrade existing inventory')['applied'])
        self.assertEqual(self.snapshot(),before)
        self.assertFalse(initialize(self.path,'tester','Repeat')['applied'])

    def test_forms_escape_text_and_keep_refresh_controls_with_no_people(self):
        self.conn.execute('DELETE FROM volunteers')
        self.conn.commit()
        html=self.client.get('/inventory/new').get_data(as_text=True)
        self.assertIn('volunteer-choices',html)
        self.assertIn('data-refresh-volunteers',html)
        form={'form_token':self.token('/volunteers'),'volunteer_name':'<script>alert(1)</script>'}
        self.client.post('/volunteers',data=form)
        html=self.client.get('/volunteers').get_data(as_text=True)
        self.assertIn('&lt;script&gt;',html)
        self.assertNotIn('<script>alert(1)</script>',html)
