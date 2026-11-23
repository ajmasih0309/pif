"""Pickup timing and reminder receipts, independent of workshop data."""
from datetime import datetime, timedelta, timezone
from math import ceil
from zoneinfo import ZoneInfo

from order_search import canonical_order_type

LOCAL_ZONE = ZoneInfo('America/Chicago')


def now_utc():
    return datetime.now(timezone.utc)


def parse_contact_time(value):
    try:
        parsed = datetime.fromisoformat(str(value))
        return parsed.replace(tzinfo=LOCAL_ZONE) if parsed.tzinfo is None else parsed
    except (ValueError, TypeError):
        return None


def pickup_window(order_type, contacted_at, now=None):
    days = {'Public': 7, 'Pedal Partner': 28}.get(canonical_order_type(order_type))
    if days is None:
        return {'deadline': None, 'label': 'No pickup deadline', 'overdue': False}
    contacted = parse_contact_time(contacted_at)
    if contacted is None:
        return {'deadline': None, 'label': 'Contact date unavailable — check pickup deadline', 'overdue': False}
    deadline = contacted.astimezone(LOCAL_ZONE) + timedelta(days=days)
    seconds = (deadline.astimezone(timezone.utc) - (now or now_utc())).total_seconds()
    if seconds <= 0:
        label = 'Pickup overdue'
    elif seconds <= 86400:
        hours = ceil(seconds / 3600)
        label = f"{hours} {'hour' if hours == 1 else 'hours'} left"
    else:
        label = f'{ceil(seconds / 86400)} days left'
    return {'deadline': deadline, 'label': label, 'overdue': seconds <= 0}


def ensure_pickup_schema(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS order_pickup_tracking (
        order_id INTEGER PRIMARY KEY, contacted_at TEXT NOT NULL)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS pickup_reminder_delivery (
        order_id INTEGER NOT NULL, contacted_at TEXT NOT NULL, deadline TEXT NOT NULL,
        mode TEXT NOT NULL, claimed_at TEXT, sent_at TEXT,
        PRIMARY KEY (order_id, contacted_at, deadline, mode))''')


def contact_times(conn):
    exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='order_pickup_tracking'").fetchone()
    return dict(conn.execute('SELECT order_id,contacted_at FROM order_pickup_tracking')) if exists else {}


def record_contact(conn, order_id, timestamp):
    ensure_pickup_schema(conn)
    conn.execute('INSERT OR REPLACE INTO order_pickup_tracking VALUES (?,?)', (order_id, timestamp))


def send_due_reminders(conn, send, mode, now=None):
    """Claim once per contact cycle/mode; retry failures while still before expiry."""
    now = now or now_utc()
    ensure_pickup_schema(conn)
    conn.commit()
    tracked = contact_times(conn)
    rows = conn.execute('''SELECT o.order_id,o.order_type,o.last_updated_date,
        c.contact_email,r.recipient_name FROM orders o
        LEFT JOIN contacts c ON c.contact_id=o.contact_id
        LEFT JOIN recipients r ON r.recipient_id=o.recipient_id
        WHERE o.order_status='Contacted' ''').fetchall()
    for row in rows:
        if not (row['contact_email'] or '').strip():
            continue
        contact = tracked.get(row['order_id'], row['last_updated_date'])
        deadline = pickup_window(row['order_type'], contact, now)['deadline']
        if deadline is None:
            continue
        due = deadline.astimezone(timezone.utc)
        if not due - timedelta(hours=24) <= now < due:
            continue
        key = (row['order_id'], contact, deadline.isoformat(), mode)
        with conn:
            conn.execute('BEGIN IMMEDIATE')
            current = conn.execute('SELECT order_status FROM orders WHERE order_id=?', (row['order_id'],)).fetchone()
            fresh_contact = contact_times(conn).get(row['order_id'], contact)
            if not current or current['order_status'] != 'Contacted' or fresh_contact != contact:
                continue
            receipt = conn.execute('''SELECT claimed_at,sent_at FROM pickup_reminder_delivery
                WHERE order_id=? AND contacted_at=? AND deadline=? AND mode=?''', key).fetchone()
            if receipt and (receipt['sent_at'] or (parse_contact_time(receipt['claimed_at']) and
                    parse_contact_time(receipt['claimed_at']) > now - timedelta(minutes=30))):
                continue
            conn.execute('INSERT OR IGNORE INTO order_pickup_tracking VALUES (?,?)', (row['order_id'], contact))
            conn.execute('INSERT OR REPLACE INTO pickup_reminder_delivery VALUES (?,?,?,?,?,NULL)', (*key, now.isoformat()))
        # Mail happens outside the write transaction and never changes order status.
        try:
            result = send(to_email=row['contact_email'], subject='Reminder: your bike pickup deadline is approaching',
                          template_name='pickup_reminder', recipient_name=row['recipient_name'],
                          deadline=deadline.strftime('%m/%d/%Y at %I:%M %p %Z'))
            delivered = getattr(result, 'status', None) == ('sent' if mode == 'live' else 'test')
        except Exception:
            delivered = False
        with conn:
            conn.execute('''UPDATE pickup_reminder_delivery SET claimed_at=NULL,sent_at=?
                WHERE order_id=? AND contacted_at=? AND deadline=? AND mode=?''',
                (now.isoformat() if delivered else None, *key))
