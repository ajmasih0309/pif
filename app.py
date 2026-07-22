"""
Main Application Entry Point (app.py)
-------------------------------------
Handles route definitions and background scheduling. 
Database logic, utilities, and configurations are imported from external modules.
"""

import os
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash
from flask_apscheduler import APScheduler
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- Local Module Imports ---
from database import get_db_connection
from utils import send_email, format_date, format_phone, clean_int


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
@app.route('/')
@login_required
def index():
    conn = get_db_connection()
    raw_items = conn.execute('SELECT rowid, * FROM orders_50').fetchall()
    conn.close()

    items = []
    for row in raw_items:
        row_dict = dict(row)
        row_dict['order_id'] = row_dict['rowid']
        
        # Fallback for legacy records missing a status
        if not row_dict.get('status'):
            row_dict['status'] = 'Completed' if row_dict.get('date_picked_up') else 'Open'
            
        items.append(row_dict)

    def group_data(data_list):
        groups = {}
        for item in data_list:
            key = f"{item['contact_email']}_{item['order_date']}"
            if key not in groups:
                groups[key] = {
                    'contact_name': item['contact_name'],
                    'contact_phone': format_phone(item['contact_phone_number']),
                    'contact_email': item['contact_email'],
                    'pedal_partner': item['pedal_partner_name'],
                    'order_date': format_date(item['order_date']),
                    'order_type': item.get('order_type', 'Standard'),
                    'shop_name': item['shop_name'],
                    'total_bikes': 0,
                    'recipients': []
                }
            groups[key]['total_bikes'] += 1
            item['age'] = clean_int(item['age'])
            item['bike_tag'] = clean_int(item['bike_tag'])
            item['date_picked_up'] = format_date(item['date_picked_up'])
            groups[key]['recipients'].append(item)
        return list(groups.values())

    open_items = [i for i in items if i['status'] == 'Open']
    contacted_items = [i for i in items if i['status'] == 'Contacted']
    completed_items = [i for i in items if i['status'] == 'Completed']
    cancelled_items = [i for i in items if i['status'] == 'Cancelled']

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
        contact_phone = request.form.get('contact_phone_number', '')
        contact_email = request.form.get('contact_email', '')
        pedal_partner = request.form.get('pedal_partner_name', '')
        order_date = request.form.get('order_date', '')
        shop_name = request.form.get('shop_name', '')
        order_type = request.form.get('order_type', 'Standard')

        recipients = request.form.getlist('recipient_name[]')
        bike_styles = request.form.getlist('bike_style_preference[]')
        ages = request.form.getlist('age[]')
        heights = request.form.getlist('height[]')
        first_choices = request.form.getlist('bike_type_first_choice[]')
        second_choices = request.form.getlist('bike_type_second_choice[]')
        notes_list = request.form.getlist('notes[]')

        conn = get_db_connection()
        for i in range(len(recipients)):
            conn.execute('''
                INSERT INTO orders_50 (
                    contact_name, contact_phone_number, contact_email, pedal_partner_name,
                    order_date, order_type, shop_name, 
                    recipient_name, bike_style_preference, age, height,
                    bike_type_first_choice, bike_type_second_choice, notes, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Open')
            ''', (
                contact_name, contact_phone, contact_email, pedal_partner,
                order_date, order_type, shop_name, 
                recipients[i], bike_styles[i], ages[i], heights[i],
                first_choices[i], second_choices[i], notes_list[i]
            ))
        
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
    order = conn.execute("SELECT * FROM orders_50 WHERE rowid = ?", (order_id,)).fetchone()
    
    conn.execute('''
        UPDATE orders_50 
        SET status = ?, last_status = status, handled_by = ?, last_updated_date = ?
        WHERE rowid = ?
    ''', (new_status, current_user, current_time, order_id))
    conn.commit()
    conn.close()

    if new_status == 'Contacted' and order['status'] != 'Contacted':
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
    conn.execute('''
        UPDATE orders_50 
        SET date_picked_up = ?, bike_tag = ?, status = 'Completed', handled_by = ? 
        WHERE rowid = ?
    ''', (date_picked_up, bike_tag, current_user, order_id))
    conn.commit()
    conn.close()
    
    return redirect(url_for('index'))

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
            return redirect(url_for('index'))
        else:
            flash("Invalid credentials. Please try again.")
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

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
            SELECT * FROM orders_50 
            WHERE status = 'Contacted' 
            AND last_updated_date LIKE ?
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
# EXECUTION
# =============================================================================
if __name__ == '__main__':
    # DB upgrade removed here — assume you run `python manage_db.py` on deployments
    app.run(debug=True)