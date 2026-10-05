"""Back up the database, merge duplicate shop codes, and enforce uniqueness.

Run from the project root: python scripts/fix_duplicate_shops.py
Use --db PATH to repair a different database. No order records are modified.
"""

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import Config


def migrate_shops(conn):
    """Keep the populated shop row; abort if locations disagree.

    NULL shop codes cannot match the order join and are left untouched.
    The cleanup and unique index are committed together, or rolled back.
    """
    with conn:
        conn.execute('BEGIN IMMEDIATE')
        duplicates = conn.execute('''
            SELECT shop_name
            FROM shops
            WHERE shop_name IS NOT NULL
            GROUP BY shop_name
            HAVING COUNT(*) > 1
        ''').fetchall()

        removed = 0
        for (shop_name,) in duplicates:
            rows = conn.execute('''
                SELECT rowid, shop_location FROM shops
                WHERE shop_name = ? ORDER BY rowid
            ''', (shop_name,)).fetchall()
            locations = {location.strip() for _, location in rows if location and location.strip()}
            if len(locations) > 1:
                raise ValueError(f'Conflicting locations for shop {shop_name!r}; no changes applied.')

            keep_id = next(
                (row_id for row_id, location in rows if location and location.strip()),
                rows[0][0],
            )
            removed += conn.execute(
                'DELETE FROM shops WHERE shop_name = ? AND rowid <> ?',
                (shop_name, keep_id),
            ).rowcount

        conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS ux_shops_shop_name ON shops (shop_name)')
    return removed


def repair_database(db_path):
    db_path = Path(db_path).resolve(strict=True)
    backup_dir = db_path.parent / 'backups'
    backup_dir.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup_path = backup_dir / f'{db_path.stem}-before-shop-dedup-{stamp}.db'

    conn = sqlite3.connect(db_path.as_uri() + '?mode=rw', uri=True)
    try:
        # SQLite's backup API also includes committed data in a WAL file.
        with backup_path.open('xb'):
            pass
        backup = sqlite3.connect(backup_path)
        try:
            conn.backup(backup)
        finally:
            backup.close()
        print(f'Backup: {backup_path}')
        removed = migrate_shops(conn)
        print(f'Removed {removed} duplicate shop row(s); shop codes are now unique.')
    finally:
        conn.close()
    return backup_path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', default=Config.DB_PATH or 'data/processed/pif.db')
    args = parser.parse_args()
    repair_database(args.db)
