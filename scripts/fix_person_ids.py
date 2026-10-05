"""Back up and repair imported person IDs without changing existing order links.

Run from the project root: python scripts/fix_person_ids.py [--db PATH]
"""

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import Config


# Match the imported tables; preserve their column order and storage types.
TABLES = {
    'contacts': ('contact_id', '''contact_name TEXT, contact_phone_number REAL,
        contact_email TEXT, contact_id INTEGER PRIMARY KEY AUTOINCREMENT'''),
    'recipients': ('recipient_id', '''recipient_name TEXT, bike_style_preference TEXT,
        age REAL, height TEXT, bike_type_first_choice TEXT, bike_type_second_choice TEXT,
        recipient_id INTEGER PRIMARY KEY AUTOINCREMENT'''),
    'pedal_partners': ('pedal_partner_id', '''pedal_partner_name TEXT,
        pedal_partner_id INTEGER PRIMARY KEY AUTOINCREMENT'''),
}


def migrate_person_ids(conn):
    if conn.in_transaction:
        raise ValueError('Migration requires a connection without an active transaction.')
    foreign_keys = conn.execute('PRAGMA foreign_keys').fetchone()[0]
    conn.execute('PRAGMA foreign_keys = OFF')
    changed = []
    try:
        with conn:
            conn.execute('BEGIN IMMEDIATE')
            for table, (key, definition) in TABLES.items():
                columns = conn.execute(f'PRAGMA table_info({table})').fetchall()
                if any(c[1] == key and c[2].upper() == 'INTEGER' and c[5] == 1 for c in columns):
                    continue
                if conn.execute(f'''
                    SELECT 1 FROM {table} WHERE {key} IS NOT NULL
                    GROUP BY {key} HAVING COUNT(*) > 1
                ''').fetchone():
                    raise ValueError(f'{table} has duplicate IDs; manual review required.')
                if conn.execute(f'''
                    SELECT 1 FROM {table}
                    WHERE {key} IS NOT NULL AND typeof({key}) <> 'integer'
                ''').fetchone():
                    raise ValueError(f'{table} has non-integer IDs; manual review required.')
                # Never let a newly assigned ID accidentally claim a broken order link.
                if conn.execute(f'''
                    SELECT 1 FROM orders o LEFT JOIN {table} p ON o.{key} = p.{key}
                    WHERE o.{key} IS NOT NULL AND p.{key} IS NULL
                ''').fetchone():
                    raise ValueError(f'Orders have missing {table} references; manual review required.')
                if conn.execute('''
                    SELECT 1 FROM sqlite_master WHERE tbl_name = ?
                    AND type IN ('index', 'trigger')
                ''', (table,)).fetchone() or conn.execute(f'PRAGMA foreign_key_list({table})').fetchall():
                    raise ValueError(f'{table} has additional schema objects; manual review required.')

                replacement = f'_new_{table}'
                conn.execute(f'CREATE TABLE {replacement} ({definition})')
                expected = conn.execute(f'PRAGMA table_info({replacement})').fetchall()
                if [(c[1], c[2].upper(), c[3], c[4]) for c in columns] != [
                    (c[1], c[2].upper(), c[3], c[4]) for c in expected
                ] or any(c[5] for c in columns):
                    raise ValueError(f'Unexpected {table} schema; manual review required.')
                names = ', '.join('"' + c[1] + '"' for c in columns)
                # Copy known IDs first so NULL IDs are allocated above the old maximum.
                conn.execute(f'''INSERT INTO {replacement} ({names})
                    SELECT {names} FROM {table} ORDER BY {key} IS NULL, {key}''')
                conn.execute(f'DROP TABLE {table}')
                conn.execute(f'ALTER TABLE {replacement} RENAME TO {table}')
                changed.append(table)
            for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
                quoted = '"' + name.replace('"', '""') + '"'
                references = conn.execute(f'PRAGMA foreign_key_list({quoted})').fetchall()
                if any(fk[2] in TABLES for fk in references):
                    if conn.execute(f'PRAGMA foreign_key_check({quoted})').fetchone():
                        raise ValueError('Person foreign key validation failed; no changes applied.')
    finally:
        conn.execute(f'PRAGMA foreign_keys = {foreign_keys}')
    return changed


def repair_database(db_path):
    path = Path(db_path).resolve(strict=True)
    backup_dir = path.parent / 'backups'
    backup_dir.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup_path = backup_dir / f'{path.stem}-before-person-ids-{stamp}.db'
    conn = sqlite3.connect(path.as_uri() + '?mode=rw', uri=True)
    try:
        with backup_path.open('xb'):
            pass
        backup = sqlite3.connect(backup_path)
        try:
            conn.backup(backup)
        finally:
            backup.close()
        print(f'Backup: {backup_path}')
        changed = migrate_person_ids(conn)
        print('Repaired tables: ' + (', '.join(changed) or 'none (already repaired)'))
    finally:
        conn.close()
    return backup_path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', default=Config.DB_PATH or 'data/processed/pif.db')
    repair_database(parser.parse_args().db)
