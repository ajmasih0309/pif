"""One-time import of the July normalized CSV set, preserving current app edits.

Defaults to a dry run in an isolated database copy. Never uses orders_data.csv:
that older, overlapping worksheet export has a different order-ID namespace.
"""
import argparse
from collections import Counter, defaultdict
from contextlib import closing
import csv
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import Config

MIGRATION = 'normalized-history-v1'
KEYS = {'contacts': 'contact_id', 'recipients': 'recipient_id',
        'pedal_partners': 'pedal_partner_id', 'shops': 'shop_name', 'orders': 'order_id'}
RENAME = {'status': 'order_status', 'handled_by': 'last_updated_by'}
NUMERIC = {'age', 'bike_tag', 'contact_phone_number'}
TYPE_NAMES = {'public': 'Public', 'pedal partner': 'Pedal Partner',
              'specialty': 'Speciality', 'speciality': 'Speciality'}


def normalize(field, value):
    if value is None:
        return None
    if field.endswith('_id'):
        if value == '':
            return None
        number = Decimal(str(value))
        if not number.is_finite() or number != int(number) or number < 1:
            raise ValueError(f'Invalid {field}: {value!r}')
        return int(number)
    if not isinstance(value, str):
        return value
    value = value.strip()
    if not value:
        return None
    if field in NUMERIC:
        try:
            number = Decimal(value)
            if number.is_finite():
                return int(number) if number == int(number) else float(number)
        except InvalidOperation:
            pass
    if field == 'order_type':
        return TYPE_NAMES.get(value.casefold(), value)
    if field in {'order_status', 'last_status'}:
        return {s.casefold(): s for s in ('Open', 'Contacted', 'Completed', 'Cancelled')}.get(value.casefold(), value)
    if field == 'last_updated_by' and value.casefold() == 'system':
        return 'System'
    if field.startswith('bike_type_'):
        # Existing option letters are A-F; do not guess other malformed values.
        candidate = value.upper().removesuffix(':')
        return candidate if candidate in 'ABCDEF' and len(candidate) == 1 else value
    if field == 'bike_style_preference':
        return {'male': 'M', 'female': 'F', 'no preference': 'N',
                'm': 'M', 'f': 'F', 'n': 'N'}.get(value.casefold(), value)
    if field in {'order_date', 'pickup_date'}:
        try:
            return date.fromisoformat(value).isoformat()
        except ValueError:
            pass  # Retain invalid source dates verbatim for review.
    return value


def read_source(directory):
    tables, manifest = {}, {}
    for table, key in KEYS.items():
        path = Path(directory) / f'{table}.csv'
        payload = path.read_bytes()
        manifest[path.name] = hashlib.sha256(payload).hexdigest()
        reader = csv.DictReader(io.StringIO(payload.decode('utf-8-sig')))
        if not reader.fieldnames or key not in reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError(f'Invalid header: {path.name}')
        rows = {}
        for line, source in enumerate(reader, 2):
            if None in source or None in source.values():
                raise ValueError(f'Malformed CSV row: {path.name}:{line}')
            row = {(RENAME.get(k, k) if table == 'orders' else k): v for k, v in source.items()}
            identity = normalize(key, row[key])
            # The imported shops file has a single blank sentinel, not a shop.
            if table == 'shops' and identity is None and not any(v.strip() for v in row.values()):
                continue
            if identity is None or identity in rows:
                raise ValueError(f'Missing or duplicate {key}: {path.name}:{line}')
            rows[identity] = row
        if not rows:
            raise ValueError(f'Empty source file: {path.name}')
        tables[table] = rows
    fingerprint = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    return tables, manifest, fingerprint


def load_table(conn, table):
    cursor = conn.execute(f'SELECT * FROM "{table}"')
    columns = [c[0] for c in cursor.description]
    rows = {}
    for values in cursor:
        row = dict(zip(columns, values))
        key = row[KEYS[table]]
        if key in rows:
            raise ValueError(f'Duplicate database key in {table}; run schema repairs first.')
        rows[key] = row
    return rows


def audit(tables):
    issues = []
    def issue(kind, identity, **detail):
        issues.append({'issue': kind, 'order_id': identity, **detail})
    duplicate_groups = defaultdict(list)
    for identity, row in tables['orders'].items():
        for field in ('order_date', 'pickup_date'):
            value = row.get(field)
            if not value:
                if field == 'order_date':
                    issue('missing_order_date', identity)
                continue
            try:
                date.fromisoformat(value)
            except (ValueError, TypeError):
                issue('invalid_date', identity, field=field, value=value)
        if not row.get('shop_name'):
            issue('missing_shop', identity)
        if not row.get('recipient_id'):
            issue('missing_recipient', identity)
        if row.get('order_status') not in {'Open', 'Contacted', 'Completed', 'Cancelled'}:
            issue('unknown_status', identity)
        if row.get('order_type') not in set(TYPE_NAMES.values()):
            issue('unknown_order_type', identity)
        if row.get('order_status') == 'Completed' and not row.get('pickup_date'):
            issue('completed_without_pickup', identity)
        try:
            if row.get('pickup_date') and row.get('order_date') and date.fromisoformat(row['pickup_date']) < date.fromisoformat(row['order_date']):
                issue('pickup_before_order', identity)
        except ValueError:
            pass
        for field in ('bike_type_first_choice', 'bike_type_second_choice'):
            if row.get(field) and row[field] not in list('ABCDEF'):
                issue('unknown_bike_choice', identity, field=field, value=row[field])
        duplicate_groups[json.dumps({k: v for k, v in row.items() if k != 'order_id'}, sort_keys=True)].append(identity)
    duplicates = [ids for ids in duplicate_groups.values() if len(ids) > 1]
    return {'issue_counts': dict(Counter(i['issue'] for i in issues)), 'issues': issues,
            'possible_duplicate_groups': duplicates,
            'possible_duplicate_excess_rows': sum(len(ids) - 1 for ids in duplicates),
            'status_counts': dict(Counter(r.get('order_status') for r in tables['orders'].values())),
            'row_counts': {t: len(rows) for t, rows in tables.items()}}


def validate_links(tables):
    for identity, row in tables['orders'].items():
        for field, table in [('contact_id', 'contacts'), ('recipient_id', 'recipients'),
                             ('pedal_partner_id', 'pedal_partners'), ('shop_name', 'shops'),
                             ('linked_order_id', 'orders')]:
            value = row.get(field)
            if value is not None and value not in tables[table]:
                raise ValueError(f'Order {identity}: missing {table} reference {value!r}')


def migrate(conn, source, manifest, fingerprint):
    """Caller owns the write transaction; failures must roll back the entire call."""
    if not conn.in_transaction:
        raise ValueError('A write transaction is required.')
    conn.execute('''CREATE TABLE IF NOT EXISTS history_migrations (
        migration_id TEXT PRIMARY KEY, source_hash TEXT NOT NULL,
        applied_at TEXT NOT NULL, report_json TEXT NOT NULL)''')
    previous = conn.execute('SELECT source_hash, report_json FROM history_migrations WHERE migration_id=?', (MIGRATION,)).fetchone()
    if previous:
        if previous[0] != fingerprint:
            raise ValueError('This migration already ran with different source files; no re-import allowed.')
        return {'already_applied': True, 'previous_report': json.loads(previous[1])}

    live = {t: load_table(conn, t) for t in KEYS}
    merged = {t: {k: dict(v) for k, v in rows.items()} for t, rows in live.items()}
    overlays, changes, additions = [], [], []
    for table, rows in source.items():
        columns = {c[1] for c in conn.execute(f'PRAGMA table_info("{table}")')}
        key = KEYS[table]
        if not set(next(iter(rows.values()))).issubset(columns):
            raise ValueError(f'Unexpected source columns in {table}')
        if table != 'shops' and not any(c[1] == key and c[5] for c in conn.execute(f'PRAGMA table_info("{table}")')):
            raise ValueError(f'{table} needs a primary key; run schema repairs first.')
        for identity, source_row in rows.items():
            imported = {k: normalize(k, v) for k, v in source_row.items()}
            current = live[table].get(identity)
            if current is None:
                merged[table][identity] = imported
                additions.append({'table': table, 'id': identity})
            else:
                for field, value in imported.items():
                    if normalize(field, current[field]) != value:
                        # Same normalized export ID namespace; preserve every later edit,
                        # including cleared fields, not merely rows with audit timestamps.
                        overlays.append({'table': table, 'id': identity, 'field': field})
                        imported[field] = current[field]
                merged[table][identity] = {**current, **imported}
    for table, rows in merged.items():
        column_types = {c[1]: c[2].upper() for c in conn.execute(f'PRAGMA table_info("{table}")')}
        for identity, row in rows.items():
            cleaned = {k: normalize(k, v) for k, v in row.items()}
            # SQLite TEXT affinity represents numeric ages as text; keep comparisons stable.
            cleaned = {k: str(v) if v is not None and column_types.get(k) == 'TEXT' else v for k, v in cleaned.items()}
            rows[identity] = cleaned
            current = live[table].get(identity)
            if current:
                for field, value in cleaned.items():
                    if value != current[field]:
                        changes.append({'table': table, 'id': identity, 'field': field,
                                        'before': current[field], 'after': value})
    validate_links(merged)
    before, after = audit(live), audit(merged)
    report = {'migration': MIGRATION, 'source_files': manifest,
              'source_rows': {t: len(r) for t, r in source.items()},
              'before': before, 'after': after, 'preserved_app_fields': overlays,
              'app_only_ids': {t: [k for k in live[t] if k not in source[t] and k is not None] for t in KEYS},
              'inserted_records': additions, 'normalizations': changes,
              'policy': 'Keep all order IDs and possible duplicates. Flag uncertain history; never invent dates or recipients. Inventory and legacy tables are unchanged.'}
    for table, rows in merged.items():
        key = KEYS[table]
        for identity, row in rows.items():
            if row == live[table].get(identity):
                continue
            if identity in live[table]:
                fields = [f for f in row if f != key]
                conn.execute(f'UPDATE "{table}" SET ' + ', '.join(f'"{f}"=?' for f in fields) + f' WHERE "{key}" IS ?',
                             [row[f] for f in fields] + [identity])
            else:
                fields = list(row)
                conn.execute(f'INSERT INTO "{table}" (' + ', '.join(f'"{f}"' for f in fields) + ') VALUES (' + ','.join('?' for _ in fields) + ')', [row[f] for f in fields])
    stored = {t: load_table(conn, t) for t in KEYS}
    validate_links(stored)
    if audit(stored) != after or conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
        raise ValueError('Post-migration validation failed.')
    conn.execute('INSERT INTO history_migrations VALUES (?, ?, ?, ?)',
                 (MIGRATION, fingerprint, datetime.now(timezone.utc).isoformat(), json.dumps(report)))
    return report


def run(db_path, source_dir, output_dir, apply=False):
    source, manifest, fingerprint = read_source(source_dir)
    db_path = Path(db_path).resolve(strict=True)
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=False)
    target = db_path if apply else output / 'preview.db'
    live = sqlite3.connect(db_path.as_uri() + ('?mode=rw' if apply else '?mode=ro'), uri=True, timeout=30)
    conn = live
    try:
        if not apply:
            conn = sqlite3.connect(target)
            live.backup(conn)
        conn.execute('BEGIN IMMEDIATE')
        if apply:
            # Reserved write lock prevents app writes between backup and migration.
            with closing(sqlite3.connect(db_path.as_uri() + '?mode=ro', uri=True)) as reader:
                backup = sqlite3.connect(output / 'before.db')
                try:
                    reader.backup(backup)
                finally:
                    backup.close()
        try:
            report = migrate(conn, source, manifest, fingerprint)
            (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    finally:
        if conn is not live:
            conn.close()
        live.close()
    (output / 'summary.md').write_text(summary(report, apply))
    return report


def summary(report, applied):
    if report.get('already_applied'):
        return '# Historical migration\n\nAlready applied. No records changed.\n'
    return ('# Historical migration\n\n' + ('Applied' if applied else 'Dry run only; active database unchanged') +
            '.\n\n- Source: July normalized CSV set; older orders_data.csv excluded.\n' +
            f'- Orders: {report["before"]["row_counts"]["orders"]} → {report["after"]["row_counts"]["orders"]}.\n' +
            f'- Normalized fields: {len(report["normalizations"])}.\n' +
            f'- Preserved app field differences: {len(report["preserved_app_fields"])}.\n' +
            f'- Possible duplicate groups retained: {len(report["after"]["possible_duplicate_groups"])}.\n\n' +
            '## Needs source review\n\n' + '\n'.join(f'- {k.replace("_", " ")}: {v}' for k, v in report['after']['issue_counts'].items()) +
            '\n\nSee report.json for affected IDs, exact field changes, source hashes, and before/after counts. No orders were deleted. Missing or contradictory facts were retained for review.\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', default=Config.DB_PATH or 'data/processed/pif.db')
    parser.add_argument('--source-dir', default='data/processed')
    parser.add_argument('--output-dir', required=True, help='New directory for backup/preview and reports')
    parser.add_argument('--apply', action='store_true', help='Apply once in a transaction after backup')
    args = parser.parse_args()
    result = run(args.db, args.source_dir, args.output_dir, args.apply)
    print(summary(result, args.apply))
