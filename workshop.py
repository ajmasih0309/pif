"""Staff inventory and volunteer time entry, independent of request orders."""
from contextlib import closing
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import re
from zoneinfo import ZoneInfo
from volunteer_impact import yearly_impact

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, session, url_for

from admin_tools import _audit, canonical_bike_tag, lookup_bike, fingerprint
from database import get_db_connection
from order_intake import check_token, form_token, shops

workshop = Blueprint('workshop', __name__)
REQUIRED_TABLES = {'bike_inventory', 'volunteers', 'bike_contributions', 'admin_changes',
                   'volunteer_hours', 'workshop_submissions'}


def now():
    return datetime.now(timezone.utc).isoformat()


def connection():
    conn = get_db_connection()
    conn.execute('PRAGMA foreign_keys=ON')
    return conn


def schema_ready(conn):
    present = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    return (REQUIRED_TABLES <= present
            and 'notes' in {r[1] for r in conn.execute('PRAGMA table_info(bike_contributions)')}
            and {'joined_on', 'is_active'} <= {r[1] for r in conn.execute('PRAGMA table_info(volunteers)')})


@workshop.before_request
def staff_only():
    if 'username' not in session:
        return redirect(url_for('login'))
    with closing(connection()) as conn:
        if not conn.execute('SELECT 1 FROM users WHERE username=?', (session['username'],)).fetchone():
            return redirect(url_for('login'))
        ready = schema_ready(conn)
    if not ready:
        return render_template('workshop_setup.html'), 503


@workshop.after_request
def private_response(response):
    response.headers['Cache-Control'] = 'no-store'
    return response


def values_for(fields):
    return {field: request.form.get(field, '').strip() for field in fields}


def check_length(values, errors, fields, limit=200):
    for field in fields:
        if len(values.get(field, '')) > limit:
            errors[field] = f'Use up to {limit:,} characters.'


def prior_submission(conn, key):
    return conn.execute('SELECT * FROM workshop_submissions WHERE submission_key=?', (key,)).fetchone()


def record_submission(conn, key, entity, entity_id):
    conn.execute('INSERT INTO workshop_submissions VALUES (?,?,?,?)', (key, entity, entity_id, now()))


def people(conn):
    return conn.execute('SELECT * FROM volunteers ORDER BY volunteer_name COLLATE NOCASE, volunteer_id').fetchall()


@workshop.get('/volunteers/<int:volunteer_id>/impact')
def volunteer_impact_preview(volunteer_id):
    with closing(connection()) as conn:
        person = conn.execute('SELECT volunteer_id,volunteer_name FROM volunteers WHERE volunteer_id=?',
                              (volunteer_id,)).fetchone()
        if not person:
            abort(404)
        stats = yearly_impact(conn, volunteer_id, datetime.now(ZoneInfo('America/Chicago')).date())
    return render_template('volunteer_impact_preview.html', person=person, impact=stats)


@workshop.get('/api/workshop/volunteers')
def volunteer_choices():
    with closing(connection()) as conn:
        return jsonify([{'volunteer_id': r['volunteer_id'], 'volunteer_name': r['volunteer_name']} for r in people(conn)])


def selected_volunteers(conn, errors):
    ids = list(dict.fromkeys(request.form.getlist('volunteer_ids')))
    if len(ids) > 100:
        errors['volunteer_ids'] = 'Choose up to 100 volunteers.'
        return []
    selected = []
    seen = set()
    for identifier in ids:
        person = conn.execute('SELECT * FROM volunteers WHERE volunteer_id=?', (identifier,)).fetchone()
        if not person:
            errors['volunteer_ids'] = 'Choose volunteers from the list.'
        elif person['volunteer_id'] not in seen:
            selected.append(person)
            seen.add(person['volunteer_id'])
    return selected


def paginate(conn, sql, params=()):
    count = conn.execute(f'SELECT COUNT(*) FROM ({sql})', params).fetchone()[0]
    pages = max(1, (count + 24) // 25)
    page = min(pages, max(1, request.args.get('page', 1, type=int)))
    rows = conn.execute(sql + ' LIMIT 25 OFFSET ?', (*params, (page - 1) * 25)).fetchall()
    return rows, {'page': page, 'pages': pages, 'total': count}


def add_contributions(conn, bike, volunteers, timestamp, key, notes=None):
    ids = []
    for person in volunteers:
        cursor = conn.execute('''INSERT INTO bike_contributions
            (inventory_id,volunteer_id,recorded_name,recorded_at,source_key,notes)
            VALUES (?,?,?,?,?,?)''', (bike, person['volunteer_id'], person['volunteer_name'],
                                    timestamp, f'web:{key}:{person["volunteer_id"]}', notes))
        ids.append(cursor.lastrowid)
    return ids


def volunteer_profile_values(values, errors):
    if values['joined_on']:
        try:
            joined = date.fromisoformat(values['joined_on'])
            if joined.isoformat() != values['joined_on'] or joined > datetime.now(ZoneInfo('America/Chicago')).date():
                raise ValueError
        except ValueError:
            errors['joined_on'] = 'Choose a valid date no later than today, or leave blank if unknown.'
    if values['is_active'] not in {'0', '1'}:
        errors['is_active'] = 'Choose Active or Inactive.'


@workshop.route('/volunteers/<int:volunteer_id>/edit', methods=['GET', 'POST'])
def edit_volunteer(volunteer_id):
    purpose = f'edit-volunteer:{volunteer_id}'
    token = request.form.get('form_token', '') if request.method == 'POST' else form_token(purpose)
    errors, status = {}, 200
    with closing(connection()) as conn, conn:
        if request.method == 'POST':
            key = check_token(token, purpose)
            conn.execute('BEGIN IMMEDIATE')
            if prior_submission(conn, key):
                return redirect(url_for('.volunteers', q=str(volunteer_id)), code=303)
        person = conn.execute('SELECT * FROM volunteers WHERE volunteer_id=?', (volunteer_id,)).fetchone()
        if not person:
            abort(404)
        before = {'joined_on': person['joined_on'], 'is_active': person['is_active']}
        values = {'joined_on': person['joined_on'] or '', 'is_active': str(person['is_active'])}
        version = fingerprint(before)
        if request.method == 'POST':
            values = values_for(('joined_on', 'is_active'))
            volunteer_profile_values(values, errors)
            if request.form.get('version') != version:
                errors['profile'] = 'This profile changed since you opened it. Review the current profile before trying again.'
                status = 409
                version = request.form.get('version', '')
            if errors:
                status = 409 if status == 409 else 400
            else:
                after = {'joined_on': values['joined_on'] or None, 'is_active': int(values['is_active'])}
                if after != before:
                    conn.execute('UPDATE volunteers SET joined_on=?,is_active=? WHERE volunteer_id=?',
                                 (after['joined_on'], after['is_active'], volunteer_id))
                    _audit(conn, session['username'], 'Volunteer joining date/status updated through management',
                           'volunteers', volunteer_id, before, after)
                record_submission(conn, key, 'volunteers', volunteer_id)
                flash('Volunteer profile updated.', 'success')
                return redirect(url_for('.volunteers', q=str(volunteer_id)), code=303)
    return render_template('volunteer_profile.html', person=person, values=values, errors=errors,
                           version=version, form_token=token,
                           today=datetime.now(ZoneInfo('America/Chicago')).date().isoformat()), status


@workshop.route('/volunteers', methods=['GET', 'POST'])
def volunteers():
    token = request.form.get('form_token', '') if request.method == 'POST' else form_token('new-volunteer')
    values = values_for(('volunteer_name', 'volunteer_email', 'volunteer_phone_number', 'joined_on'))
    values['is_active'] = request.form.get('is_active', '1')
    if request.method == 'GET':
        values['joined_on'] = datetime.now(ZoneInfo('America/Chicago')).date().isoformat()
    errors = {}
    q = request.args.get('q', '').strip()
    with closing(connection()) as conn, conn:
        if request.method == 'POST':
            key = check_token(token, 'new-volunteer')
            conn.execute('BEGIN IMMEDIATE')
            if prior_submission(conn, key):
                flash('That volunteer was already saved.', 'info')
                return redirect(url_for('.volunteers'), code=303)
            if not values['volunteer_name']:
                errors['volunteer_name'] = 'Enter a volunteer name.'
            check_length(values, errors, values)
            volunteer_profile_values(values, errors)
            if values['volunteer_email'] and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', values['volunteer_email']):
                errors['volunteer_email'] = 'Enter a valid email address or leave it blank.'
            phone = values['volunteer_phone_number']
            digits = re.sub(r'\D', '', phone)
            if phone and (not (len(digits) == 10 or len(digits) == 11 and digits.startswith('1')) or re.search(r'[^0-9+().\s-]', phone)):
                errors['volunteer_phone_number'] = 'Enter a 10-digit phone number, optionally with country code 1.'
            existing = conn.execute('SELECT 1 FROM volunteers WHERE lower(trim(volunteer_name))=lower(?)', (values['volunteer_name'],)).fetchone()
            if existing and request.form.get('different_person') != 'yes':
                errors['volunteer_name'] = 'A volunteer with this name exists. Use their ID, or confirm this is a different person.'
            if not errors:
                cursor = conn.execute('''INSERT INTO volunteers (volunteer_name,volunteer_email,volunteer_phone_number,joined_on,is_active)
                    VALUES (?,?,?,?,?)''', (values['volunteer_name'],values['volunteer_email'],
                    values['volunteer_phone_number'],values['joined_on'] or None,int(values['is_active'])))
                identifier = cursor.lastrowid
                _audit(conn, session['username'], 'Volunteer added through portal', 'volunteers', identifier, {}, values)
                record_submission(conn, key, 'volunteers', identifier)
                flash(f'Volunteer saved with ID #{identifier}. Use this person in bike contributions and hours.', 'success')
                return redirect(url_for('.volunteers', q=str(identifier)), code=303)
        rows, pagination = paginate(conn, '''SELECT * FROM volunteers
            WHERE volunteer_name LIKE ? OR volunteer_email LIKE ? OR CAST(volunteer_id AS TEXT)=?
            ORDER BY volunteer_name COLLATE NOCASE,volunteer_id''', (f'%{q}%', f'%{q}%', q))
    return render_template('volunteers.html', rows=rows, pagination=pagination, q=q,
                           values=values, errors=errors, form_token=token,
                           today=datetime.now(ZoneInfo('America/Chicago')).date().isoformat()), (400 if errors else 200)


@workshop.get('/inventory')
def inventory():
    q = request.args.get('q', '').strip()
    shop = request.args.get('shop', '')
    tag = canonical_bike_tag(q) if q else ''
    with closing(connection()) as conn:
        available_shops = shops(conn)
        rows, pagination = paginate(conn, '''SELECT b.*, s.shop_location,
            (SELECT COUNT(*) FROM bike_contributions c WHERE c.inventory_id=b.inventory_id) AS contributions
            FROM bike_inventory b LEFT JOIN shops s ON s.shop_name=b.shop_name
            WHERE (?='' OR b.bike_tag=? OR b.bike_tag LIKE ? OR b.make LIKE ? OR b.model LIKE ? OR b.colour LIKE ?)
              AND (?='' OR b.shop_name=?) ORDER BY b.inventory_id DESC''',
            (q, tag, f'%{q}%', f'%{q}%', f'%{q}%', f'%{q}%', shop, shop))
    return render_template('inventory.html', rows=rows, pagination=pagination, q=q, shop=shop, shops=available_shops)


@workshop.route('/inventory/new', methods=['GET', 'POST'])
def new_bike():
    purpose = 'new-inventory-bike'
    token = request.form.get('form_token', '') if request.method == 'POST' else form_token(purpose)
    fields = ('bike_tag', 'shop_name', 'recorded_at', 'make', 'model', 'colour', 'wheel_size', 'bike_type')
    values = values_for(fields)
    if request.method == 'GET':
        values.update(shop_name=session.get('workshop_shop', 'B'), recorded_at=datetime.now().strftime('%Y-%m-%dT%H:%M'))
    errors, duplicate = {}, None
    with closing(connection()) as conn, conn:
        available_shops = shops(conn)
        if request.method == 'POST':
            key = check_token(token, purpose)
            conn.execute('BEGIN IMMEDIATE')
            prior = prior_submission(conn, key)
            if prior:
                return redirect(url_for('.bike', inventory_id=prior['entity_id']), code=303)
            check_length(values, errors, fields)
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,49}', values['bike_tag']) or not any(c.isdigit() for c in values['bike_tag']):
                errors['bike_tag'] = 'Enter a bike tag containing a number (letters and hyphens are allowed).'
            else:
                values['bike_tag'] = canonical_bike_tag(values['bike_tag'])
                if values['bike_tag'] == '0' or values['bike_tag'].casefold() in {'test2', 'test3'}:
                    errors['bike_tag'] = 'Enter the actual bike tag.'
                duplicate = lookup_bike(conn, values['bike_tag'])
                if duplicate:
                    errors['bike_tag'] = 'This tag already exists. Open its record to add volunteers.'
            if values['shop_name'] not in {s['shop_name'] for s in available_shops}:
                errors['shop_name'] = 'Choose a shop.'
            try:
                if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}', values['recorded_at']):
                    raise ValueError
                if datetime.fromisoformat(values['recorded_at']) > datetime.now():
                    raise ValueError
            except ValueError:
                errors['recorded_at'] = 'Enter a valid finished time, no later than now.'
            selected = selected_volunteers(conn, errors)
            if not selected:
                errors['volunteer_ids'] = 'Choose at least one volunteer. Add their profile first if needed.'
            if not errors:
                timestamp = now()
                cursor = conn.execute('''INSERT INTO bike_inventory
                    (bike_tag,shop_name,recorded_at,make,model,colour,wheel_size,bike_type,created_at)
                    VALUES (?,?,?,?,?,?,?,?,?)''', (*[values[f] for f in fields], timestamp))
                identifier = cursor.lastrowid
                contributions = add_contributions(conn, identifier, selected, values['recorded_at'], key)
                _audit(conn, session['username'], 'Finished bike recorded through portal', 'bike_inventory', identifier,
                       {}, {**values, 'volunteer_ids': [p['volunteer_id'] for p in selected], 'contribution_ids': contributions})
                record_submission(conn, key, 'bike_inventory', identifier)
                session['workshop_shop'] = values['shop_name']
                flash('Finished bike saved. Volunteer hours are recorded separately.', 'success')
                return redirect(url_for('.bike', inventory_id=identifier), code=303)
        volunteers = people(conn)
        suggestions = {field: [r[0] for r in conn.execute(f'SELECT DISTINCT {field} FROM bike_inventory WHERE {field} IS NOT NULL AND {field}<>\'\' ORDER BY {field} LIMIT 100')]
                       for field in ('make', 'model', 'colour', 'wheel_size', 'bike_type')}
    return render_template('inventory_form.html', values=values, errors=errors, form_token=token,
                           shops=available_shops, volunteers=volunteers, suggestions=suggestions,
                           selected_ids=request.form.getlist('volunteer_ids'), duplicate=duplicate), (400 if errors else 200)


@workshop.route('/inventory/<int:inventory_id>', methods=['GET', 'POST'])
def bike(inventory_id):
    purpose = f'bike-contributors-{inventory_id}'
    token = request.form.get('form_token', '') if request.method == 'POST' else form_token(purpose)
    errors = {}
    with closing(connection()) as conn, conn:
        if request.method == 'POST':
            key = check_token(token, purpose)
            conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT * FROM bike_inventory WHERE inventory_id=?', (inventory_id,)).fetchone()
        if row is None:
            abort(404)
        if request.method == 'POST':
            if prior_submission(conn, key):
                return redirect(url_for('.bike', inventory_id=inventory_id), code=303)
            selected = selected_volunteers(conn, errors)
            if not selected:
                errors['volunteer_ids'] = 'Choose at least one volunteer.'
            if not errors:
                ids = add_contributions(conn, inventory_id, selected, now(), key)
                _audit(conn, session['username'], 'Additional bike contribution recorded', 'bike_contributions', inventory_id,
                       {}, {'contribution_ids': ids, 'volunteer_ids': [p['volunteer_id'] for p in selected]})
                record_submission(conn, key, 'bike_contributions', inventory_id)
                flash('Contributions saved. The original bike details are unchanged.', 'success')
                return redirect(url_for('.bike', inventory_id=inventory_id), code=303)
        detail = lookup_bike(conn, row['bike_tag'])
        volunteers = people(conn)
    return render_template('inventory_detail.html', bike=detail, volunteers=volunteers, errors=errors,
                           form_token=token, selected_ids=request.form.getlist('volunteer_ids')), (400 if errors else 200)


def hours_values(values, conn, errors):
    person = conn.execute('SELECT volunteer_id FROM volunteers WHERE volunteer_id=?', (values['volunteer_id'],)).fetchone()
    if not person:
        errors['volunteer_id'] = 'Choose a volunteer.'
    else:
        values['volunteer_id'] = str(person['volunteer_id'])
    try:
        if date.fromisoformat(values['work_date']).isoformat() != values['work_date'] or date.fromisoformat(values['work_date']) > date.today():
            raise ValueError
    except ValueError:
        errors['work_date'] = 'Choose a valid work date, no later than today.'
    minutes = 0
    try:
        if not re.fullmatch(r'(?:[0-9]{1,2}(?:\.[0-9]{1,10})?|\.[0-9]{1,10})', values['hours']):
            raise ValueError
        duration = Decimal(values['hours']) * 60
        if not duration.is_finite() or not 1 <= duration <= 1440 or abs(duration - duration.to_integral_value()) > Decimal('0.000001'):
            raise ValueError
        minutes = int(duration.to_integral_value())
    except (InvalidOperation, ValueError):
        errors['hours'] = 'Enter between 1 minute and 24 hours, in whole minutes. For example, 1.5 means 1 hour 30 minutes.'
    if values['shop_name'] and not conn.execute('SELECT 1 FROM shops WHERE shop_name=?', (values['shop_name'],)).fetchone():
        errors['shop_name'] = 'Choose a shop or leave it unassigned.'
    check_length(values, errors, ('activity',))
    check_length(values, errors, ('notes',), 2000)
    return minutes


@workshop.get('/volunteer-hours')
def hours():
    filters = {f: request.args.get(f, '').strip() for f in ('volunteer_id', 'shop', 'from_date', 'to_date')}
    conditions, params = ['h.voided_at IS NULL'], []
    for field, column in [('volunteer_id', 'h.volunteer_id'), ('shop', 'h.shop_name'),
                           ('from_date', 'h.work_date >='), ('to_date', 'h.work_date <=')]:
        value = filters[field]
        if value:
            if field.endswith('date'):
                try:
                    if date.fromisoformat(value).isoformat() != value:
                        raise ValueError
                except ValueError:
                    abort(400, 'Use YYYY-MM-DD for date filters.')
                conditions.append(column + ' ?')
            else:
                conditions.append(column + '=?')
            params.append(value)
    if filters['from_date'] and filters['to_date'] and filters['from_date'] > filters['to_date']:
        abort(400, 'The end date must be on or after the start date.')
    sql = '''SELECT h.*,v.volunteer_name,s.shop_location FROM volunteer_hours h
             JOIN volunteers v ON v.volunteer_id=h.volunteer_id
             LEFT JOIN shops s ON s.shop_name=h.shop_name WHERE ''' + ' AND '.join(conditions)
    with closing(connection()) as conn:
        rows, pagination = paginate(conn, sql + ' ORDER BY h.work_date DESC,h.time_log_id DESC', params)
        total = conn.execute('SELECT COALESCE(SUM(minutes),0) FROM (' + sql + ')', params).fetchone()[0]
        volunteers, available_shops = people(conn), shops(conn)
    return render_template('volunteer_hours.html', rows=rows, pagination=pagination, total_minutes=total,
                           filters=filters, volunteers=volunteers, shops=available_shops)


@workshop.get('/volunteer-hours/links')
def volunteer_links():
    with closing(connection()) as conn:
        available_shops = shops(conn)
    return render_template('volunteer_entry_links.html', shops=available_shops)


@workshop.route('/volunteer-hours/new', methods=['GET', 'POST'])
@workshop.route('/volunteer-hours/<int:time_log_id>/edit', methods=['GET', 'POST'])
def hours_form(time_log_id=None):
    purpose = f'hours-{time_log_id or "new"}'
    token = request.form.get('form_token', '') if request.method == 'POST' else form_token(purpose)
    values = values_for(('volunteer_id', 'work_date', 'hours', 'shop_name', 'activity', 'notes', 'reason'))
    errors, row = {}, None
    with closing(connection()) as conn, conn:
        if request.method == 'POST':
            key = check_token(token, purpose)
            conn.execute('BEGIN IMMEDIATE')
            if prior_submission(conn, key):
                flash('That time entry was already saved.', 'info')
                return redirect(url_for('.hours'), code=303)
        if time_log_id is not None:
            row = conn.execute('SELECT * FROM volunteer_hours WHERE time_log_id=?', (time_log_id,)).fetchone()
            if row is None:
                abort(404)
            if row['voided_at']:
                abort(409, 'This time entry has been voided.')
        if request.method == 'GET':
            values.update(work_date=date.today().isoformat(), shop_name=session.get('workshop_shop', 'B'))
            if row:
                values.update({k: str(row[k] or '') for k in values if k in row.keys()})
                values['hours'] = format(Decimal(row['minutes']) / 60, '.10f').rstrip('0').rstrip('.')
        if request.method == 'POST':
            minutes = hours_values(values, conn, errors)
            if row and request.form.get('version') != str(row['version']):
                abort(409, 'This time entry changed. Reload before editing it again.')
            if row and (not values['reason'] or len(values['reason']) > 500):
                errors['reason'] = 'Explain the correction (up to 500 characters).'
            # Multiple sessions per day are allowed, but a day cannot exceed 24 hours.
            other_minutes = conn.execute('''SELECT COALESCE(SUM(minutes),0) FROM volunteer_hours
                WHERE volunteer_id=? AND work_date=? AND voided_at IS NULL AND time_log_id<>?''',
                (values['volunteer_id'], values['work_date'], time_log_id or -1)).fetchone()[0]
            if minutes + other_minutes > 1440:
                errors['hours'] = 'This volunteer already has hours on this date. The daily total cannot exceed 24 hours.'
            if not errors:
                timestamp = now()
                fields = (int(values['volunteer_id']), values['work_date'], minutes,
                          values['shop_name'] or None, values['activity'], values['notes'], timestamp, session['username'])
                if row:
                    conn.execute('''UPDATE volunteer_hours SET volunteer_id=?,work_date=?,minutes=?,shop_name=?,
                        activity=?,notes=?,updated_at=?,updated_by=?,version=version+1 WHERE time_log_id=?''', (*fields,time_log_id))
                else:
                    cursor = conn.execute('''INSERT INTO volunteer_hours
                        (volunteer_id,work_date,minutes,shop_name,activity,notes,updated_at,updated_by,created_at,created_by)
                        VALUES (?,?,?,?,?,?,?,?,?,?)''', (*fields,timestamp,session['username']))
                    time_log_id = cursor.lastrowid
                after = dict(conn.execute('SELECT * FROM volunteer_hours WHERE time_log_id=?', (time_log_id,)).fetchone())
                _audit(conn, session['username'], values['reason'] or 'Volunteer time recorded', 'volunteer_hours', time_log_id,
                       dict(row) if row else {}, after)
                record_submission(conn, key, 'volunteer_hours', time_log_id)
                flash('Volunteer hours saved.', 'success')
                return redirect(url_for('.hours', volunteer_id=values['volunteer_id']), code=303)
        volunteers, available_shops = people(conn), shops(conn)
    return render_template('volunteer_hours_form.html', values=values, errors=errors, form_token=token,
                           row=row, volunteers=volunteers, shops=available_shops,
                           void_token=form_token(f'void-hours-{time_log_id}') if row else None), (400 if errors else 200)


@workshop.post('/volunteer-hours/<int:time_log_id>/void')
def void_hours(time_log_id):
    check_token(request.form.get('form_token', ''), f'void-hours-{time_log_id}')
    reason = request.form.get('reason', '').strip()
    if not reason or len(reason) > 500:
        abort(400, 'Explain why this entry should be voided (up to 500 characters).')
    with closing(connection()) as conn, conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT * FROM volunteer_hours WHERE time_log_id=?', (time_log_id,)).fetchone()
        if row is None:
            abort(404)
        if not row['voided_at']:
            if request.form.get('version') != str(row['version']):
                abort(409, 'This time entry changed. Reload before voiding it.')
            conn.execute('''UPDATE volunteer_hours SET voided_at=?,void_reason=?,updated_at=?,updated_by=?,version=version+1
                WHERE time_log_id=?''', (now(),reason,now(),session['username'],time_log_id))
            after = dict(conn.execute('SELECT * FROM volunteer_hours WHERE time_log_id=?', (time_log_id,)).fetchone())
            _audit(conn, session['username'], reason, 'volunteer_hours', time_log_id, dict(row), after)
    flash('Time entry voided and excluded from totals. Its history is retained.', 'success')
    return redirect(url_for('.hours'), code=303)
