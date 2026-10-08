"""Volunteer self-entry. Name selection is attribution, not staff authentication."""
from contextlib import closing
from datetime import datetime
import re
from zoneinfo import ZoneInfo

from flask import Blueprint, abort, current_app, jsonify, redirect, render_template, request, session, url_for
from itsdangerous import BadSignature, URLSafeTimedSerializer

from volunteer_impact import yearly_impact
from admin_tools import _audit, canonical_bike_tag, fingerprint, TAG_KEY_SQL
from order_intake import check_token, form_token, shops
from workshop import connection, now, prior_submission, record_submission, add_contributions, schema_ready

volunteer_entry = Blueprint('volunteer_entry', __name__, url_prefix='/volunteer')
COOKIE = 'pif_remembered_volunteer'
REMEMBER_SECONDS = 180 * 24 * 60 * 60
PURPOSE = 'volunteer-self-hours'
WHEEL_SIZES = ('12 inch', '14 inch', '16 inch', '18 inch', '20 inch', '24 inch',
               '26 inch', '27 inch', '27.5 inch', '29 inch', '650B', '650C', '700C', 'Other')
BIKE_TYPES = tuple('ABCDEF')
BIKE_COLOURS = (
    ('Black', '#202521'), ('White', '#ffffff'), ('Grey', '#808080'),
    ('Silver', '#c0c0c0'), ('Red', '#d32f2f'), ('Orange', '#ed7d20'),
    ('Yellow', '#f5d328'), ('Green', '#388443'), ('Blue', '#2268c4'),
    ('Purple', '#854bb0'), ('Pink', '#ed8db5'), ('Brown', '#865534'),
    ('Gold', '#c5a340'), ('Multicolour', 'linear-gradient(135deg, #d32f2f, #f5d328, #2268c4)'),
    ('Other', 'repeating-linear-gradient(45deg, #fff, #fff 4px, #ccc 4px, #ccc 8px)'),
)



def today():
    return datetime.now(ZoneInfo('America/Chicago')).date()


def signer():
    return URLSafeTimedSerializer(current_app.secret_key, salt='pif-volunteer-preference-v1')


def remembered_person(conn):
    try:
        identifier = signer().loads(request.cookies.get(COOKIE, ''), max_age=REMEMBER_SECONDS)
        if type(identifier) is not int:
            return None
        return conn.execute('SELECT volunteer_id,volunteer_name FROM volunteers WHERE volunteer_id=? AND is_active=1', (identifier,)).fetchone()
    except (BadSignature, ValueError, TypeError):
        return None


@volunteer_entry.before_request
def available():
    with closing(connection()) as conn:
        ready = schema_ready(conn)
    if not ready:
        return render_template('volunteer_unavailable.html', requester_mode=True), 503


@volunteer_entry.after_request
def private_response(response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['X-Robots-Tag'] = 'noindex, nofollow'
    return response


def name_matches(conn, query):
    # Don't publish a directory or contact channels. Escape LIKE wildcards so
    # searching '%' cannot return every profile. IDs distinguish namesakes.
    if not 2 <= len(query) <= 100:
        return []
    escaped = query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    return [dict(row) for row in conn.execute('''SELECT volunteer_id,volunteer_name FROM volunteers
        WHERE is_active=1 AND volunteer_name LIKE ? ESCAPE '\\'
        ORDER BY volunteer_name COLLATE NOCASE,volunteer_id LIMIT 10''', (f'%{escaped}%',))]


@volunteer_entry.get('/names')
def names():
    with closing(connection()) as conn:
        return jsonify(name_matches(conn, request.args.get('q', '').strip()))


@volunteer_entry.post('/impact')
def impact():
    # User explicitly approved aggregate visibility through name selection.
    # This endpoint reads totals only; contact details and individual logs stay private.
    check_token(request.form.get('form_token', ''), 'volunteer-impact')
    identifier = request.form.get('volunteer_id', '')
    if not re.fullmatch(r'[0-9]{1,18}', identifier):
        abort(400)
    with closing(connection()) as conn:
        person = conn.execute('SELECT volunteer_id FROM volunteers WHERE volunteer_id=? AND is_active=1',
                              (int(identifier),)).fetchone()
        if not person:
            abort(404)
        stats = yearly_impact(conn, person['volunteer_id'], today())
    return render_template('_volunteer_impact.html', impact=stats)


@volunteer_entry.post('/forget')
def forget():
    check_token(request.form.get('form_token', ''), 'forget-volunteer')
    session.pop('volunteer_receipt', None)
    session.pop('volunteer_bike_receipt', None)
    endpoint = '.finished_bike' if request.form.get('return_to') == 'bikes' else '.log_hours'
    response = redirect(url_for(endpoint, shop=request.form.get('shop', '')), code=303)
    response.delete_cookie(COOKIE, path='/volunteer', httponly=True, samesite='Lax')
    return response


def receipt_response(conn, identifier, remember):
    row = conn.execute('''SELECT h.*,v.volunteer_name,s.shop_location FROM volunteer_hours h
        JOIN volunteers v ON v.volunteer_id=h.volunteer_id
        LEFT JOIN shops s ON s.shop_name=h.shop_name WHERE time_log_id=?''', (identifier,)).fetchone()
    session['volunteer_receipt'] = {key: row[key] for key in
        ('volunteer_id', 'volunteer_name', 'minutes', 'work_date', 'shop_location', 'shop_name')}
    response = redirect(url_for('.thanks'), code=303)
    return remember_response(response, row['volunteer_id'], remember)


def remember_response(response, volunteer_id, remember):
    if remember:
        response.set_cookie(COOKIE, signer().dumps(volunteer_id), max_age=REMEMBER_SECONDS,
                            path='/volunteer', httponly=True, secure=request.is_secure, samesite='Lax')
    else:
        response.delete_cookie(COOKIE, path='/volunteer', httponly=True, samesite='Lax')
    return response


def bike_receipt_response(conn, inventory_id, key, remember, existing):
    bike = conn.execute('''SELECT b.bike_tag,b.shop_name,s.shop_location FROM bike_inventory b
        JOIN shops s ON s.shop_name=b.shop_name WHERE inventory_id=?''', (inventory_id,)).fetchone()
    contributors = conn.execute('''SELECT volunteer_id,recorded_name FROM bike_contributions
        WHERE inventory_id=? AND source_key LIKE ? ORDER BY contribution_id''',
        (inventory_id, f'web:{key}:%')).fetchall()
    session['volunteer_bike_receipt'] = {**dict(bike), 'volunteer_name': contributors[0]['recorded_name'],
                                         'count': len(contributors), 'existing': existing}
    response = redirect(url_for('.bike_thanks'), code=303)
    return remember_response(response, contributors[0]['volunteer_id'], remember)


@volunteer_entry.route('/finished-bike', methods=['GET', 'POST'])
def finished_bike():
    purpose = 'volunteer-self-finished-bike'
    token = request.form.get('form_token', '') if request.method == 'POST' else form_token(purpose)
    fields = ('volunteer_id', 'bike_tag', 'shop_name', 'make', 'model', 'colour', 'wheel_size', 'bike_type', 'contribution_notes')
    values = {field: request.form.get(field, '').strip() for field in fields}
    query = request.args.get('q', '').strip()[:100]
    action = request.form.get('action', 'save')
    errors, person, existing = {}, None, None
    remember = request.form.get('remember') == 'yes'
    with closing(connection()) as conn, conn:
        available_shops = shops(conn)
        codes = {s['shop_name'] for s in available_shops}
        if request.method == 'GET':
            values['shop_name'] = request.args.get('shop', '')
            if values['shop_name'] not in codes:
                values['shop_name'] = ''
            person = remembered_person(conn)
            remember = bool(person)
            if person:
                values['volunteer_id'] = str(person['volunteer_id'])
        else:
            key = check_token(token, purpose)
            conn.execute('BEGIN IMMEDIATE')
            prior = prior_submission(conn, key)
            if prior:
                return bike_receipt_response(conn, prior['entity_id'], key, remember,
                                             prior['entity'] == 'bike_contributions')
            if re.fullmatch(r'[0-9]{1,18}', values['volunteer_id']):
                person = conn.execute('SELECT volunteer_id,volunteer_name FROM volunteers WHERE volunteer_id=? AND is_active=1',
                                      (int(values['volunteer_id']),)).fetchone()
            if request.form.getlist('helper_ids') or request.form.getlist('volunteer_ids'):
                errors['contribution_notes'] = 'Each volunteer reports their own contribution. Submit this form again for yourself only.'
            if action not in {'check_tag', 'save'}:
                errors['contribution_notes'] = 'This form has changed. Please review and submit your own contribution.'
            tag = values['bike_tag']
            if (not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,49}', tag)
                    or not any(c.isdigit() for c in tag)):
                errors['bike_tag'] = 'Enter the actual bike tag; include a number. Letters and hyphens are allowed.'
            else:
                values['bike_tag'] = canonical_bike_tag(tag)
                if values['bike_tag'] == '0' or values['bike_tag'].casefold() in {'test2', 'test3'}:
                    errors['bike_tag'] = 'Enter the actual bike tag.'
                else:
                    existing = conn.execute(f'SELECT * FROM bike_inventory WHERE ({TAG_KEY_SQL})=?',
                                            (values['bike_tag'],)).fetchone()
            if action == 'save':
                if request.form.get('existing_token') and not existing:
                    errors['bike_tag'] = 'The tag changed. Check the new tag and review its bike details before saving.'
                if not person:
                    errors['volunteer_id'] = 'Find and select your name. Ask staff to add you if needed.'
                if not existing and values['shop_name'] not in codes:
                    errors['shop_name'] = 'Choose the shop where the bike was finished.'
                for field in ('make', 'model', 'colour', 'wheel_size', 'bike_type'):
                    if len(values[field]) > 200:
                        errors[field] = 'Use up to 200 characters.'
                if not existing:
                    for field, options in (('wheel_size', WHEEL_SIZES), ('bike_type', BIKE_TYPES),
                                           ('colour', tuple(name for name, _ in BIKE_COLOURS))):
                        if values[field] and values[field] not in options:
                            errors[field] = 'Choose one of the listed options, or leave blank if unsure.'
                if len(values['contribution_notes']) > 2000:
                    errors['contribution_notes'] = 'Use up to 2,000 characters.'
                if existing:
                    if request.form.get('confirm_existing') != 'yes':
                        errors['confirm_existing'] = 'This tag is already recorded. Review it below and confirm your contribution.'
                    else:
                        check_token(request.form.get('existing_token', ''),
                                    f'confirm-finished-bike:{existing["inventory_id"]}:{fingerprint(dict(existing))}')
                if not errors:
                    timestamp = now()
                    selected = [person]
                    if existing:
                        identifier = existing['inventory_id']
                    else:
                        cursor = conn.execute('''INSERT INTO bike_inventory
                            (bike_tag,shop_name,recorded_at,make,model,colour,wheel_size,bike_type,created_at)
                            VALUES (?,?,?,?,?,?,?,?,?)''',
                            (values['bike_tag'],values['shop_name'],timestamp,values['make'],values['model'],
                             values['colour'],values['wheel_size'],values['bike_type'],timestamp))
                        identifier = cursor.lastrowid
                    contribution_ids = add_contributions(conn, identifier, selected, timestamp, key,
                                                         values['contribution_notes'] or None)
                    entity = 'bike_contributions' if existing else 'bike_inventory'
                    after = {'inventory_id': identifier, 'contribution_ids': contribution_ids,
                             'volunteer_ids': [person['volunteer_id']], 'notes': values['contribution_notes'] or None}
                    if not existing:
                        after['bike'] = dict(conn.execute('SELECT * FROM bike_inventory WHERE inventory_id=?', (identifier,)).fetchone())
                    _audit(conn, f'volunteer-self:{person["volunteer_id"]}', 'Self-reported finished bike contribution',
                           entity, identifier, {}, after)
                    record_submission(conn, key, entity, identifier)
                    return bike_receipt_response(conn, identifier, key, remember, bool(existing))
        matches = name_matches(conn, query) if not person else []
        suggestions = {field: [r[0] for r in conn.execute(
            f"SELECT DISTINCT {field} FROM bike_inventory WHERE {field} IS NOT NULL AND {field}<>'' ORDER BY {field} LIMIT 100")]
            for field in ('make', 'model')}
        existing_shop = next((s['shop_location'] for s in available_shops if existing and s['shop_name'] == existing['shop_name']), '')
    return render_template('volunteer_finished_bike.html', requester_mode=True, values=values, person=person,
        remember=remember, errors=errors, form_token=token, shops=available_shops, query=query, matches=matches,
        suggestions=suggestions, wheel_sizes=WHEEL_SIZES, bike_types=BIKE_TYPES, bike_colours=BIKE_COLOURS,
        existing=existing, existing_shop=existing_shop, checked_tag=action == 'check_tag' and request.method == 'POST',
        existing_token=form_token(f'confirm-finished-bike:{existing["inventory_id"]}:{fingerprint(dict(existing))}') if existing else '',
        forget_token=form_token('forget-volunteer')), (400 if errors else 200)


@volunteer_entry.get('/bike-thanks')
def bike_thanks():
    receipt = session.get('volunteer_bike_receipt')
    if not receipt:
        return redirect(url_for('.finished_bike'))
    return render_template('volunteer_bike_thanks.html', requester_mode=True, receipt=receipt,
                           forget_token=form_token('forget-volunteer'))


@volunteer_entry.route('/log-hours', methods=['GET', 'POST'])
def log_hours():
    token = request.form.get('form_token', '') if request.method == 'POST' else form_token(PURPOSE)
    fields = ('volunteer_id', 'work_date', 'hours', 'minutes', 'shop_name', 'activity', 'notes')
    values = {field: request.form.get(field, '').strip() for field in fields}
    errors, person = {}, None
    query = request.args.get('q', '').strip()[:100]
    remember = request.form.get('remember') == 'yes'
    with closing(connection()) as conn, conn:
        available_shops = shops(conn)
        codes = {s['shop_name'] for s in available_shops}
        saved_person = remembered_person(conn)
        if request.method == 'GET':
            # A shop QR wins over any previous visit. Never carry yesterday's duration.
            values.update(work_date=today().isoformat(), shop_name=request.args.get('shop', ''))
            if values['shop_name'] not in codes:
                values['shop_name'] = ''
            person, remember = saved_person, bool(saved_person)
            if person:
                values['volunteer_id'] = str(person['volunteer_id'])
        else:
            key = check_token(token, PURPOSE)
            conn.execute('BEGIN IMMEDIATE')
            prior = prior_submission(conn, key)
            if prior:
                return receipt_response(conn, prior['entity_id'], remember)
            if re.fullmatch(r'[0-9]{1,18}', values['volunteer_id']):
                person = conn.execute('SELECT volunteer_id,volunteer_name FROM volunteers WHERE volunteer_id=? AND is_active=1',
                                      (int(values['volunteer_id']),)).fetchone()
            if not person:
                errors['volunteer_id'] = 'Find and select your name. If it is missing, ask staff to add you.'
            try:
                day = datetime.strptime(values['work_date'], '%Y-%m-%d').date()
                if day.isoformat() != values['work_date'] or day > today():
                    raise ValueError
            except ValueError:
                errors['work_date'] = 'Choose a valid date, no later than today.'
            minutes = 0
            if not all(re.fullmatch(r'[0-9]{1,2}', values[f] or '0') for f in ('hours', 'minutes')):
                errors['duration'] = 'Enter whole hours and minutes, such as 2 hours and 17 minutes.'
            else:
                hours, remainder = int(values['hours'] or 0), int(values['minutes'] or 0)
                minutes = hours * 60 + remainder
                if remainder > 59 or not 1 <= minutes <= 1440:
                    errors['duration'] = 'Enter 0–59 minutes and a total between 1 minute and 24 hours.'
            if values['shop_name'] not in codes:
                errors['shop_name'] = 'Choose the shop where you volunteered.'
            for field, limit in [('activity', 200), ('notes', 2000)]:
                if len(values[field]) > limit:
                    errors[field] = f'Use up to {limit:,} characters.'
            if person:
                other = conn.execute('''SELECT COALESCE(SUM(minutes),0) FROM volunteer_hours
                    WHERE volunteer_id=? AND work_date=? AND voided_at IS NULL''',
                    (person['volunteer_id'], values['work_date'])).fetchone()[0]
                if other + minutes > 1440:
                    errors['duration'] = 'This would take your daily total over 24 hours. Check the date and duration, or ask staff to correct an earlier entry.'
            if not errors:
                # Explicit self-reported attribution; never impersonate a staff login.
                actor, timestamp = f'volunteer-self:{person["volunteer_id"]}', now()
                cursor = conn.execute('''INSERT INTO volunteer_hours
                    (volunteer_id,work_date,minutes,shop_name,activity,notes,created_at,created_by,updated_at,updated_by)
                    VALUES (?,?,?,?,?,?,?,?,?,?)''',
                    (person['volunteer_id'], values['work_date'], minutes, values['shop_name'], values['activity'],
                     values['notes'], timestamp, actor, timestamp, actor))
                identifier = cursor.lastrowid
                after = dict(conn.execute('SELECT * FROM volunteer_hours WHERE time_log_id=?', (identifier,)).fetchone())
                _audit(conn, actor, 'Self-reported volunteer hours', 'volunteer_hours', identifier, {}, after)
                record_submission(conn, key, 'volunteer_hours', identifier)
                return receipt_response(conn, identifier, remember)
        matches = name_matches(conn, query) if not person else []
        stats = yearly_impact(conn, person['volunteer_id'], today()) if person else None
    return render_template('volunteer_log_hours.html', requester_mode=True, values=values, person=person,
                           remember=remember, errors=errors, form_token=token, shops=available_shops,
                           today=today().isoformat(), query=query, matches=matches,
                           impact=stats, impact_token=form_token('volunteer-impact'),
                           forget_token=form_token('forget-volunteer')), (400 if errors else 200)


@volunteer_entry.get('/thanks')
def thanks():
    receipt = session.get('volunteer_receipt')
    if not receipt:
        return redirect(url_for('.log_hours'))
    with closing(connection()) as conn:
        stats = yearly_impact(conn, receipt['volunteer_id'], today()) if receipt.get('volunteer_id') else None
    return render_template('volunteer_hours_thanks.html', requester_mode=True, receipt=receipt, impact=stats,
                           forget_token=form_token('forget-volunteer'))
