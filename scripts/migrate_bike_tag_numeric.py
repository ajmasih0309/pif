"""Reusable migration to unify bike_inventory.bike_tag and orders.bike_tag as INTEGER (TASK-401).

Usage:
    .venv/bin/python scripts/migrate_bike_tag_numeric.py --dry-run --db-path /tmp/copy.db
    .venv/bin/python scripts/migrate_bike_tag_numeric.py --apply --db-path data/processed/pif.db
"""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import re
import sqlite3

ROOT = Path(__file__).resolve().parent.parent


def _backup_db(db_path: Path) -> Path:
    backup_dir = ROOT / 'backups'
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup_path = backup_dir / f'{db_path.stem}-before-bike-tag-numeric-{ts}.db'
    src = sqlite3.connect(f'file:{db_path.resolve()}?mode=ro', uri=True)
    dst = sqlite3.connect(str(backup_path))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return backup_path

# Owner-approved mappings for legacy non-numeric tags in bike_inventory (TASK-401).
TAG_CORRECTIONS = {
    '61`02': 6102,
    '596ffy': 5966,
    '2781Sch': 2781,
    'L3060': 3060,
}
PLACEHOLDER_TAGS = {'Xxxx'}


def _parse_positive_int(raw):
    text = str(raw).strip()
    if re.fullmatch(r'[0-9]+', text):
        val = int(text)
        return val if val > 0 else None
    if re.fullmatch(r'[0-9]+\.0+', text):
        val = int(text.split('.')[0])
        return val if val > 0 else None
    return None


def audit_database(conn):
    """Inspect bike_inventory and orders for non-numeric, zero, or colliding tags."""
    inv_cols = {r[1]: r[2] for r in conn.execute('PRAGMA table_info(bike_inventory)').fetchall()}
    ord_cols = {r[1]: r[2] for r in conn.execute('PRAGMA table_info(orders)').fetchall()}

    inv_rows = conn.execute('SELECT inventory_id, bike_tag FROM bike_inventory').fetchall()
    corrections = []
    deletes = []
    unexpected_inv = []
    seen_tags = {}
    collisions = []

    for inv_id, raw_tag in inv_rows:
        tag_str = '' if raw_tag is None else str(raw_tag).strip()
        if tag_str in PLACEHOLDER_TAGS:
            deletes.append((inv_id, tag_str))
            continue
        if tag_str in TAG_CORRECTIONS:
            target = TAG_CORRECTIONS[tag_str]
            corrections.append((inv_id, tag_str, target))
        else:
            target = _parse_positive_int(tag_str)
            if target is None:
                unexpected_inv.append((inv_id, raw_tag))
                continue
        if target in seen_tags:
            collisions.append((target, seen_tags[target], inv_id))
        else:
            seen_tags[target] = inv_id

    ord_rows = conn.execute('SELECT order_id, bike_tag FROM orders WHERE bike_tag IS NOT NULL').fetchall()
    zero_orders = []
    unexpected_orders = []
    for order_id, raw_tag in ord_rows:
        if isinstance(raw_tag, (int, float)) and raw_tag <= 0:
            zero_orders.append((order_id, raw_tag))
        elif _parse_positive_int(raw_tag) is None:
            unexpected_orders.append((order_id, raw_tag))

    return {
        'inv_type': inv_cols.get('bike_tag'),
        'ord_type': ord_cols.get('bike_tag'),
        'inv_total': len(inv_rows),
        'corrections': corrections,
        'deletes': deletes,
        'unexpected_inv': unexpected_inv,
        'collisions': collisions,
        'zero_orders': zero_orders,
        'unexpected_orders': unexpected_orders,
    }


def _rebuild_orders_integer_tag(conn):
    """Rebuild orders table with bike_tag INTEGER CHECK(...) preserving all columns and data."""
    cols = [r[1] for r in conn.execute('PRAGMA table_info(orders)').fetchall()]
    col_list = ', '.join(cols)
    select_exprs = []
    for c in cols:
        if c == 'bike_tag':
            select_exprs.append(
                'CASE WHEN bike_tag IS NULL OR bike_tag <= 0 THEN NULL ELSE CAST(bike_tag AS INTEGER) END'
            )
        else:
            select_exprs.append(c)

    conn.execute('''CREATE TABLE orders__new (
        order_id INTEGER PRIMARY KEY AUTOINCREMENT,
        linked_order_id INTEGER,
        contact_id INTEGER,
        recipient_id INTEGER,
        shop_name TEXT,
        pedal_partner_id INTEGER,
        order_date TEXT,
        order_type TEXT,
        order_status TEXT DEFAULT 'Open',
        last_status TEXT,
        last_updated_date TEXT,
        pickup_date TEXT,
        age TEXT,
        height TEXT,
        bike_style_preference TEXT,
        bike_type_first_choice TEXT,
        bike_type_second_choice TEXT,
        bike_tag INTEGER CHECK(bike_tag IS NULL OR (typeof(bike_tag) = 'integer' AND bike_tag > 0)),
        notes TEXT,
        last_updated_by TEXT DEFAULT 'System'
    )''')
    conn.execute(f'INSERT INTO orders__new ({col_list}) SELECT {", ".join(select_exprs)} FROM orders')
    conn.execute('DROP TABLE orders')
    conn.execute('ALTER TABLE orders__new RENAME TO orders')


def _rebuild_bike_inventory_integer_tag(conn):
    """Rebuild bike_inventory table with bike_tag INTEGER NOT NULL UNIQUE CHECK(...)."""
    conn.execute('''CREATE TABLE bike_inventory__new (
        inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
        recorded_at TEXT,
        shop_name TEXT NOT NULL REFERENCES shops(shop_name),
        bike_tag INTEGER NOT NULL UNIQUE CHECK(typeof(bike_tag) = 'integer' AND bike_tag > 0),
        make TEXT,
        model TEXT,
        colour TEXT,
        wheel_size TEXT,
        bike_type TEXT,
        created_at TEXT NOT NULL
    )''')
    conn.execute('''INSERT INTO bike_inventory__new
        (inventory_id, recorded_at, shop_name, bike_tag, make, model, colour, wheel_size, bike_type, created_at)
        SELECT inventory_id, recorded_at, shop_name, CAST(bike_tag AS INTEGER),
               make, model, colour, wheel_size, bike_type, created_at
        FROM bike_inventory''')
    conn.execute('DROP TABLE bike_inventory')
    conn.execute('ALTER TABLE bike_inventory__new RENAME TO bike_inventory')


def apply_migration(db_path):
    """Apply numeric bike_tag cleanup and schema unification with backup and integrity checks."""
    db_path = Path(db_path)
    backup_path = _backup_db(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        report = audit_database(conn)
        if report['unexpected_inv'] or report['unexpected_orders'] or report['collisions']:
            raise RuntimeError(f'Unsafe data state detected: {report}')

        conn.execute('PRAGMA foreign_keys = OFF')
        with conn:
            for inv_id, _old, new_tag in report['corrections']:
                conn.execute('UPDATE bike_inventory SET bike_tag = ? WHERE inventory_id = ?', (str(new_tag), inv_id))
            for inv_id, _old in report['deletes']:
                conn.execute('DELETE FROM bike_contributions WHERE inventory_id = ?', (inv_id,))
                conn.execute('DELETE FROM bike_inventory WHERE inventory_id = ?', (inv_id,))

            if report['inv_type'] != 'INTEGER':
                _rebuild_bike_inventory_integer_tag(conn)
            if report['ord_type'] != 'INTEGER':
                _rebuild_orders_integer_tag(conn)
            elif report['zero_orders']:
                conn.execute('UPDATE orders SET bike_tag = NULL WHERE bike_tag IS NOT NULL AND bike_tag <= 0')

            if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='admin_changes'").fetchone():
                import json
                conn.execute(
                    '''INSERT INTO admin_changes (changed_at, actor, reason, entity, entity_id, before_json, after_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (
                        datetime.now(timezone.utc).isoformat(),
                        'migration:task-401',
                        'Unify bike_inventory.bike_tag and orders.bike_tag to INTEGER',
                        'schema',
                        0,
                        json.dumps({'inv_type': report['inv_type'], 'ord_type': report['ord_type']}),
                        json.dumps({
                            'inv_type': 'INTEGER',
                            'ord_type': 'INTEGER',
                            'corrected': len(report['corrections']),
                            'deleted': len(report['deletes']),
                            'zero_orders_nulled': len(report['zero_orders']),
                        }),
                    ),
                )

        conn.execute('PRAGMA foreign_keys = ON')
        fk_errors = conn.execute('PRAGMA foreign_key_check').fetchall()
        integrity = conn.execute('PRAGMA integrity_check').fetchone()[0]
        if fk_errors:
            raise RuntimeError(f'Foreign key check failed: {fk_errors}')
        if integrity != 'ok':
            raise RuntimeError(f'Integrity check failed: {integrity}')
        return {'backup': str(backup_path), 'report': report, 'fk_errors': 0, 'integrity': integrity}
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description='Unify bike_tag to numeric INTEGER (TASK-401).')
    parser.add_argument('--db-path', default='data/processed/pif.db')
    parser.add_argument('--apply', action='store_true', help='Apply migration (default is dry-run).')
    parser.add_argument('--dry-run', action='store_true', help='Inspect only without modifying database.')
    args = parser.parse_args()

    db_path = Path(args.db_path)
    if not db_path.exists():
        raise SystemExit(f'Database not found: {db_path}')

    if args.apply and not args.dry_run:
        result = apply_migration(db_path)
        print('APPLIED:', result)
    else:
        conn = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
        try:
            report = audit_database(conn)
            print('DRY-RUN:', report)
        finally:
            conn.close()


if __name__ == '__main__':
    main()
