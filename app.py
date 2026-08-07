"""
Main Application Entry Point (app.py)
-------------------------------------
Handles route definitions and background scheduling. 
Database logic, utilities, and configurations are imported from external modules.
"""

import os
from datetime import datetime, timedelta
from functools import wraps
import subprocess

from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash
from flask_apscheduler import APScheduler
from dotenv import load_dotenv

# for search api
from flask import jsonify

# Load environment variables
load_dotenv()

# --- Local Module Imports ---
from database import get_db_connection
from utils import send_email, format_date, format_phone, clean_int, unformat_phone, fetch_all_orders


# =============================================================================
# APP CONFIGURATION & SCHEDULER
# =============================================================================
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'loremipsum')
app.config['DB_PATH'] = os.getenv('DB_PATH', 'data/processed/pif.db')

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

    # 2. group data for tabbed view
    def group_data(data_list):
        groups = {}
        for item in data_list:
            key = f"{item['contact_name']}_{item['order_date']}"
            if key not in groups:
                groups[key] = {
                    'contact_name': item['contact_name'],
                    'contact_phone': format_phone(item['contact_phone_number']),
                    'contact_email': item['contact_email'],
                    'pedal_partner': item['pedal_partner_name'],
                    'order_date': format_date(item['order_date']),
                    'order_type': item.get('order_type', 'Public'),
                    #'shop_name': item.get('shop_name', ''),
                    'shop_name': item.get('shop_location', ''),
                    'total_bikes': 0,
                    'recipients': []
                }
            groups[key]['total_bikes'] += 1
            item['age'] = clean_int(item['age'])
            item['bike_tag'] = clean_int(item.get('bike_tag'))
            item['date_picked_up'] = format_date(item['date_picked_up'])
            groups[key]['recipients'].append(item)
        return list(groups.values())

    open_items = [i for i in items if i['order_status'] == 'Open']
    contacted_items = [i for i in items if i['order_status'] == 'Contacted']
    completed_items = [i for i in items if i['order_status'] == 'Completed']
    cancelled_items = [i for i in items if i['order_status'] == 'Cancelled']

    open_orders = sorted(group_data(open_items), key=lambda x: x['order_date'])
    contacted_orders = sorted(group_data(contacted_items), key=lambda x: x['order_date'])
    cancelled_orders = sorted(group_data(cancelled_items), key=lambda x: x['order_date'], reverse=True)
    all_orders = sorted(group_data(items), key=lambda x: x['order_date'], reverse=True)
    
    def get_max_pickup(group):
        dates = [r['date_picked_up'] for r in group['recipients'] if r['date_picked_up']]
        return max(dates) if dates else ''
    
    completed_orders = sorted(group_data(completed_items), key=get_max_pickup, reverse=True)

    return render_template(
        'index.html', 
        open_orders=open_orders, 
        contacted_orders=contacted_orders,
        completed_orders=completed_orders, 
        cancelled_orders=cancelled_orders,
        all_orders=all_orders,
        today=datetime.now().strftime('%Y-%m-%d')
    )

@app.route('/add', methods=('GET', 'POST'))
@login_required
def add():
    if request.method == 'POST':
        contact_name = request.form.get('contact_name', '')
        contact_phone = unformat_phone(request.form.get('contact_phone_number', ''))
        contact_email = request.form.get('contact_email', '')
        pedal_partner = request.form.get('pedal_partner_name', '').strip()
        order_date = request.form.get('order_date', '')
        shop_name = request.form.get('shop_name', '')
        
        # Order Type Logic Translation
        order_type = request.form.get('order_type', 'Public')
        
        # Safety fallback: If marked as 'Pedal Partner' but the name field was left blank, revert to 'Public'
        if order_type == 'Pedal Partner' and not pedal_partner:
            order_type = 'Public'

        recipients = request.form.getlist('recipient_name[]')
        bike_styles = request.form.getlist('bike_style_preference[]')
        ages = request.form.getlist('age[]')
        heights = request.form.getlist('height[]')
        first_choices = request.form.getlist('bike_type_first_choice[]')
        second_choices = request.form.getlist('bike_type_second_choice[]')
        notes_list = request.form.getlist('notes[]')

        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn = get_db_connection()
        
        # 1. Manage Contact
        conn.execute('''INSERT OR IGNORE INTO contacts (contact_name, contact_phone_number, contact_email) 
                        VALUES (?, ?, ?)''', (contact_name, contact_phone, contact_email))
        contact_id = conn.execute('SELECT contact_id FROM contacts WHERE contact_email = ? AND contact_name = ?', 
                                  (contact_email, contact_name)).fetchone()['contact_id']

        # 2. Manage Pedal Partner
        pedal_partner_id = None
        if pedal_partner:
            conn.execute('INSERT OR IGNORE INTO pedal_partners (pedal_partner_name) VALUES (?)', (pedal_partner,))
            pp_row = conn.execute('SELECT pedal_partner_id FROM pedal_partners WHERE pedal_partner_name = ?', (pedal_partner,)).fetchone()
            if pp_row:
                pedal_partner_id = pp_row['pedal_partner_id']

        # 3. Manage Shop
        conn.execute('INSERT OR IGNORE INTO shops (shop_name) VALUES (?)', (shop_name,))

        # 4. Insert Recipients and Orders
        for i in range(len(recipients)):
            conn.execute('''INSERT INTO recipients (recipient_name, age, height, bike_style_preference) 
                            VALUES (?, ?, ?, ?)''', 
                         (recipients[i], ages[i], heights[i], bike_styles[i]))
            recipient_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]

            conn.execute('''
                INSERT INTO orders (
                    contact_id, recipient_id, shop_name, pedal_partner_id,
                    order_date, order_type, order_status, last_status, last_updated_date
                ) VALUES (?, ?, ?, ?, ?, ?, 'Open', 'Open', ?)
            ''', (contact_id, recipient_id, shop_name, pedal_partner_id, order_date, order_type, current_time))
        
            send_email(
                to_email=contact_email, 
                subject="We received your bike request!",
                template_name="order_received",
                recipient_name=recipients[i],
                shop_name=shop_name
            )
        
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    
    return render_template('add.html')

@app.route('/update_status/<int:order_id>', methods=['POST'])
@login_required
def update_status(order_id):
    new_status = request.form.get('new_status')
    current_user = session.get('username', 'Unknown')
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    conn = get_db_connection()
    order = conn.execute('''
        SELECT o.order_status, c.contact_email, r.recipient_name 
        FROM orders o
        JOIN contacts c ON o.contact_id = c.contact_id
        JOIN recipients r ON o.recipient_id = r.recipient_id
        WHERE o.order_id = ?
    ''', (order_id,)).fetchone()
    
    conn.execute('''
        UPDATE orders 
        SET order_status = ?, last_status = order_status, handled_by = ?, last_updated_date = ?
        WHERE order_id = ?
    ''', (new_status, current_user, current_time, order_id))
    conn.commit()
    conn.close()

    if new_status == 'Contacted' and order['order_status'] != 'Contacted':
        pickup_deadline = (datetime.now() + timedelta(days=7)).strftime('%m/%d/%Y')
        send_email(
            to_email=order['contact_email'],
            subject="Your bike is ready for pickup!",
            template_name="pickup_ready",
            recipient_name=order['recipient_name'],
            deadline=pickup_deadline
        )

    return redirect(url_for('index'))

@app.route('/fulfill/<int:order_id>', methods=['POST'])
@login_required
def fulfill(order_id):
    date_picked_up = request.form.get('date_picked_up')
    bike_tag = request.form.get('bike_tag')
    current_user = session.get('username', 'Unknown') 
    
    conn = get_db_connection()
    # Note: Using pickup_date to align with index SQL schema
    conn.execute('''
        UPDATE orders 
        SET pickup_date = ?, bike_tag = ?, order_status = 'Completed', handled_by = ? 
        WHERE order_id = ?
    ''', (date_picked_up, bike_tag, current_user, order_id))
    conn.commit()
    conn.close()
    
    return redirect(url_for('index'))

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
    conn = get_db_connection()
    
    # Determine if this is a form submission or initial load
    if not request.args:
        selected_year = '2026'
        selected_shops = ['B', 'R', 'S']
        selected_months = [str(i).zfill(2) for i in range(1, 13)] # '01' to '12'
    else:
        selected_year = request.args.get('year', '2026')
        selected_shops = request.args.getlist('shop')
        # Pad month numbers with leading zeros for SQLite strftime compatibility
        selected_months = [m.zfill(2) for m in request.args.getlist('month')]

    # Fallback if filters are completely cleared (prevent SQL errors)
    if not selected_shops or not selected_months:
        monthly_counts = [0] * 12
        this_year_total = 0
        last_year_total = 0
    else:
        shop_placeholders = ','.join(['?'] * len(selected_shops))
        month_placeholders = ','.join(['?'] * len(selected_months))
        
        # 1. Monthly Chart Data (Groups by month)
        chart_query = f'''
            SELECT strftime('%m', o.order_date) as month, COUNT(r.recipient_id) as total_bikes
            FROM orders o
            JOIN recipients r ON o.recipient_id = r.recipient_id
            WHERE strftime('%Y', o.order_date) = ? 
              AND o.shop_name IN ({shop_placeholders})
              AND strftime('%m', o.order_date) IN ({month_placeholders})
            GROUP BY month
            ORDER BY month
        '''
        params = [selected_year] + selected_shops + selected_months
        chart_data_raw = conn.execute(chart_query, params).fetchall()
        
        monthly_counts = [0] * 12
        for row in chart_data_raw:
            if row['month']:
                monthly_counts[int(row['month']) - 1] = row['total_bikes']

        # 2. Totals Query (Reusable for This Year and Last Year)
        totals_query = f'''
            SELECT COUNT(r.recipient_id) as total
            FROM orders o
            JOIN recipients r ON o.recipient_id = r.recipient_id
            WHERE strftime('%Y', o.order_date) = ? 
              AND o.shop_name IN ({shop_placeholders})
              AND strftime('%m', o.order_date) IN ({month_placeholders})
        '''
        
        # This Year
        this_year_total = conn.execute(totals_query, params).fetchone()['total'] or 0
        
        # Last Year
        last_year = str(int(selected_year) - 1)
        last_year_params = [last_year] + selected_shops + selected_months
        last_year_total = conn.execute(totals_query, last_year_params).fetchone()['total'] or 0
        
    conn.close()

    return render_template(
        'dashboard.html',
        monthly_counts=monthly_counts,
        this_year_total=this_year_total,
        last_year_total=last_year_total,
        selected_year=selected_year,
        selected_shops=selected_shops,
        selected_months=[int(m) for m in selected_months] # Converted to int for easier Jinja template checking
    )

@app.route('/explorer')
@login_required
def explorer():
    items = fetch_all_orders()
    return render_template('explorer.html', items=items)

# =============================================================================
# BACKGROUND TASKS
# =============================================================================
@scheduler.task('cron', id='daily_pickup_reminder', hour=9, minute=0)
def check_pickup_deadlines():
    with app.app_context():
        print("Running daily pickup reminder check...")
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
    # DB upgrade removed here — assume you run `python manage_db.py` on deployments
    app.run(debug=True, port=5003)