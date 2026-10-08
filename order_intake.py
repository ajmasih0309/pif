"""Shared form validation and atomic order creation for staff and invitees."""
import hashlib
import json
import re
import secrets
from datetime import date, datetime

from flask import abort, current_app, session
from itsdangerous import BadSignature, URLSafeSerializer

FIELDS = ('recipient_name', 'bike_style_preference', 'age', 'height',
          'bike_type_first_choice', 'bike_type_second_choice', 'notes')
HEIGHTS = ["< 3'0\""] + [f"{feet}'{inches}\"" for feet in range(3, 7) for inches in range(12)] + ["7'0\"", "> 7'0\""]
TYPES = ('Public', 'Pedal Partner', 'Speciality')


def ensure_schema(conn):
    # Additive only; existing orders and historical data are untouched.
    conn.execute('''CREATE TABLE IF NOT EXISTS order_submissions (
        submission_key TEXT PRIMARY KEY, order_ids TEXT NOT NULL, created_at TEXT NOT NULL)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS request_invites (
        invite_id INTEGER PRIMARY KEY AUTOINCREMENT, token_hash TEXT UNIQUE NOT NULL,
        issuance_key TEXT UNIQUE NOT NULL, label TEXT NOT NULL, shop_name TEXT NOT NULL,
        order_type TEXT NOT NULL, pedal_partner_name TEXT NOT NULL,
        issued_by TEXT NOT NULL, created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL,
        used_at INTEGER, revoked_at INTEGER)''')


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def form_token(purpose):
    session.setdefault('intake_csrf', secrets.token_urlsafe(32))
    signer = URLSafeSerializer(current_app.secret_key, salt='pif-intake-form-v1')
    return signer.dumps({'owner': session['intake_csrf'], 'purpose': purpose, 'nonce': secrets.token_urlsafe(32)})


def check_token(value, purpose):
    try:
        data = URLSafeSerializer(current_app.secret_key, salt='pif-intake-form-v1').loads(value)
        if data['purpose'] != purpose or not secrets.compare_digest(data['owner'], session.get('intake_csrf', '')):
            raise ValueError
    except (BadSignature, ValueError, KeyError, TypeError):
        abort(400, 'This form is no longer valid. Reload the page and try again.')
    return digest(value)


def form_values(form=None):
    values = {name: (form.get(name, '') if form is not None else '') for name in
              ('order_date', 'shop_name', 'contact_name', 'contact_phone_number', 'contact_email', 'pedal_partner_name', 'order_type')}
    if form is None:
        values.update(order_date=date.today().isoformat(), order_type='Public')
        return values, [{field: '' for field in FIELDS}]
    count = min(max(1, len(form.getlist('recipient_name[]'))), 100)
    arrays = {field: form.getlist(field + '[]') for field in FIELDS}
    return values, [{field: arrays[field][i] if i < len(arrays[field]) else '' for field in FIELDS} for i in range(count)]


def validate(form, shop_codes):
    values, rows = form_values(form)
    values = {k: v.strip() for k, v in values.items()}
    errors = {}
    for field, label, limit in [('contact_name', 'Contact name', 150), ('contact_email', 'Email', 254),
                                ('contact_phone_number', 'Phone number', 40)]:
        if (field == 'contact_name' and not values[field]) or len(values[field]) > limit:
            errors[field] = f'Enter a {label.lower()} (up to {limit} characters).'
    if values['contact_email'] and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', values['contact_email']):
        errors['contact_email'] = 'Enter an email address such as name@example.com.'
    phone = re.sub(r'\D', '', values['contact_phone_number'])
    if len(phone) == 11 and phone.startswith('1'):
        phone = phone[1:]
    if values['contact_phone_number'] and (len(phone) != 10 or re.search(r'[^0-9+().\s-]', values['contact_phone_number'])):
        errors['contact_phone_number'] = 'Enter a 10-digit phone number.'
    if values['shop_name'] not in shop_codes:
        errors['shop_name'] = 'Choose a bike shop.'
    try:
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', values['order_date']):
            raise ValueError
        date.fromisoformat(values['order_date'])
    except ValueError:
        errors['order_date'] = 'Enter a valid order date.'
    if values['order_type'] not in TYPES:
        errors['order_type'] = 'Choose a valid order type.'
    if len(values['pedal_partner_name']) > 150:
        errors['pedal_partner_name'] = 'Use up to 150 characters.'
    if values['order_type'] == 'Pedal Partner' and not values['pedal_partner_name']:
        errors['pedal_partner_name'] = 'Enter the Pedal Partner name.'
    names = form.getlist('recipient_name[]')
    if not 1 <= len(names) <= 100:
        errors['recipients'] = 'Include between 1 and 100 recipients.'
    if any(len(form.getlist(field + '[]')) not in (0, len(names)) for field in FIELDS[1:]):
        errors['recipients'] = 'Recipient details are incomplete. Check each recipient and submit again.'
    for i, row in enumerate(rows):
        for field in row:
            row[field] = row[field].strip()
        prefix = f'recipient-{i}-'
        if not row['recipient_name'] or len(row['recipient_name']) > 150:
            errors[prefix + 'recipient_name'] = 'Enter a recipient name (up to 150 characters).'
        if row['age'] and (len(row['age']) > 3 or not row['age'].isascii() or not row['age'].isdigit() or not 1 <= int(row['age']) <= 80):
            errors[prefix + 'age'] = 'Enter a whole-number age from 1 to 80.'
        if row['height'] and row['height'] not in HEIGHTS:
            errors[prefix + 'height'] = 'Choose a height from the list.'
        if row['bike_style_preference'] not in ('', 'Male', 'Female', 'No Preference'):
            errors[prefix + 'bike_style_preference'] = 'Choose a style preference from the list.'
        for field in ('bike_type_first_choice', 'bike_type_second_choice'):
            if row[field] and row[field] not in list('ABCDEF'):
                errors[prefix + field] = 'Choose a bike style A–F.'
        if len(row['notes']) > 2000:
            errors[prefix + 'notes'] = 'Keep notes within 2,000 characters.'
    return values, rows, phone, errors


def existing_submission(conn, key):
    row = conn.execute('SELECT order_ids FROM order_submissions WHERE submission_key=?', (key,)).fetchone()
    return json.loads(row['order_ids']) if row else None


def save_order(conn, values, rows, phone, actor, key):
    """Call inside BEGIN IMMEDIATE; receipt and every recipient commit together."""
    previous = existing_submission(conn, key)
    if previous:
        return previous, False
    contact = conn.execute('''SELECT contact_id FROM contacts WHERE contact_name=?
        AND contact_email=? AND contact_phone_number=? ORDER BY contact_id LIMIT 1''',
        (values['contact_name'], values['contact_email'], phone)).fetchone() if values['contact_email'] or phone else None
    contact_id = contact['contact_id'] if contact else conn.execute('''INSERT INTO contacts
        (contact_name, contact_phone_number, contact_email) VALUES (?, ?, ?)''',
        (values['contact_name'], phone, values['contact_email'])).lastrowid
    partner_id = None
    if values['pedal_partner_name']:
        partner = conn.execute('SELECT pedal_partner_id FROM pedal_partners WHERE pedal_partner_name=? ORDER BY pedal_partner_id LIMIT 1',
                               (values['pedal_partner_name'],)).fetchone()
        partner_id = partner['pedal_partner_id'] if partner else conn.execute(
            'INSERT INTO pedal_partners (pedal_partner_name) VALUES (?)', (values['pedal_partner_name'],)).lastrowid
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ids = []
    for row in rows:
        recipient_id = conn.execute('''INSERT INTO recipients (recipient_name, age, height,
            bike_style_preference) VALUES (?, ?, ?, ?)''', (row['recipient_name'], row['age'] or None,
            row['height'] or None, row['bike_style_preference'] or None)).lastrowid
        ids.append(conn.execute('''INSERT INTO orders (contact_id, recipient_id, shop_name,
            pedal_partner_id, order_date, order_type, order_status, last_status,
            last_updated_date, last_updated_by, bike_type_first_choice, bike_type_second_choice, notes)
            VALUES (?, ?, ?, ?, ?, ?, 'Open', 'Open', ?, ?, ?, ?, ?)''',
            (contact_id, recipient_id, values['shop_name'], partner_id, values['order_date'],
             values['order_type'], timestamp, actor, row['bike_type_first_choice'],
             row['bike_type_second_choice'], row['notes'])).lastrowid)
    conn.execute('INSERT INTO order_submissions VALUES (?, ?, ?)', (key, json.dumps(ids), timestamp))
    return ids, True


def shops(conn):
    return conn.execute('SELECT shop_name, shop_location FROM shops WHERE shop_name IS NOT NULL ORDER BY shop_location').fetchall()
