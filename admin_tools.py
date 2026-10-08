"""Local maintenance operations. Never import the web app or trigger email/jobs."""

from contextlib import closing
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from uuid import uuid4


ORDER_FIELDS = {'notes', 'shop_name', 'pickup_date', 'bike_tag',
                'bike_type_first_choice', 'bike_type_second_choice'}
BIKE_FIELDS = {'recorded_at', 'shop_name', 'bike_tag', 'make', 'model', 'colour',
               'wheel_size', 'bike_type', 'volunteer_name'}
TAG_KEY_SQL = "CASE WHEN bike_tag <> '' AND bike_tag NOT GLOB '*[^0-9]*' THEN COALESCE(NULLIF(ltrim(bike_tag, '0'), ''), '0') ELSE bike_tag END"
SCHEMA = (
    'CREATE UNIQUE INDEX IF NOT EXISTS ux_shops_shop_name ON shops(shop_name)',
    '''CREATE TABLE IF NOT EXISTS bike_inventory (
        inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
        recorded_at TEXT,
        shop_name TEXT NOT NULL REFERENCES shops(shop_name),
        bike_tag TEXT NOT NULL UNIQUE CHECK(length(trim(bike_tag)) > 0),
        make TEXT, model TEXT, colour TEXT, wheel_size TEXT, bike_type TEXT,
        created_at TEXT NOT NULL
    )''',
    f'CREATE UNIQUE INDEX IF NOT EXISTS ux_inventory_canonical_tag ON bike_inventory ({TAG_KEY_SQL})',
    '''CREATE TABLE IF NOT EXISTS volunteers (
        volunteer_id INTEGER PRIMARY KEY,
        volunteer_name TEXT NOT NULL,
        volunteer_email TEXT,
        volunteer_phone_number TEXT,
        joined_on TEXT,
        is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1))
    )''',
    '''CREATE TABLE IF NOT EXISTS bike_contributions (
        contribution_id INTEGER PRIMARY KEY AUTOINCREMENT,
        inventory_id INTEGER NOT NULL REFERENCES bike_inventory(inventory_id),
        volunteer_id INTEGER REFERENCES volunteers(volunteer_id),
        recorded_name TEXT,
        recorded_at TEXT,
        source_key TEXT UNIQUE,
        source_sheet TEXT,
        source_row INTEGER,
        notes TEXT
    )''',
    'CREATE INDEX IF NOT EXISTS ix_bike_contributions_inventory ON bike_contributions(inventory_id)',
    '''CREATE TABLE IF NOT EXISTS admin_changes (
        change_id INTEGER PRIMARY KEY AUTOINCREMENT,
        changed_at TEXT NOT NULL, actor TEXT NOT NULL, reason TEXT NOT NULL,
        entity TEXT NOT NULL, entity_id TEXT NOT NULL,
        before_json TEXT NOT NULL, after_json TEXT NOT NULL
    )''',
    '''CREATE TABLE IF NOT EXISTS volunteer_hours (
        time_log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        volunteer_id INTEGER NOT NULL REFERENCES volunteers(volunteer_id),
        work_date TEXT NOT NULL,
        minutes INTEGER NOT NULL CHECK(typeof(minutes) = 'integer' AND minutes BETWEEN 1 AND 1440),
        shop_name TEXT REFERENCES shops(shop_name),
        activity TEXT, notes TEXT,
        created_at TEXT NOT NULL, created_by TEXT NOT NULL,
        updated_at TEXT NOT NULL, updated_by TEXT NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        voided_at TEXT, void_reason TEXT
    )''',
    'CREATE INDEX IF NOT EXISTS ix_volunteer_hours_date ON volunteer_hours(work_date, volunteer_id)',
    '''CREATE TABLE IF NOT EXISTS workshop_submissions (
        submission_key TEXT PRIMARY KEY,
        entity TEXT NOT NULL, entity_id INTEGER NOT NULL, created_at TEXT NOT NULL
    )''',
)


def connect(path, writable=False):
    path = Path(path).resolve(strict=True)
    conn = sqlite3.connect(path.as_uri() + ('?mode=rw' if writable else '?mode=ro'), uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    return conn


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def fingerprint(row):
    return hashlib.sha256(encoded(row).encode()).hexdigest()


def read_order(conn, order_id):
    row = conn.execute('SELECT * FROM orders WHERE order_id=?', (order_id,)).fetchone()
    if row is None:
        raise ValueError('Order not found.')
    return dict(row)


def valid_shop(conn, value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('A shop code is required.')
    value = value.strip()
    if conn.execute('SELECT COUNT(*) FROM shops WHERE shop_name=?', (value,)).fetchone()[0] != 1:
        raise ValueError('Shop must match exactly one existing shop code.')
    return value


def clean_fields(changes, allowed):
    if not isinstance(changes, dict) or not changes or set(changes) - allowed:
        raise ValueError('Supply a nonempty JSON object using supported fields: ' + ', '.join(sorted(allowed)))
    cleaned = {}
    for key, value in changes.items():
        if value is not None and not isinstance(value, str):
            raise ValueError(f'{key} must be text or null (identifiers must be quoted).')
        if value is not None and len(value) > (10000 if key == 'notes' else 200):
            raise ValueError(f'{key} is too long.')
        cleaned[key] = value.strip() if value is not None else None
    return cleaned


def order_preview(conn, order_id, changes):
    before = read_order(conn, order_id)
    changes = clean_fields(changes, ORDER_FIELDS)
    if 'shop_name' in changes:
        changes['shop_name'] = valid_shop(conn, changes['shop_name'])
    if changes.get('pickup_date'):
        value = changes['pickup_date']
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError('Use YYYY-MM-DD for pickup_date.')
    if 'bike_tag' in changes and changes['bike_tag'] not in (None, ''):
        tag = changes['bike_tag']
        # Existing orders store REAL tags; reject values that would lose precision.
        if not re.fullmatch(r'[1-9][0-9]*', tag) or int(tag) > 2**53 - 1:
            raise ValueError('Order bike tags must be positive whole numbers without leading zeros.')
        changes['bike_tag'] = int(tag)
    for field in ('bike_type_first_choice', 'bike_type_second_choice'):
        if field in changes and changes[field] not in (None, '', 'A', 'B', 'C', 'D', 'E', 'F'):
            raise ValueError('Bike choices must be A–F, blank, or null.')
        if field in changes and not changes[field]:
            recipient = conn.execute(f'SELECT {field} FROM recipients WHERE recipient_id=?',
                                     (before['recipient_id'],)).fetchone()
            if recipient and recipient[0]:
                raise ValueError('Clearing this choice would reveal a shared recipient fallback; correct the shared data separately.')
    after = {**before, **changes}
    if before['order_status'] == 'Completed' and (not after['pickup_date'] or not after['bike_tag']):
        raise ValueError('Completed orders must retain a pickup date and bike tag.')
    delta = {k: {'before': before[k], 'after': v} for k, v in changes.items() if before[k] != v}
    return {'order_id': order_id, 'version': fingerprint(before), 'changes': delta}


def _actor(conn, actor, reason):
    if not actor or not reason or not reason.strip():
        raise ValueError('An existing username and nonempty reason are required.')
    if conn.execute('SELECT COUNT(*) FROM users WHERE username=?', (actor,)).fetchone()[0] != 1:
        raise ValueError('Actor must match exactly one existing username.')


def _backup(path):
    path = Path(path).resolve(strict=True)
    folder = path.parent / 'backups'
    folder.mkdir(mode=0o700, exist_ok=True)
    backup = folder / f'{path.stem}-before-admin-{uuid4().hex}.db'
    fd = os.open(backup, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    with closing(connect(path)) as source, closing(sqlite3.connect(backup)) as target:
        source.backup(target)
    return str(backup)


def _audit(conn, actor, reason, entity, entity_id, before, after):
    conn.execute('''INSERT INTO admin_changes
        (changed_at, actor, reason, entity, entity_id, before_json, after_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (datetime.now(timezone.utc).isoformat(), actor, reason.strip(), entity,
         str(entity_id), encoded(before), encoded(after)))


def initialize(path, actor, reason):
    with closing(connect(path, writable=True)) as conn, conn:
        conn.execute('BEGIN IMMEDIATE')
        _actor(conn, actor, reason)
        present = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        canonical_index = conn.execute("SELECT 1 FROM sqlite_master WHERE type='index' AND name='ux_inventory_canonical_tag'").fetchone()
        contribution_columns = {r[1] for r in conn.execute('PRAGMA table_info(bike_contributions)')}
        volunteer_columns = {r[1] for r in conn.execute('PRAGMA table_info(volunteers)')}
        if {'bike_inventory', 'admin_changes', 'volunteers', 'bike_contributions',
            'volunteer_hours', 'workshop_submissions'} <= present and canonical_index and 'notes' in contribution_columns and {'joined_on', 'is_active'} <= volunteer_columns:
            return {'applied': False, 'message': 'Maintenance tables already exist.'}
        backup = _backup(path)
        for statement in SCHEMA:
            conn.execute(statement)
        if 'notes' not in {r[1] for r in conn.execute('PRAGMA table_info(bike_contributions)')}:
            conn.execute('ALTER TABLE bike_contributions ADD COLUMN notes TEXT')
        volunteer_columns = {r[1] for r in conn.execute('PRAGMA table_info(volunteers)')}
        if 'joined_on' not in volunteer_columns:
            conn.execute('ALTER TABLE volunteers ADD COLUMN joined_on TEXT')
        if 'is_active' not in volunteer_columns:
            conn.execute('ALTER TABLE volunteers ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1))')
        if 'volunteer_name' in {r[1] for r in conn.execute('PRAGMA table_info(bike_inventory)')}:
            conn.execute('''INSERT INTO bike_contributions
                (inventory_id, recorded_name, recorded_at, source_key)
                SELECT inventory_id, volunteer_name, recorded_at, 'legacy-inventory:' || inventory_id
                FROM bike_inventory WHERE volunteer_name IS NOT NULL AND trim(volunteer_name) <> ''
                AND NOT EXISTS (SELECT 1 FROM bike_contributions c
                    WHERE c.source_key = 'legacy-inventory:' || bike_inventory.inventory_id)''')
        _audit(conn, actor, reason, 'schema', 'maintenance-v5', {}, {'version': 5})
        return {'applied': True, 'backup': backup}


def edit_order(path, order_id, changes, version, actor, reason):
    with closing(connect(path, writable=True)) as conn, conn:
        conn.execute('BEGIN IMMEDIATE')
        _actor(conn, actor, reason)
        preview = order_preview(conn, order_id, changes)
        if not version or version != preview['version']:
            raise ValueError('Order changed or preview version is missing. Preview again before applying.')
        if not preview['changes']:
            return {'applied': False, 'message': 'No changes.'}
        before = read_order(conn, order_id)
        backup = _backup(path)
        values = {k: v['after'] for k, v in preview['changes'].items()}
        values.update(last_updated_by=actor, last_updated_date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        assignments = ', '.join(f'{key}=?' for key in values)
        conn.execute(f'UPDATE orders SET {assignments} WHERE order_id=?', (*values.values(), order_id))
        after = read_order(conn, order_id)
        _audit(conn, actor, reason, 'orders', order_id, before, after)
        return {'applied': True, 'backup': backup, 'changes': preview['changes']}


def bike_preview(conn, values):
    values = clean_fields(values, BIKE_FIELDS)
    if not values.get('bike_tag'):
        raise ValueError('A globally unique bike_tag is required.')
    values['bike_tag'] = canonical_bike_tag(values['bike_tag'])
    values['shop_name'] = valid_shop(conn, values.get('shop_name'))
    if values.get('recorded_at'):
        datetime.fromisoformat(values['recorded_at'])
    if conn.execute(f'SELECT 1 FROM bike_inventory WHERE ({TAG_KEY_SQL})=?', (values['bike_tag'],)).fetchone():
        raise ValueError('Bike tag already exists; tags are unique across all shops and years.')
    return values


def add_bike(path, values, actor, reason):
    with closing(connect(path, writable=True)) as conn, conn:
        conn.execute('BEGIN IMMEDIATE')
        _actor(conn, actor, reason)
        values = bike_preview(conn, values)
        backup = _backup(path)
        volunteer_name = values.pop('volunteer_name', None)
        values['created_at'] = datetime.now(timezone.utc).isoformat()
        names = ', '.join(values)
        params = ', '.join('?' for _ in values)
        cursor = conn.execute(f'INSERT INTO bike_inventory ({names}) VALUES ({params})', tuple(values.values()))
        inventory_id = cursor.lastrowid
        if volunteer_name:
            conn.execute('''INSERT INTO bike_contributions (inventory_id, recorded_name, recorded_at)
                VALUES (?, ?, ?)''', (inventory_id, volunteer_name, values.get('recorded_at')))
        _audit(conn, actor, reason, 'bike_inventory', inventory_id, {}, {**values, 'volunteer_name': volunteer_name})
        return {'applied': True, 'inventory_id': inventory_id, 'backup': backup}


def canonical_bike_tag(tag):
    tag = tag.strip()
    return str(int(tag)) if re.fullmatch(r'[0-9]+', tag) else tag


def lookup_bike(conn, tag):
    row = conn.execute(f'SELECT * FROM bike_inventory WHERE ({TAG_KEY_SQL})=?', (canonical_bike_tag(tag),)).fetchone()
    if row is None:
        return None
    result = dict(row)
    result['contributions'] = [dict(r) for r in conn.execute('''SELECT c.*, v.volunteer_name
        FROM bike_contributions c LEFT JOIN volunteers v ON c.volunteer_id=v.volunteer_id
        WHERE c.inventory_id=? ORDER BY c.contribution_id''', (row['inventory_id'],))]
    return result
