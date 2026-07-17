import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime
import re
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

# initialize app & database path
app = Flask(__name__)
app.secret_key = 'loremipsum'
DB_PATH = "data/processed/pif.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# --- AUTO-UPGRADE DATABASE ---
def upgrade_db():
    conn = get_db_connection()
    try:
        # Tries to add the status column. If it exists, it safely ignores this.
        conn.execute("ALTER TABLE orders_50 ADD COLUMN status TEXT DEFAULT 'Open'")
        # Migrate old completed orders to the new status
        conn.execute("UPDATE orders_50 SET status = 'Completed' WHERE date_picked_up IS NOT NULL AND date_picked_up != ''")
        conn.commit()
    except sqlite3.OperationalError:
        pass # Column already exists

    # --- NEW: Add handled_by column ---
    try:
        conn.execute("ALTER TABLE orders_50 ADD COLUMN handled_by TEXT DEFAULT 'System'")
        conn.commit()
    except sqlite3.OperationalError:
        pass # Column already exists
    conn.close()

# --- AUTHENTICATION SETUP ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- HELPER FUNCTIONS ---
def format_date(d_str):
    if not d_str: return ""
    try:
        clean_date = str(d_str).split()[0].split('T')[0]
        return datetime.strptime(clean_date, '%Y-%m-%d').strftime('%m/%d/%Y')
    except:
        return d_str 

def format_phone(p_str):
    if not p_str: return ""
    digits = re.sub(r'\D', '', str(p_str))
    if len(digits) == 10:
        return f"({digits[:3]})-{digits[3:6]}-{digits[6:]}"
    return p_str

def clean_int(val):
    if val in [None, '', 'nan', 'NaN']: return ""
    try:
        return str(int(float(val)))
    except:
        return str(val)

# --- ROUTES ---
@app.route('/')
@login_required
def index():
    conn = get_db_connection()
    # Pull the hidden native rowid alongside the rest of your data
    raw_items = conn.execute('SELECT rowid, * FROM orders_50').fetchall()
    conn.close()

    items = []
    for row in raw_items:
        row_dict = dict(row)
        
        # Force the frontend to use the indestructible rowid
        row_dict['order_id'] = row_dict['rowid']
        
        # Ensure status exists for old records
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

    # Filter data into the 4 buckets based on Status
    open_items = [i for i in items if i['status'] == 'Open']
    contacted_items = [i for i in items if i['status'] == 'Contacted']
    completed_items = [i for i in items if i['status'] == 'Completed']
    cancelled_items = [i for i in items if i['status'] == 'Cancelled']

    # Group and Sort (Contacted = Earliest First)
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
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    return render_template('add.html')

@app.route('/update_status/<int:order_id>', methods=['POST'])
@login_required
def update_status(order_id):
    new_status = request.form.get('new_status')
    current_user = session.get('username', 'Unknown') # Get the active user
    
    conn = get_db_connection()
    conn.execute('''
        UPDATE orders_50 
        SET status = ?, handled_by = ? 
        WHERE rowid = ?
    ''', (new_status, current_user, order_id))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/fulfill/<int:order_id>', methods=['POST'])
@login_required
def fulfill(order_id):
    date_picked_up = request.form.get('date_picked_up')
    bike_tag = request.form.get('bike_tag')
    current_user = session.get('username', 'Unknown') # Get the active user
    
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

        # Check if user exists and password matches
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

if __name__ == '__main__':
    upgrade_db() # Runs safely once on startup
    app.run(debug=True)