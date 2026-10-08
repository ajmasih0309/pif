import re
import json
import sqlite3
from datetime import date
from unittest.mock import patch

from admin_tools import initialize
from test_order_workflow import DatabaseTestCase, app
from volunteer_entry import COOKIE


class VolunteerEntryTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.conn.execute('CREATE TABLE users (username TEXT)')
        self.conn.execute("INSERT INTO users VALUES ('tester')")
        self.conn.commit()
        initialize(self.path, 'tester', 'Enable test entry')
        self.conn.execute("INSERT INTO shops VALUES ('R','Rogers')")
        self.conn.execute("INSERT INTO volunteers(volunteer_id,volunteer_name,volunteer_email,volunteer_phone_number) VALUES (10,'Alex Example','private@example.invalid','4795551234')")
        self.conn.execute("INSERT INTO volunteers(volunteer_id,volunteer_name,volunteer_email,volunteer_phone_number) VALUES (20,'Alex Example',NULL,NULL)")
        self.conn.commit()
        config = patch.dict(app.config, TESTING=True, SECRET_KEY='test-only', DB_PATH=str(self.path))
        config.start()
        self.addCleanup(config.stop)
        clock = patch('volunteer_entry.today', return_value=date(2026,10,5))
        clock.start()
        self.addCleanup(clock.stop)
        self.client = app.test_client()

    def form(self, **changes):
        html = self.client.get('/volunteer/log-hours?shop=B').get_data(as_text=True)
        # Remembered pages contain a separate forget form ahead of the time form.
        html = html.split('id="volunteer-time"', 1)[1]
        token = re.search(r'name="form_token" value="([^"]+)"', html).group(1)
        values = dict(form_token=token, volunteer_id='10', work_date='2026-10-05', hours='2', minutes='17',
                      shop_name='B', activity='', notes='')
        values.update(changes)
        return values

    def post(self, values):
        return self.client.post('/volunteer/log-hours', data=values)

    def bike_form(self, **changes):
        html=self.client.get('/volunteer/finished-bike?shop=B').get_data(as_text=True).split('id="volunteer-bike"',1)[1]
        token=re.search(r'name="form_token" value="([^"]+)"',html).group(1)
        values=dict(form_token=token,volunteer_id='10',bike_tag='00123',shop_name='B',
                    make='Trek',model='Example',colour='Blue',wheel_size='26 inch',bike_type='B')
        values.update(changes)
        return values

    def bike_post(self, values):
        return self.client.post('/volunteer/finished-bike',data=values)

    def test_finished_bike_individual_note_attribution_and_retry(self):
        before=self.snapshot()
        values=self.bike_form(contribution_notes='Adjusted brakes with Alex',remember='yes')
        for _ in range(2): self.assertEqual(self.bike_post(values).status_code,303)
        self.assertEqual(self.conn.execute('SELECT bike_tag,make,wheel_size,bike_type,colour FROM bike_inventory').fetchall(),
                         [('123','Trek','26 inch','B','Blue')])
        self.assertEqual(self.conn.execute('SELECT volunteer_id,notes FROM bike_contributions ORDER BY contribution_id').fetchall(),[(10,'Adjusted brakes with Alex')])
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM volunteer_hours').fetchone()[0],0)
        self.assertEqual(self.snapshot(),before)
        html=self.client.get('/volunteer/bike-thanks').get_data(as_text=True)
        self.assertIn('Your contribution is recorded.',html)
        audit=self.conn.execute("SELECT actor,after_json FROM admin_changes WHERE entity='bike_inventory'").fetchone()
        self.assertEqual(audit[0],'volunteer-self:10')
        self.assertEqual(json.loads(audit[1])['notes'],'Adjusted brakes with Alex')
        self.assertIn('Log my hours',html)
        self.assertIn('Logging time as',self.client.get('/volunteer/log-hours?shop=R').get_data(as_text=True))
        html=self.client.get('/volunteer/finished-bike?shop=R').get_data(as_text=True)
        self.assertIn('Recording as',html)
        self.assertIn('value="R" selected',html)
        self.assertIn('name="bike_tag" value=""',html)
        self.assertEqual(app.test_client().get('/volunteer/bike-thanks').status_code,302)

    def test_existing_tag_requires_bound_confirmation_and_never_overwrites(self):
        self.bike_post(self.bike_form(contribution_notes='First private note'))
        original=self.conn.execute('SELECT * FROM bike_inventory').fetchone()
        values=self.bike_form(bike_tag='000123',make='Changed',shop_name='R',volunteer_id='20',contribution_notes='<script>Second note</script>')
        response=self.bike_post(values)
        self.assertEqual(response.status_code,400)
        self.assertIn(b'already recorded',response.data)
        self.assertNotIn(b'private@example.invalid',response.data)
        self.assertNotIn(b'First private note',response.data)
        token=re.search(r'name="existing_token" value="([^"]+)"',response.get_data(as_text=True)).group(1)
        values.update(confirm_existing='yes',existing_token=token)
        changed_tag={**values,'bike_tag':'999'}
        self.assertEqual(self.bike_post(changed_tag).status_code,400)
        for _ in range(2): self.assertEqual(self.bike_post(values).status_code,303)
        self.assertEqual(self.conn.execute('SELECT * FROM bike_inventory').fetchone(),original)
        self.assertEqual(self.conn.execute('SELECT volunteer_id,notes FROM bike_contributions ORDER BY contribution_id').fetchall(),
                         [(10,'First private note'),(20,'<script>Second note</script>')])
        staff=app.test_client()
        with staff.session_transaction() as session: session['username']='tester'
        detail=staff.get('/inventory/1')
        self.assertEqual(detail.status_code,200)
        self.assertIn(b'First private note',detail.data)
        self.assertIn(b'&lt;script&gt;Second note&lt;/script&gt;',detail.data)
        self.assertNotIn(b'<script>Second note</script>',detail.data)
        self.assertIn(b'original bike details are unchanged',self.client.get('/volunteer/bike-thanks').data)
        self.bike_post(self.bike_form(bike_tag='456'))
        # A confirmation for tag 123 does not authorize adding to tag 456.
        self.assertEqual(self.bike_post(self.bike_form(bike_tag='456',confirm_existing='yes',existing_token=token)).status_code,400)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM bike_contributions WHERE inventory_id=2').fetchone()[0],1)

    def test_tag_check_preserves_note_without_writes(self):
        response=self.bike_post(self.bike_form(action='check_tag',volunteer_id='',contribution_notes='Replaced cables'))
        self.assertEqual(response.status_code,200)
        self.assertIn(b'ready for a new bike record',response.data)
        self.assertIn(b'Replaced cables</textarea>',response.data)
        self.assertNotIn(b'name="helper_ids"',response.data)
        self.assertIn(b'name="make" value="Trek"',response.data)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM bike_inventory').fetchone()[0],0)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM workshop_submissions').fetchone()[0],0)

    def test_invalid_finished_bike_does_not_write_or_create_profiles(self):
        for changes in [{'bike_tag':''},{'bike_tag':'TEST2'},{'bike_tag':'000'}, {'bike_tag':'x'*5000},
                        {'shop_name':'missing'},{'volunteer_id':'999'},{'helper_ids':['999']},
                        {'helper_ids':['20']},{'volunteer_ids':['20']},{'action':'find_helpers'},
                        {'contribution_notes':'x'*2001},{'make':'x'*201},
                        {'wheel_size':'unknown-size'},{'bike_type':'G'},{'colour':'invalid-colour'}]:
            with self.subTest(changes=changes):
                self.assertEqual(self.bike_post(self.bike_form(**changes)).status_code,400)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM bike_inventory').fetchone()[0],0)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM bike_contributions').fetchone()[0],0)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM volunteers').fetchone()[0],2)

    def test_bike_audit_failure_rolls_back_everything(self):
        values=self.bike_form(contribution_notes='Must roll back')
        with patch('volunteer_entry._audit',side_effect=sqlite3.IntegrityError('audit failed')):
            with self.assertRaises(sqlite3.IntegrityError): self.bike_post(values)
        for table in ('bike_inventory','bike_contributions','workshop_submissions'):
            self.assertEqual(self.conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0],0)

    def test_old_schema_is_unavailable_until_explicit_upgrade(self):
        self.conn.execute('ALTER TABLE bike_contributions DROP COLUMN notes')
        self.conn.commit()
        for route in ('/volunteer/finished-bike', '/volunteer/log-hours'):
            self.assertEqual(self.client.get(route).status_code,503)
        with self.client.session_transaction() as session: session['username']='tester'
        self.assertEqual(self.client.get('/inventory').status_code,503)
        self.assertNotIn('notes',{r[1] for r in self.conn.execute('PRAGMA table_info(bike_contributions)')})
        initialize(self.path,'tester','Enable notes')
        self.assertEqual(self.client.get('/volunteer/finished-bike').status_code,200)

    def test_bike_tokens_are_purpose_bound_and_forget_stays_on_bike_form(self):
        self.assertEqual(self.bike_post(self.bike_form(form_token=self.form()['form_token'])).status_code,400)
        self.bike_post(self.bike_form(remember='yes'))
        html=self.client.get('/volunteer/finished-bike?shop=B').get_data(as_text=True)
        token=re.search(r'name="form_token" value="([^"]+)"',html).group(1)
        response=self.client.post('/volunteer/forget',data={'form_token':token,'shop':'B','return_to':'bikes'})
        self.assertEqual(response.location,'/volunteer/finished-bike?shop=B')
        self.assertIsNone(self.client.get_cookie(COOKIE,path='/volunteer'))
        self.assertEqual(self.client.get('/volunteer/bike-thanks').status_code,302)

    def test_anonymous_exact_minutes_save_retry_receipt_and_attribution(self):
        before = self.snapshot()
        values = self.form()
        for _ in range(2):
            self.assertEqual(self.post(values).status_code, 303)
        self.assertEqual(self.conn.execute('SELECT volunteer_id,minutes,created_by FROM volunteer_hours').fetchall(),
                         [(10,137,'volunteer-self:10')])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM admin_changes WHERE entity='volunteer_hours'").fetchone()[0],1)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM volunteers').fetchone()[0],2)
        self.assertEqual(self.snapshot(),before)
        receipt = self.client.get('/volunteer/thanks').get_data(as_text=True)
        self.assertIn('2h 17m',receipt)
        self.assertIn('Bentonville',receipt)
        self.assertNotIn('private@example.invalid',receipt)
        stranger = app.test_client()
        self.assertEqual(stranger.get('/volunteer/thanks').status_code,302)
        self.assertEqual(stranger.post('/volunteer/log-hours',data=values).status_code,400)

    def impact_request(self, volunteer_id='10', token=None):
        if token is None:
            page=self.client.get('/volunteer/log-hours?shop=B').get_data(as_text=True)
            token=re.search(r'data-impact-token="([^"]+)"',page).group(1)
        return self.client.post('/volunteer/impact',data={'volunteer_id':volunteer_id,'form_token':token})

    def test_impact_hidden_without_selection_and_remembered_summary_clears_on_forget(self):
        page=self.client.get('/volunteer/log-hours?q=Alex').get_data(as_text=True)
        self.assertNotIn('Your year so far',page)
        self.assertRegex(page,r'<div data-volunteer-impact[^>]+hidden')
        self.post(self.form(remember='yes'))
        page=self.client.get('/volunteer/log-hours?shop=R').get_data(as_text=True)
        self.assertIn('Your year so far',page)
        self.assertIn('2h 17m',page)
        self.assertNotRegex(page,r'<div data-volunteer-impact[^>]+hidden')
        token=re.search(r'name="form_token" value="([^"]+)"',page).group(1)
        self.client.post('/volunteer/forget',data={'form_token':token,'shop':'B'})
        self.assertNotIn(b'Your year so far',self.client.get('/volunteer/log-hours').data)

    def test_public_impact_is_aggregate_only_read_only_and_uses_selected_id(self):
        self.post(self.form(notes='Private time note'))
        self.bike_post(self.bike_form(contribution_notes='Private bike note'))
        self.conn.execute("UPDATE bike_contributions SET recorded_at='2026-01-05T18:00:00+00:00'")
        self.conn.commit()
        tables=('volunteer_hours','bike_inventory','bike_contributions','admin_changes','workshop_submissions')
        before={t:self.conn.execute(f'SELECT * FROM {t}').fetchall() for t in tables}
        response=self.impact_request()
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.headers['Cache-Control'],'no-store')
        self.assertIn(b'2h 17m',response.data)
        self.assertIn(b'Bikes worked on',response.data)
        for private in (b'Private time note',b'Private bike note',b'private@example.invalid',b'4795551234'):
            self.assertNotIn(private,response.data)
        self.assertIn(b'first entry',self.impact_request('20').data)
        self.assertEqual(before,{t:self.conn.execute(f'SELECT * FROM {t}').fetchall() for t in tables})
        for identifier in ('', '999', '10.0'):
            self.assertIn(self.impact_request(identifier).status_code,(400,404))
        self.assertEqual(self.impact_request(token=self.form()['form_token']).status_code,400)
        self.assertEqual(self.client.delete('/volunteer/impact').status_code,405)
        self.assertEqual(self.client.post('/volunteer-hours/1/void').status_code,302)

    def test_saved_hours_receipt_shows_updated_total_without_double_counting_retry(self):
        self.post(self.form(hours='1',minutes='0'))
        values=self.form(hours='2',minutes='17')
        self.post(values)
        self.post(values)
        receipt=self.client.get('/volunteer/thanks').get_data(as_text=True)
        self.assertIn('Your year so far',receipt)
        self.assertIn('3h 17m',receipt)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM volunteer_hours').fetchone()[0],2)

    def test_defaults_shop_links_and_optional_fields(self):
        html = self.client.get('/volunteer/log-hours?shop=R').get_data(as_text=True)
        self.assertIn('value="R" selected',html)
        self.assertIn('value="2026-10-05"',html)
        self.assertIn('placeholder="0" value=""',html)
        self.assertNotIn('Request Form Links',html)
        self.assertNotIn('private@example.invalid',html)
        self.assertEqual(self.post(self.form(hours='',minutes='1')).status_code,303)
        self.assertEqual(self.conn.execute('SELECT minutes FROM volunteer_hours').fetchone()[0],1)

    def test_search_minimum_wildcards_limit_and_namesakes(self):
        self.assertEqual(self.client.get('/volunteer/names?q=A').json,[])
        self.assertEqual(self.client.get('/volunteer/names?q=%25%25').json,[])
        names=self.client.get('/volunteer/names?q=Alex').json
        self.assertEqual([r['volunteer_id'] for r in names],[10,20])
        self.assertEqual(set(names[0]),{'volunteer_id','volunteer_name'})
        self.conn.executemany('INSERT INTO volunteers(volunteer_name) VALUES (?)', [('Alison',)]*20)
        self.conn.commit()
        self.assertEqual(len(self.client.get('/volunteer/names?q=Al').json),10)
        html=self.client.get('/volunteer/log-hours?shop=B&q=Alex').get_data(as_text=True)
        self.assertIn('name="volunteer_id" value="10"',html)
        self.assertIn('name="volunteer_id" value="20"',html)

    def test_remember_is_opt_in_signed_and_can_be_forgotten(self):
        self.post(self.form())
        self.assertIsNone(self.client.get_cookie(COOKIE,path='/volunteer'))
        response=self.post(self.form(remember='yes'))
        cookie=self.client.get_cookie(COOKIE,path='/volunteer')
        self.assertTrue(cookie.http_only)
        self.assertEqual(cookie.same_site,'Lax')
        self.assertIn('Max-Age=15552000',response.headers.get('Set-Cookie'))
        html=self.client.get('/volunteer/log-hours?shop=R').get_data(as_text=True)
        self.assertIn('Logging time as <strong>Alex Example',html)
        self.assertIn('value="R" selected',html)
        self.assertIn('placeholder="0" value=""',html)
        token=re.search(r'name="form_token" value="([^"]+)"',html).group(1)
        self.assertEqual(self.client.post('/volunteer/forget',data={'form_token':token,'shop':'R'}).status_code,303)
        self.assertIsNone(self.client.get_cookie(COOKIE,path='/volunteer'))
        self.assertEqual(self.client.get('/volunteer/thanks').status_code,302)
        self.client.set_cookie(COOKIE,'10',path='/volunteer')
        self.assertNotIn('Logging time as',self.client.get('/volunteer/log-hours').get_data(as_text=True))

    def test_unchecking_remember_clears_previous_choice_and_no_staff_access(self):
        self.post(self.form(remember='yes'))
        self.post(self.form())
        self.assertIsNone(self.client.get_cookie(COOKIE,path='/volunteer'))
        for route in ['/volunteers','/volunteer-hours','/volunteer-hours/1/edit','/api/workshop/volunteers','/volunteer-hours/links']:
            self.assertEqual(self.client.get(route).status_code,302)
        self.assertEqual(self.client.post('/volunteers',data={'volunteer_name':'New person'}).status_code,302)
        self.assertEqual(self.client.post('/volunteer/forget').status_code,400)

    def test_inactive_volunteer_is_not_selectable_and_remembered_name_is_ignored(self):
        self.post(self.form(remember='yes'))
        time_form=self.form()
        bike_form=self.bike_form()
        self.conn.execute('UPDATE volunteers SET is_active=0 WHERE volunteer_id=10')
        self.conn.commit()
        self.assertEqual([r['volunteer_id'] for r in self.client.get('/volunteer/names?q=Alex').json],[20])
        self.assertNotIn(b'Logging time as',self.client.get('/volunteer/log-hours').data)
        self.assertNotIn(b'Your year so far',self.client.get('/volunteer/log-hours').data)
        self.assertEqual(self.post(time_form).status_code,400)
        self.assertEqual(self.bike_post(bike_form).status_code,400)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM volunteer_hours').fetchone()[0],1)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM bike_inventory').fetchone()[0],0)
        self.assertEqual(self.impact_request().status_code,404)

    def test_validation_retains_exact_values_and_creates_no_partial_records(self):
        for changes in [{'volunteer_id':'999'},{'volunteer_id':'10.0'},{'hours':'2.5'},{'minutes':'60'},
                        {'minutes':'-1'},{'hours':'0','minutes':'0'},{'hours':'24','minutes':'1'},
                        {'hours':'1e9'},{'shop_name':'unknown'},{'work_date':'2026-10-06'},
                        {'work_date':'2026-02-30'},{'notes':'x'*2001}]:
            with self.subTest(changes=changes):
                response=self.post(self.form(**changes))
                self.assertEqual(response.status_code,400)
                self.assertIn(b'not been saved',response.data)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM volunteer_hours').fetchone()[0],0)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM workshop_submissions').fetchone()[0],0)

    def test_daily_total_includes_staff_entries_and_audit_failure_rolls_back(self):
        self.post(self.form(hours='23',minutes='0'))
        self.assertEqual(self.post(self.form(hours='2',minutes='0')).status_code,400)
        values=self.form(hours='0',minutes='30')
        with patch('volunteer_entry._audit',side_effect=sqlite3.IntegrityError('audit failed')):
            with self.assertRaises(sqlite3.IntegrityError): self.post(values)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM volunteer_hours').fetchone()[0],1)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM workshop_submissions').fetchone()[0],1)

    def test_setup_and_logged_in_view_do_not_leak_staff_navigation(self):
        with self.client.session_transaction() as session: session['username']='tester'
        html=self.client.get('/volunteer/log-hours?shop=B').get_data(as_text=True)
        self.assertNotIn('Order Desk',html)
        links=self.client.get('/volunteer-hours/links')
        self.assertEqual(links.status_code,200)
        self.assertIn(b'/volunteer/log-hours?shop=R',links.data)
        self.conn.execute('DROP TABLE volunteer_hours')
        self.conn.commit()
        self.assertEqual(self.client.get('/volunteer/log-hours').status_code,503)
        self.assertFalse(self.conn.execute("SELECT 1 FROM sqlite_master WHERE name='volunteer_hours'").fetchone())
