"""
Main Application Entry Point (app.py)
-------------------------------------
Handles route definitions and background scheduling. 
Database logic, utilities, and configurations are imported from external modules.
"""

import os
from contextlib import closing
from datetime import datetime, timedelta
from functools import wraps
import subprocess

from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import check_password_hash
from flask_apscheduler import APScheduler
from dotenv import load_dotenv

# for search api
from flask import jsonify

# Load environment variables
load_dotenv()

# --- Local Module Imports ---
from config import Config
from database import get_db_connection
from order_search import search_orders
from order_intake import (ensure_schema, form_token, check_token, form_values, validate,
                          save_order, existing_submission, shops, HEIGHTS, TYPES)
from utils import send_email, email_feedback, fetch_all_orders


# =============================================================================
# APP CONFIGURATION & SCHEDULER
# =============================================================================
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'loremipsum')
app.config['DB_PATH'] = os.getenv('DB_PATH', 'data/processed/pif.db')
for setting in ('MAIL_USERNAME', 'MAIL_PASSWORD', 'MAIL_SERVER', 'MAIL_PORT',
                'MAIL_DEFAULT_SENDER', 'MAIL_TEST_RECIPIENT', 'EMAIL_MODE',
                'EMAIL_PREVIEW_DIR', 'EMAIL_LIVE_ENABLED', 'EMAIL_REMINDERS_ENABLED'):
    app.config[setting] = getattr(Config, setting)

from requester_links import requester_links
app.register_blueprint(requester_links)
from workshop import workshop
app.register_blueprint(workshop)
from volunteer_entry import volunteer_entry
app.register_blueprint(volunteer_entry)

scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

# =============================================================================
# AUTHENTICATION
# =============================================================================
def login_required(f):
    """Decorator to protect routes requiring authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# =============================================================================
# APP ROUTES
# =============================================================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            session['username'] = user['username']
            
            # --- Capture and Log Device Info ---
            ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
            ip_address = ip_address.split(',')[0].strip() if ip_address else None

            log_conn = None
            try:
                log_conn = get_db_connection()
                log_conn.execute(
                    "INSERT INTO login_logs (username, ip_address, device_info) VALUES (?, ?, ?)",
                    (user['username'], ip_address, request.user_agent.string)
                )
                log_conn.commit()
            except Exception as e:
                print(f"Failed to log login: {e}")
            finally:
                if log_conn:
                    log_conn.close()
            # -----------------------------------

            return redirect(url_for('index'))
        else:
            flash("Invalid credentials. Please try again.")
            
    return render_template('login.html')


@app.route('/')
@login_required
def index():
    # 1. Fetch pre-cleaned data
    items = fetch_all_orders()
    items, filters = search_orders(items, request.args.get('q', ''), request.args.get('order_type', 'all'))
    active_tab = request.args.get('status', 'all' if filters['filters_active'] else 'open')
    if active_tab not in {'open', 'contacted', 'completed', 'cancelled', 'all'}:
        active_tab = 'all' if filters['filters_active'] else 'open'

    # 2. group data for tabbed view
    def group_data(data_list):
        groups = {}
        for item in data_list:
            # Keep different contacts, shops and order types separate even when
            # they share a name and date. Missing contacts stay separate too.
            key = (item['contact_id'] if item.get('contact_id') is not None else ('order', item['order_id']),
                   item['order_date_iso'], item['shop_name'], item['order_type'])
            if key not in groups:
                groups[key] = {
                    'contact_name': item['contact_name'],
                    'contact_phone': item['contact_phone_number'],
                    'contact_email': item['contact_email'],
                    'pedal_partner': item['pedal_partner_name'],
                    'order_date': item['order_date'],
                    'order_date_iso': item['order_date_iso'],
                    'order_type': item.get('order_type', 'Public'),
                    #'shop_name': item.get('shop_name', ''),
                    'shop_name': item.get('shop_location', ''),
                    'total_bikes': 0,
                    'recipients': []
                }
            groups[key]['total_bikes'] += 1
            groups[key]['recipients'].append(item)
        return list(groups.values())

    open_items = [i for i in items if i['order_status'] == 'Open']
    contacted_items = [i for i in items if i['order_status'] == 'Contacted']
    completed_items = [i for i in items if i['order_status'] == 'Completed']
    cancelled_items = [i for i in items if i['order_status'] == 'Cancelled']

    open_orders = sorted(group_data(open_items), key=lambda x: x['order_date_iso'])
    contacted_orders = sorted(group_data(contacted_items), key=lambda x: x['order_date_iso'])
    cancelled_orders = sorted(group_data(cancelled_items), key=lambda x: x['order_date_iso'], reverse=True)
    all_orders = sorted(group_data(items), key=lambda x: x['order_date_iso'], reverse=True)
    
    def get_max_pickup(group):
        dates = [r['pickup_date_iso'] for r in group['recipients'] if r['pickup_date_iso']]
        return max(dates) if dates else ''
    
    completed_orders = sorted(group_data(completed_items), key=get_max_pickup, reverse=True)

    status_groups = {
        'open': open_orders, 'contacted': contacted_orders, 'completed': completed_orders,
        'cancelled': cancelled_orders, 'all': all_orders,
    }
    status_counts = {status: sum(group['total_bikes'] for group in groups)
                     for status, groups in status_groups.items()}
    groups = status_groups[active_tab]
    page_size = 25
    page_count = max(1, (len(groups) + page_size - 1) // page_size)
    page = min(max(1, request.args.get('page', 1, type=int)), page_count)
    start = (page - 1) * page_size
    pagination = {'page': page, 'pages': page_count, 'total': len(groups),
                  'first': start + 1 if groups else 0, 'last': min(start + page_size, len(groups))}
    # Keep families together, but send only the current page of the selected tab.
    visible_groups = {status + '_orders': (groups[start:start + page_size] if status == active_tab else [])
                      for status in status_groups}

    return render_template(
        'index.html', 
        **visible_groups,
        status_counts=status_counts,
        pagination=pagination,
        today=datetime.now().strftime('%Y-%m-%d'),
        active_tab=active_tab,
        **filters,
    )

@app.route('/add', methods=('GET', 'POST'))
@login_required
def add():
    token = request.form.get('form_token', '') if request.method == 'POST' else form_token('staff-order')
    values, recipients = form_values(request.form if request.method == 'POST' else None)
    errors = {}
    with closing(get_db_connection()) as conn, conn:
        ensure_schema(conn)
        available_shops = shops(conn)
        if request.method == 'POST':
            key = check_token(token, 'staff-order')
            conn.execute('BEGIN IMMEDIATE')
            if existing_submission(conn, key):
                flash('This order was already saved. No duplicate was created.', 'info')
                return redirect(url_for('index'))
            values, recipients, phone, errors = validate(request.form, {s['shop_name'] for s in available_shops})
            if not errors:
                ids, _ = save_order(conn, values, recipients, phone, session['username'], key)
    if request.method == 'POST' and not errors:
        # Confirmation email is sent only after the entire submission commits.
        notifications = []
        for recipient in (recipients if values['contact_email'] else []):
            sent = send_email(to_email=values['contact_email'], subject="We received your bike request!",
                              template_name='order_received', recipient_name=recipient['recipient_name'],
                              shop_name=values['shop_name'])
            notifications.append(sent)
        flash(f'Order saved for {len(ids)} recipient(s).', 'success')
        email_feedback(notifications, 'Order saved. Confirmation email could not be sent.')
        return redirect(url_for('index'))
    return render_template('add.html', values=values, recipients=recipients, errors=errors,
                           form_token=token, shops=available_shops, heights=HEIGHTS,
                           order_types=TYPES, requester_mode=False), (400 if errors else 200)

def redirect_to_desk():
    """Keep the user's search and tab after an order action, using local URLs only."""
    params = {key: request.form['return_' + key] for key in ('q', 'order_type', 'status', 'page')
              if request.form.get('return_' + key)}
    return redirect(url_for('index', **params))


@app.route('/update_status/<int:order_id>', methods=['POST'])
@login_required
def update_status(order_id):
    new_status = request.form.get('new_status')
    if new_status not in {'Open', 'Contacted', 'Cancelled'}:
        abort(400, 'Invalid status. Use the pickup form to complete an order.')
    current_user = session.get('username', 'Unknown')
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    with closing(get_db_connection()) as conn, conn:
        conn.execute('BEGIN IMMEDIATE')
        order = conn.execute('''
        SELECT o.order_status, c.contact_email, r.recipient_name 
        FROM orders o
        LEFT JOIN contacts c ON o.contact_id = c.contact_id
        LEFT JOIN recipients r ON o.recipient_id = r.recipient_id
        WHERE o.order_id = ?
        ''', (order_id,)).fetchone()
        if order is None:
            abort(404)
        if order['order_status'] == new_status:
            return redirect_to_desk()
        allowed_transitions = {
            'Open': {'Contacted', 'Cancelled'},
            'Contacted': {'Cancelled'},
            'Cancelled': {'Open'},
        }
        if new_status not in allowed_transitions.get(order['order_status'], set()):
            abort(409, 'This order has changed. Reload Order Desk before taking another action.')
        conn.execute('''
        UPDATE orders 
        SET order_status = ?, last_status = order_status, last_updated_by = ?, last_updated_date = ?
        WHERE order_id = ?
        ''', (new_status, current_user, current_time, order_id))

    if new_status == 'Contacted' and order['order_status'] != 'Contacted':
        pickup_deadline = (datetime.now() + timedelta(days=7)).strftime('%m/%d/%Y')
        sent = send_email(
            to_email=order['contact_email'],
            subject="Your bike is ready for pickup!",
            template_name="pickup_ready",
            recipient_name=order['recipient_name'],
            deadline=pickup_deadline
        )
        email_feedback([sent], 'Status saved. Pickup email could not be sent.')

    flash(f'Order #{order_id} moved to {new_status}.', 'success')
    return redirect_to_desk()

@app.route('/fulfill/<int:order_id>', methods=['POST'])
@login_required
def fulfill(order_id):
    date_picked_up = request.form.get('date_picked_up')
    bike_tag = request.form.get('bike_tag')
    current_user = session.get('username', 'Unknown') 
    try:
        datetime.strptime(date_picked_up or '', '%Y-%m-%d')
        bike_tag = int(bike_tag)
        if bike_tag <= 0:
            raise ValueError
    except (TypeError, ValueError):
        abort(400, 'A pickup date and positive whole-number bike tag are required.')
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Note: Using pickup_date to align with index SQL schema
    with closing(get_db_connection()) as conn, conn:
        conn.execute('BEGIN IMMEDIATE')
        order = conn.execute('''SELECT order_status, pickup_date, bike_tag
            FROM orders WHERE order_id = ?''', (order_id,)).fetchone()
        if order is None:
            abort(404)
        if order['order_status'] == 'Completed' and order['pickup_date'] == date_picked_up and order['bike_tag'] == bike_tag:
            # A double click or retry must not overwrite the original audit trail.
            return redirect_to_desk()
        if order['order_status'] != 'Contacted':
            abort(409, 'Only Contacted orders can be picked up. Reload Order Desk to see this order’s current status.')
        conn.execute('''
        UPDATE orders 
        SET pickup_date = ?, bike_tag = ?, last_status = order_status,
            order_status = 'Completed', last_updated_by = ?, last_updated_date = ?
        WHERE order_id = ?
        ''', (date_picked_up, bike_tag, current_user, current_time, order_id))
    
    flash(f'Order #{order_id} completed. Pickup date and bike tag saved.', 'success')
    return redirect_to_desk()

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/api/search_contacts')
@login_required
def search_contacts():
    query = request.args.get('q', '').strip()
    if len(query) < 2:
        return jsonify([]) # Don't search until at least 2 characters are typed
    
    conn = get_db_connection()
    # Using LIKE with a wildcard at the end to match prefixes
    results = conn.execute(
        "SELECT DISTINCT contact_name FROM contacts WHERE contact_name LIKE ? ORDER BY contact_name LIMIT 10", 
        (f"{query}%",)
    ).fetchall()
    conn.close()
    
    return jsonify([row['contact_name'] for row in results])

@app.route('/api/search_partners')
@login_required
def search_partners():
    query = request.args.get('q', '').strip()
    if len(query) < 2:
        return jsonify([])
    
    conn = get_db_connection()
    results = conn.execute(
        "SELECT DISTINCT pedal_partner_name FROM pedal_partners WHERE pedal_partner_name LIKE ? ORDER BY pedal_partner_name LIMIT 10", 
        (f"{query}%",)
    ).fetchall()
    conn.close()
    
    return jsonify([row['pedal_partner_name'] for row in results])


@app.route('/dashboard')
@login_required
def dashboard():
    current_year = datetime.now().year
    selected_year = request.args.get('year', str(current_year))
    if (len(selected_year) != 4 or not selected_year.isascii()
            or not selected_year.isdigit() or int(selected_year) < 1):
        selected_year = str(current_year)
        flash('Invalid year. Showing the current year instead.', 'warning')

    if not request.args:
        selected_shops = ['B', 'R', 'S']
        selected_months = list(range(1, 13))
    else:
        selected_shops = sorted(set(request.args.getlist('shop')) & {'B', 'R', 'S'})
        month_values = request.args.getlist('month')
        valid_months = {str(m): m for m in range(1, 13)}
        valid_months.update({f'{m:02d}': m for m in range(1, 13)})
        selected_months = sorted({valid_months[m] for m in month_values if m in valid_months})
        if any(m not in valid_months for m in month_values):
            flash('Invalid month filters were ignored.', 'warning')

    monthly_counts = [0] * 12
    last_year_total = 0
    last_year = f'{int(selected_year) - 1:04d}'
    with closing(get_db_connection()) as conn:
        year_rows = conn.execute('''
            SELECT DISTINCT strftime('%Y', pickup_date) AS year
            FROM orders WHERE order_status = 'Completed'
        ''').fetchall()
        available_years = sorted(
            {str(current_year - offset) for offset in range(3)} | {selected_year}
            | {row['year'] for row in year_rows if row['year'] and row['year'] != '0000'},
            reverse=True,
        )
        if selected_shops and selected_months:
            shop_placeholders = ','.join('?' for _ in selected_shops)
            month_placeholders = ','.join('?' for _ in selected_months)
            # One order line represents one bike. Joining recipients can multiply
            # legacy rows or hide completed orders whose recipient link is missing.
            rows = conn.execute(f'''
                SELECT strftime('%Y', pickup_date) AS year,
                       strftime('%m', pickup_date) AS month, COUNT(*) AS total
                FROM orders
                WHERE order_status = 'Completed'
                  AND strftime('%Y', pickup_date) IN (?, ?)
                  AND shop_name IN ({shop_placeholders})
                  AND strftime('%m', pickup_date) IN ({month_placeholders})
                GROUP BY year, month
            ''', [selected_year, last_year] + selected_shops
                + [f'{m:02d}' for m in selected_months]).fetchall()
            for row in rows:
                if row['year'] == selected_year:
                    monthly_counts[int(row['month']) - 1] = row['total']
                else:
                    last_year_total += row['total']

    return render_template(
        'dashboard.html',
        monthly_counts=monthly_counts,
        this_year_total=sum(monthly_counts),
        last_year_total=last_year_total,
        selected_year=selected_year,
        selected_shops=selected_shops,
        selected_months=selected_months,
        available_years=available_years,
    )

@app.route('/explorer')
@login_required
def explorer():
    items = fetch_all_orders()
    items, filters = search_orders(items, request.args.get('q', ''), request.args.get('order_type', 'all'))
    return render_template('explorer.html', items=items, **filters)

# =============================================================================
# BACKGROUND TASKS
# =============================================================================
@scheduler.task('cron', id='daily_pickup_reminder', hour=9, minute=0)
def check_pickup_deadlines():
    with app.app_context():
        if not app.config.get('EMAIL_REMINDERS_ENABLED', False):
            return
        app.logger.info('Running daily pickup reminder check.')
        conn = get_db_connection()
        
        target_date_str = (datetime.now() - timedelta(days=6)).strftime('%Y-%m-%d')
        
        orders = conn.execute('''
            SELECT o.last_updated_date, c.contact_email, r.recipient_name 
            FROM orders o
            JOIN contacts c ON o.contact_id = c.contact_id
            JOIN recipients r ON o.recipient_id = r.recipient_id
            WHERE o.order_status = 'Contacted' 
            AND o.last_updated_date LIKE ?
        ''', (f"{target_date_str}%",)).fetchall()
        
        for order in orders:
            base_date = datetime.strptime(order['last_updated_date'].split()[0], '%Y-%m-%d')
            deadline = (base_date + timedelta(days=7)).strftime('%m/%d/%Y')
            
            send_email(
                to_email=order['contact_email'],
                subject="URGENT: Pick up your bike tomorrow!",
                template_name="pickup_reminder",
                recipient_name=order['recipient_name'],
                deadline=deadline
            )
            
        conn.close()

# =============================================================================
# VERSION DETAILS
# =============================================================================

def get_git_revision_short_hash():
    try:
        return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('ascii').strip()
    except Exception:
        return "dev"

@app.context_processor
def inject_global_vars():
    return dict(
        app_version=f"v1.0.1 ({get_git_revision_short_hash()})"
    )


# =============================================================================
# EXECUTION
# =============================================================================
if __name__ == '__main__':
    app.run(debug=True, port=5003)
