#!/usr/bin/env python3
"""
Reusable migration script for PIF Volunteer Time Clock & Shop Details.
---------------------------------------------------------------------
Tasks implemented:
- TASK-615: Upgrade `shops` table with address, landmark, and store operating hours.
- TASK-611: Upgrade `volunteers` schema (joined_on, is_active) and ensure `volunteer_hours`.
- TASK-612: Standardize volunteer profiles, compute joined_on and 180-day is_active flag.
- TASK-613: Standardize volunteer hours into integer minutes and map shop codes ('B', 'R', 'S').
            Applies Option B catch-up backfill on prior open shop days for entries > 24 hours.
- TASK-614: Provides --dry-run (inspection report) and --apply (safe migration with backup).

Usage:
    .venv/bin/python scripts/migrate_volunteer_clock.py --dry-run
    .venv/bin/python scripts/migrate_volunteer_clock.py --apply --db-path data/processed/pif.db
"""

import argparse
import datetime
from pathlib import Path
import re
import shutil
import sqlite3
import sys

import openpyxl

# --- Configuration & Reference Data ---

SHOP_DATA = {
    'B': {
        'shop_id': 1,
        'shop_location': 'Bentonville',
        'address': '3902 NW Wishing Springs Rd., Bentonville, AR 72712',
        'landmark': None,
        'store_hours': 'Mon: 5:00 PM – 8:00 PM, Wed: 9:00 AM – 12:00 PM, Sat: 9:00 AM – 12:00 PM',
        'open_weekdays': {0: (17, 20), 2: (9, 12), 5: (9, 12)},  # Mon=0, Wed=2, Sat=5
    },
    'R': {
        'shop_id': 2,
        'shop_location': 'Rogers',
        'address': '315 W. Olive St., Rogers, AR 72756',
        'landmark': 'behind Rogers Activity Center',
        'store_hours': 'Mon: 5:00 PM – 8:00 PM, Wed: 9:00 AM – 12:00 PM, Sat: 9:00 AM – 12:00 PM',
        'open_weekdays': {0: (17, 20), 2: (9, 12), 5: (9, 12)},  # Mon=0, Wed=2, Sat=5
    },
    'S': {
        'shop_id': 3,
        'shop_location': 'Springdale',
        'address': '115 Willella Pl., Springdale, AR 72764',
        'landmark': 'Jones Center campus',
        'store_hours': 'Mon: 5:00 PM – 8:00 PM, Wed: 9:00 AM – 12:00 PM',
        'open_weekdays': {0: (17, 20), 2: (9, 12)},              # Mon=0, Wed=2 (Sat closed)
    },
}

RAW_SHOP_MAP = {
    'bentonville/bella vista shop': 'B',
    'bentonville': 'B',
    'rogers shop': 'R',
    'rogers': 'R',
    'springdale': 'S',
    'springdale shop': 'S',
}


def standardize_name(name: str) -> str:
    """Normalize whitespace and convert to Title Case."""
    cleaned = re.sub(r'\s+', ' ', str(name)).strip()
    return cleaned.title()


def get_shop_code(raw_shop: str) -> str:
    """Map raw shop strings to canonical 'B', 'R', 'S'."""
    if not raw_shop:
        return 'B'  # Default to Bentonville per O-004
    key = str(raw_shop).strip().lower()
    if key in RAW_SHOP_MAP:
        return RAW_SHOP_MAP[key]
    if 'bentonville' in key:
        return 'B'
    if 'rogers' in key:
        return 'R'
    if 'springdale' in key:
        return 'S'
    return 'B'


def split_catchup_hours(submission_date, total_hours, shop_code):
    """
    Option B: Break shifts exceeding 24 hours into 3-hour shifts (180 mins)
    on prior open days for that specific shop, preserving 100% of the minutes.
    """
    open_weekdays = SHOP_DATA[shop_code]['open_weekdays']
    remaining_minutes = int(round(total_hours * 60))
    current_date = submission_date.date() if isinstance(submission_date, datetime.datetime) else submission_date

    shifts = []
    day = current_date
    while remaining_minutes > 0:
        if day.weekday() in open_weekdays:
            shift_mins = min(180, remaining_minutes)
            shifts.append((day.isoformat(), shift_mins))
            remaining_minutes -= shift_mins
        day -= datetime.timedelta(days=1)
    return shifts


def parse_raw_time_clock(excel_path: Path):
    """
    Parse 'Form Responses 1' from the raw workbook.
    Returns:
        volunteers_dict: {canonical_name: {'joined_date': date, 'last_active': date, 'raw_names': set}}
        shifts_list: list of parsed shift dicts
        stats: dictionary of summary counters and anomalies
    """
    wb = openpyxl.load_workbook(str(excel_path), read_only=True)
    if 'Form Responses 1' not in wb.sheetnames:
        raise ValueError(f"Sheet 'Form Responses 1' not found in {excel_path}. Available: {wb.sheetnames}")

    sheet = wb['Form Responses 1']

    volunteers = {}
    shifts = []
    stats = {
        'total_rows_scanned': 0,
        'blank_rows_skipped': 0,
        'valid_entries_parsed': 0,
        'normal_shifts': 0,
        'catchup_entries': 0,
        'catchup_splits_generated': 0,
        'total_hours_parsed': 0.0,
        'total_minutes_parsed': 0,
        'shop_breakdown': {'B': 0, 'R': 0, 'S': 0},
    }

    raw_entries = []

    for idx, row in enumerate(sheet.iter_rows(values_only=True)):
        if idx == 0 or not row:
            continue
        stats['total_rows_scanned'] += 1

        ts = row[0] if len(row) > 0 else None
        name = row[1] if len(row) > 1 else None
        hrs_raw = row[2] if len(row) > 2 else None
        shop_raw = row[3] if len(row) > 3 else None

        # Filter empty / trailing blank rows
        if not ts and not name and not hrs_raw and not shop_raw:
            stats['blank_rows_skipped'] += 1
            continue

        if not ts or not name or hrs_raw is None:
            stats['blank_rows_skipped'] += 1
            continue

        try:
            hours_val = float(str(hrs_raw).strip())
            if hours_val <= 0:
                stats['blank_rows_skipped'] += 1
                continue
        except (ValueError, TypeError):
            stats['blank_rows_skipped'] += 1
            continue

        canonical_name = standardize_name(name)
        shop_code = get_shop_code(shop_raw)

        raw_entries.append({
            'timestamp': ts,
            'raw_name': name,
            'canonical_name': canonical_name,
            'hours': hours_val,
            'shop_code': shop_code,
        })

    # Sort chronologically by timestamp
    raw_entries.sort(key=lambda x: x['timestamp'])

    if not raw_entries:
        raise ValueError("No valid entries found in Form Responses 1.")

    max_timestamp = max(x['timestamp'] for x in raw_entries)
    cutoff_date = (max_timestamp - datetime.timedelta(days=180)).date()

    for item in raw_entries:
        stats['valid_entries_parsed'] += 1
        stats['total_hours_parsed'] += item['hours']
        minutes = int(round(item['hours'] * 60))
        stats['total_minutes_parsed'] += minutes
        stats['shop_breakdown'][item['shop_code']] += 1

        cname = item['canonical_name']
        ts = item['timestamp']
        entry_date = ts.date() if isinstance(ts, datetime.datetime) else ts

        if cname not in volunteers:
            volunteers[cname] = {
                'joined_date': entry_date,
                'last_active': entry_date,
                'raw_names': {item['raw_name']},
                'total_hours': 0.0,
            }
        else:
            if entry_date < volunteers[cname]['joined_date']:
                volunteers[cname]['joined_date'] = entry_date
            if entry_date > volunteers[cname]['last_active']:
                volunteers[cname]['last_active'] = entry_date
            volunteers[cname]['raw_names'].add(item['raw_name'])

        volunteers[cname]['total_hours'] += item['hours']

        # Determine shift handling (Normal vs Option B Catchup)
        if item['hours'] > 24.0:
            stats['catchup_entries'] += 1
            splits = split_catchup_hours(ts, item['hours'], item['shop_code'])
            stats['catchup_splits_generated'] += len(splits)
            for s_date, s_mins in splits:
                shifts.append({
                    'canonical_name': cname,
                    'work_date': s_date,
                    'minutes': s_mins,
                    'shop_code': item['shop_code'],
                    'activity': 'Catchup hours',
                    'notes': f"Catchup hours: split from {item['hours']}h logged on {str(ts)[:19]}",
                    'created_at': ts.isoformat() if isinstance(ts, datetime.datetime) else str(ts),
                    'created_by': 'migration:time_clock:catchup',
                })
        else:
            stats['normal_shifts'] += 1
            shifts.append({
                'canonical_name': cname,
                'work_date': entry_date.isoformat(),
                'minutes': minutes,
                'shop_code': item['shop_code'],
                'activity': 'Volunteer shift',
                'notes': None,
                'created_at': ts.isoformat() if isinstance(ts, datetime.datetime) else str(ts),
                'created_by': 'migration:time_clock',
            })

    # Finalize active flag (1 if active within last 180 days relative to max entry, else 0)
    for cname, vdata in volunteers.items():
        vdata['is_active'] = 1 if vdata['last_active'] >= cutoff_date else 0

    stats['unique_volunteers'] = len(volunteers)
    stats['active_volunteers'] = sum(1 for v in volunteers.values() if v['is_active'] == 1)
    stats['inactive_volunteers'] = sum(1 for v in volunteers.values() if v['is_active'] == 0)
    stats['total_shifts_generated'] = len(shifts)
    stats['max_timestamp'] = max_timestamp
    stats['cutoff_date'] = cutoff_date

    return volunteers, shifts, stats


def upgrade_schema_and_shops(conn):
    """
    Ensures:
    1. shops table has shop_id, address, landmark, store_hours, and seeds B, R, S.
    2. volunteers table has joined_on and is_active.
    3. volunteer_hours table exists matching the application domain model.
    """
    # 1. Upgrade shops table
    conn.execute('''CREATE TABLE IF NOT EXISTS shops (
        shop_id INTEGER,
        shop_name TEXT UNIQUE,
        shop_location TEXT,
        address TEXT,
        landmark TEXT,
        store_hours TEXT
    )''')
    shop_cols = {r[1] for r in conn.execute('PRAGMA table_info(shops)')}
    if 'shop_id' not in shop_cols:
        conn.execute('ALTER TABLE shops ADD COLUMN shop_id INTEGER')
    for col in ('address', 'landmark', 'store_hours'):
        if col not in shop_cols:
            conn.execute(f'ALTER TABLE shops ADD COLUMN {col} TEXT')

    # Seed/Update shops
    for code, sinfo in SHOP_DATA.items():
        existing = conn.execute('SELECT rowid FROM shops WHERE shop_name = ?', (code,)).fetchone()
        if existing:
            conn.execute('''
                UPDATE shops
                SET shop_id = ?,
                    shop_location = ?,
                    address = ?,
                    landmark = ?,
                    store_hours = ?
                WHERE shop_name = ?
            ''', (sinfo['shop_id'], sinfo['shop_location'], sinfo['address'], sinfo['landmark'], sinfo['store_hours'], code))
        else:
            conn.execute('''
                INSERT INTO shops (shop_id, shop_name, shop_location, address, landmark, store_hours)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (sinfo['shop_id'], code, sinfo['shop_location'], sinfo['address'], sinfo['landmark'], sinfo['store_hours']))

    # Ensure unique indexes on shop_name and shop_id
    conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS ux_shops_shop_name ON shops (shop_name)')
    conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS ux_shops_shop_id ON shops (shop_id)')

    # Remove rogue empty/null shop row if present
    conn.execute('DELETE FROM shops WHERE shop_name IS NULL')

    # 2. Upgrade volunteers table
    conn.execute('''CREATE TABLE IF NOT EXISTS volunteers (
        volunteer_id INTEGER PRIMARY KEY AUTOINCREMENT,
        volunteer_name TEXT NOT NULL,
        volunteer_email TEXT,
        volunteer_phone_number TEXT,
        joined_on TEXT,
        is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1))
    )''')
    vol_cols = {r[1] for r in conn.execute('PRAGMA table_info(volunteers)')}
    if 'joined_on' not in vol_cols:
        conn.execute('ALTER TABLE volunteers ADD COLUMN joined_on TEXT')
    if 'is_active' not in vol_cols:
        conn.execute('ALTER TABLE volunteers ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1))')

    # 3. Ensure volunteer_hours and workshop tables
    conn.execute('''CREATE TABLE IF NOT EXISTS bike_inventory (
        inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
        recorded_at TEXT,
        shop_name TEXT NOT NULL REFERENCES shops(shop_name),
        bike_tag TEXT NOT NULL UNIQUE CHECK(length(trim(bike_tag)) > 0),
        make TEXT, model TEXT, colour TEXT, wheel_size TEXT, bike_type TEXT,
        created_at TEXT NOT NULL
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS bike_contributions (
        contribution_id INTEGER PRIMARY KEY AUTOINCREMENT,
        inventory_id INTEGER NOT NULL REFERENCES bike_inventory(inventory_id),
        volunteer_id INTEGER REFERENCES volunteers(volunteer_id),
        recorded_name TEXT,
        recorded_at TEXT,
        source_key TEXT UNIQUE,
        source_sheet TEXT,
        source_row INTEGER,
        notes TEXT
    )''')
    conn.execute('CREATE INDEX IF NOT EXISTS ix_bike_contributions_inventory ON bike_contributions(inventory_id)')

    conn.execute('''CREATE TABLE IF NOT EXISTS volunteer_hours (
        time_log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        volunteer_id INTEGER NOT NULL REFERENCES volunteers(volunteer_id),
        work_date TEXT NOT NULL,
        minutes INTEGER NOT NULL CHECK(typeof(minutes) = 'integer' AND minutes BETWEEN 1 AND 1440),
        shop_name TEXT REFERENCES shops(shop_name),
        activity TEXT,
        notes TEXT,
        created_at TEXT NOT NULL,
        created_by TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        updated_by TEXT NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        voided_at TEXT,
        void_reason TEXT
    )''')
    conn.execute('CREATE INDEX IF NOT EXISTS ix_volunteer_hours_date ON volunteer_hours(work_date, volunteer_id)')


def create_backup(db_path: Path) -> Path:
    """Create a timestamped backup copy before running changes."""
    backup_dir = db_path.parent / 'backups'
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup_path = backup_dir / f"{db_path.stem}-before-volunteer-clock-{ts}.db"
    shutil.copy2(db_path, backup_path)
    return backup_path


def apply_migration(db_path: Path, volunteers: dict, shifts: list):
    """
    Applies schema upgrades, inserts/updates volunteers, and inserts shifts inside
    an atomic transaction. Creates a backup first.
    """
    db_path = db_path.resolve()
    if not db_path.exists():
        raise FileNotFoundError(f"Target database not found: {db_path}")

    backup_path = create_backup(db_path)
    print(f"Backed up active database to:\n  {backup_path}")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # 1. Upgrade schema & shops first before turning on foreign keys
    # so that legacy tables referencing shops(shop_id) have valid target indexes.
    with conn:
        conn.execute('BEGIN IMMEDIATE')
        upgrade_schema_and_shops(conn)

    # 2. Turn on foreign key enforcement and insert volunteers and hours atomically
    conn.execute('PRAGMA foreign_keys=ON')

    with conn:
        conn.execute('BEGIN IMMEDIATE')

        # Insert or update volunteers
        existing_rows = conn.execute('SELECT volunteer_id, volunteer_name FROM volunteers').fetchall()
        name_to_id = {standardize_name(r['volunteer_name']): r['volunteer_id'] for r in existing_rows}

        inserted_volunteers = 0
        updated_volunteers = 0

        # Sort volunteers by joined_date, then name for deterministic IDs
        sorted_volunteers = sorted(volunteers.items(), key=lambda x: (x[1]['joined_date'], x[0]))

        for cname, vinfo in sorted_volunteers:
            if cname in name_to_id:
                vid = name_to_id[cname]
                conn.execute('''
                    UPDATE volunteers
                    SET joined_on = COALESCE(joined_on, ?),
                        is_active = ?
                    WHERE volunteer_id = ?
                ''', (vinfo['joined_date'].isoformat(), vinfo['is_active'], vid))
                updated_volunteers += 1
            else:
                cursor = conn.execute('''
                    INSERT INTO volunteers (volunteer_name, joined_on, is_active)
                    VALUES (?, ?, ?)
                ''', (cname, vinfo['joined_date'].isoformat(), vinfo['is_active']))
                vid = cursor.lastrowid
                name_to_id[cname] = vid
                inserted_volunteers += 1

        # 3. Insert shifts into volunteer_hours
        inserted_shifts = 0
        for s in shifts:
            vid = name_to_id[s['canonical_name']]
            conn.execute('''
                INSERT INTO volunteer_hours (
                    volunteer_id, work_date, minutes, shop_name, activity, notes,
                    created_at, created_by, updated_at, updated_by, version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            ''', (
                vid, s['work_date'], s['minutes'], s['shop_code'], s['activity'], s['notes'],
                s['created_at'], s['created_by'], s['created_at'], s['created_by']
            ))
            inserted_shifts += 1

    conn.close()

    print(f"\nMigration Applied Successfully:")
    print(f"  - Volunteers inserted: {inserted_volunteers}")
    print(f"  - Volunteers updated:  {updated_volunteers}")
    print(f"  - Shift records inserted: {inserted_shifts}")


def print_dry_run_report(volunteers: dict, shifts: list, stats: dict, excel_path: Path):
    """Prints a structured dry-run inspection report."""
    print("=" * 70)
    print("PIF VOLUNTEER TIME CLOCK MIGRATION — DRY-RUN INSPECTION REPORT")
    print("=" * 70)
    print(f"Source Excel File: {excel_path}")
    print(f"Total Rows Scanned:        {stats['total_rows_scanned']:,}")
    print(f"Blank/Empty Rows Skipped:  {stats['blank_rows_skipped']:,}")
    print(f"Valid Clock Submissions:   {stats['valid_entries_parsed']:,}")
    print("-" * 70)
    print(f"Total Hours Logged:        {stats['total_hours_parsed']:,.2f} hours")
    print(f"Total Minutes Logged:      {stats['total_minutes_parsed']:,} minutes")
    print(f"Submissions Date Range:    Earliest: {min(v['joined_date'] for v in volunteers.values())} | Latest: {stats['max_timestamp']}")
    print(f"180-Day Active Cutoff:     {stats['cutoff_date']}")
    print("-" * 70)
    print("VOLUNTEER DIRECTORY BREAKDOWN:")
    print(f"  Total Unique Volunteers: {stats['unique_volunteers']}")
    print(f"  Active Volunteers (>=180d): {stats['active_volunteers']}")
    print(f"  Inactive Volunteers (<180d): {stats['inactive_volunteers']}")
    print("-" * 70)
    print("SHOP SUBMISSION BREAKDOWN:")
    for code, count in stats['shop_breakdown'].items():
        sinfo = SHOP_DATA[code]
        print(f"  [{code}] {sinfo['shop_location']:12s}: {count:5,d} entries | Hours: {sinfo['store_hours']}")
    print("-" * 70)
    print("SHIFT BREAKDOWN & OPTION B CATCH-UP BACKFILL:")
    print(f"  Standard Daily Shifts (<= 24h): {stats['normal_shifts']:,}")
    print(f"  Catch-up Submissions (> 24h):   {stats['catchup_entries']:,}")
    print(f"  Shifts Generated from Catch-up: {stats['catchup_splits_generated']:,} (split into 3-hour open-day shifts)")
    print(f"  Total Volunteer Hours Records to Insert: {stats['total_shifts_generated']:,}")
    print("=" * 70)
    print("Sample Volunteers (first 5 by joined date):")
    sample_vols = sorted(volunteers.items(), key=lambda x: (x[1]['joined_date'], x[0]))[:5]
    for name, v in sample_vols:
        status = "Active" if v['is_active'] == 1 else "Inactive"
        print(f"  • {name:22s} | Joined: {v['joined_date']} | Last: {v['last_active']} | Total: {v['total_hours']:6.1f}h | {status}")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Migrate raw PIF volunteer time clock Excel data into database.")
    parser.add_argument('--excel-path', default='data/raw/PIF Volunteer Reporting time clock.xlsx', help="Path to raw Excel workbook.")
    parser.add_argument('--db-path', default='data/processed/pif.db', help="Path to SQLite database.")
    parser.add_argument('--dry-run', action='store_true', help="Inspect and report without modifying the database.")
    parser.add_argument('--apply', action='store_true', help="Execute the migration with backup.")

    args = parser.parse_args()

    excel_path = Path(args.excel_path).resolve()
    if not excel_path.exists():
        print(f"Error: Excel file not found: {excel_path}", file=sys.stderr)
        sys.exit(1)

    db_path = Path(args.db_path).resolve()

    volunteers, shifts, stats = parse_raw_time_clock(excel_path)

    if args.dry_run or not args.apply:
        print_dry_run_report(volunteers, shifts, stats, excel_path)
        if not args.apply:
            print("\nTo apply this migration to a database, run with --apply --db-path <path>")
        sys.exit(0)

    if args.apply:
        apply_migration(db_path, volunteers, shifts)


if __name__ == '__main__':
    main()
