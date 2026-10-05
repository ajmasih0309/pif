"""Staff-issued, single-submission requester forms. No email or network setup."""
from contextlib import closing
from datetime import date, datetime, timezone
import secrets
import time

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.datastructures import MultiDict

from database import get_db_connection
from order_intake import (HEIGHTS, TYPES, check_token, digest, ensure_schema, form_token,
                          form_values, save_order, shops, validate)

requester_links = Blueprint('requester_links', __name__)


@requester_links.after_request
def private_response(response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['X-Robots-Tag'] = 'noindex, nofollow'
    return response


def state(invite, now):
    if invite['used_at'] is not None:
        return 'Used'
    if invite['revoked_at'] is not None:
        return 'Revoked'
    if invite['expires_at'] <= now:
        return 'Expired'
    return 'Unused'


@requester_links.route('/request-links', methods=['GET', 'POST'])
def manage():
    if 'username' not in session:
        return redirect(url_for('login'))
    token = request.form.get('form_token', '') if request.method == 'POST' else form_token('issue-link')
    values = {k: request.form.get(k, '') for k in ('label', 'shop_name', 'order_type', 'pedal_partner_name', 'days')}
    if request.method == 'GET':
        values.update(order_type='Public', days='7')
    errors, created_link = {}, None
    with closing(get_db_connection()) as conn, conn:
        ensure_schema(conn)
        available_shops = shops(conn)
        if request.method == 'POST':
            key = check_token(token, 'issue-link')
            if values['shop_name'] not in {s['shop_name'] for s in available_shops}:
                errors['shop_name'] = 'Choose a shop.'
            if values['order_type'] not in TYPES:
                errors['order_type'] = 'Choose an order type.'
            if values['days'] not in ('1', '7', '14'):
                errors['days'] = 'Choose 1, 7, or 14 days.'
            if len(values['label']) > 100:
                errors['label'] = 'Use up to 100 characters.'
            if len(values['pedal_partner_name']) > 150 or (values['order_type'] == 'Pedal Partner' and not values['pedal_partner_name'].strip()):
                errors['pedal_partner_name'] = 'Enter a Pedal Partner name (up to 150 characters).'
            if not errors:
                conn.execute('BEGIN IMMEDIATE')
                if conn.execute('SELECT 1 FROM request_invites WHERE issuance_key=?', (key,)).fetchone():
                    flash('That link was already created. You can revoke it and create another if needed.', 'info')
                    return redirect(url_for('.manage'))
                secret = secrets.token_urlsafe(32)
                now = int(time.time())
                conn.execute('''INSERT INTO request_invites (token_hash, issuance_key, label,
                    shop_name, order_type, pedal_partner_name, issued_by, created_at, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (digest(secret), key, values['label'].strip(), values['shop_name'], values['order_type'],
                     values['pedal_partner_name'].strip(), session['username'], now, now + int(values['days']) * 86400))
                created_link = url_for('.intake', secret=secret)
                token = form_token('issue-link')
        now = int(time.time())
        # Paginate so the history remains small even after years of use.
        page = max(1, request.args.get('page', 1, type=int))
        invites = [dict(r) for r in conn.execute('SELECT * FROM request_invites ORDER BY invite_id DESC LIMIT 26 OFFSET ?', ((page - 1) * 25,))]
        has_next = len(invites) > 25
        for invite in invites:
            invite['state'] = state(invite, now)
            invite['expires_display'] = datetime.fromtimestamp(invite['expires_at'], timezone.utc).strftime('%b %d, %Y %H:%M UTC')
    return render_template('request_links.html', values=values, errors=errors, shops=available_shops,
                           order_types=TYPES, form_token=token, revoke_token=form_token('revoke-link'),
                           created_link=created_link, invites=invites[:25], page=page, has_next=has_next), (400 if errors else 200)


@requester_links.post('/request-links/<int:invite_id>/revoke')
def revoke(invite_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    check_token(request.form.get('form_token', ''), 'revoke-link')
    with closing(get_db_connection()) as conn, conn:
        ensure_schema(conn)
        conn.execute('UPDATE request_invites SET revoked_at=? WHERE invite_id=? AND used_at IS NULL AND revoked_at IS NULL', (int(time.time()), invite_id))
    flash('Link revoked. Any completed submission is unchanged.', 'success')
    return redirect(url_for('.manage'))


@requester_links.route('/request/<secret>', methods=['GET', 'POST'])
def intake(secret):
    if len(secret) != 43:
        abort(404)
    with closing(get_db_connection()) as conn, conn:
        ensure_schema(conn)
        # The write lock serializes token consumption with order creation and revocation.
        if request.method == 'POST':
            conn.execute('BEGIN IMMEDIATE')
        invite = conn.execute('SELECT * FROM request_invites WHERE token_hash=?', (digest(secret),)).fetchone()
        if invite is None:
            return render_template('request_result.html', requester_mode=True, state='Unavailable'), 404
        current_state = state(invite, int(time.time()))
        if current_state != 'Unused':
            return render_template('request_result.html', requester_mode=True, state=current_state), (200 if current_state == 'Used' else 410)
        purpose = f'invite-{invite["invite_id"]}'
        token = request.form.get('form_token', '') if request.method == 'POST' else form_token(purpose)
        available_shops = shops(conn)
        values, recipients = form_values()
        values.update(shop_name=invite['shop_name'], order_type=invite['order_type'], pedal_partner_name=invite['pedal_partner_name'])
        errors = {}
        if request.method == 'POST':
            check_token(token, purpose)
            posted = MultiDict(request.form)
            # Staff-selected routing is authoritative; the requester controls intake fields only.
            for field in ('shop_name', 'order_type', 'pedal_partner_name'):
                posted[field] = invite[field]
            posted['order_date'] = date.today().isoformat()
            values, recipients, phone, errors = validate(posted, {s['shop_name'] for s in available_shops})
            if not errors:
                save_order(conn, values, recipients, phone, f'Request link #{invite["invite_id"]}', f'invite:{invite["invite_id"]}')
                conn.execute('UPDATE request_invites SET used_at=? WHERE invite_id=?', (int(time.time()), invite['invite_id']))
                return redirect(url_for('.intake', secret=secret), code=303)
    return render_template('add.html', values=values, recipients=recipients, errors=errors,
                           shops=available_shops, heights=HEIGHTS, order_types=TYPES,
                           form_token=token, requester_mode=True), (400 if errors else 200)
