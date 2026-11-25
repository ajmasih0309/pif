"""Versioned SQLite schema migration framework for PIF Portal (TASK-601)."""
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from admin_tools import SCHEMA as WORKSHOP_SCHEMA


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def _migrate_v1_core_intake_and_pickup(conn):
    """Create order intake receipt, invite, and pickup reminder tracking tables."""
    conn.execute('''CREATE TABLE IF NOT EXISTS order_submissions (
        submission_key TEXT PRIMARY KEY,
        order_ids TEXT NOT NULL,
        created_at TEXT NOT NULL
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS request_invites (
        invite_id INTEGER PRIMARY KEY AUTOINCREMENT,
        token_hash TEXT NOT NULL UNIQUE,
        issuance_key TEXT NOT NULL UNIQUE,
        label TEXT NOT NULL,
        shop_name TEXT NOT NULL,
        order_type TEXT NOT NULL,
        pedal_partner_name TEXT NOT NULL,
        issued_by TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        expires_at INTEGER NOT NULL,
        used_at INTEGER,
        revoked_at INTEGER
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS order_pickup_tracking (
        order_id INTEGER PRIMARY KEY,
        contacted_at TEXT NOT NULL
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS pickup_reminder_delivery (
        order_id INTEGER NOT NULL,
        contacted_at TEXT NOT NULL,
        deadline TEXT NOT NULL,
        mode TEXT NOT NULL,
        claimed_at TEXT,
        sent_at TEXT,
        PRIMARY KEY (order_id, contacted_at, deadline, mode)
    )''')


def _migrate_v2_workshop_and_audit(conn):
    """Ensure workshop, volunteer, bike inventory, and audit tables match v5 schema."""
    for statement in WORKSHOP_SCHEMA:
        conn.execute(statement)
    if 'notes' not in {r[1] for r in conn.execute('PRAGMA table_info(bike_contributions)')}:
        conn.execute('ALTER TABLE bike_contributions ADD COLUMN notes TEXT')
    vol_cols = {r[1] for r in conn.execute('PRAGMA table_info(volunteers)')}
    if 'joined_on' not in vol_cols:
        conn.execute('ALTER TABLE volunteers ADD COLUMN joined_on TEXT')
    if 'is_active' not in vol_cols:
        conn.execute('ALTER TABLE volunteers ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1))')


def _migrate_v3_numeric_bike_tags(conn):
    """Ensure bike_inventory.bike_tag and orders.bike_tag use INTEGER type when present."""
    from scripts.migrate_bike_tag_numeric import (
        _rebuild_bike_inventory_integer_tag,
        _rebuild_orders_integer_tag,
        audit_database,
    )
    report = audit_database(conn)
    if report['unexpected_inv'] or report['unexpected_orders'] or report['collisions']:
        raise RuntimeError(f'Cannot auto-convert bike_tag due to non-numeric/colliding rows: {report}')
    if report['inv_type'] != 'INTEGER' or report['ord_type'] != 'INTEGER':
        conn.execute('PRAGMA foreign_keys = OFF')
        if report['inv_type'] != 'INTEGER':
            _rebuild_bike_inventory_integer_tag(conn)
        if report['ord_type'] != 'INTEGER':
            _rebuild_orders_integer_tag(conn)
        conn.execute('PRAGMA foreign_keys = ON')


MIGRATIONS = (
    (1, 'core_intake_and_pickup_tables', _migrate_v1_core_intake_and_pickup),
    (2, 'workshop_and_audit_tables', _migrate_v2_workshop_and_audit),
    (3, 'numeric_bike_tag_constraints', _migrate_v3_numeric_bike_tags),
)
EXPECTED_SCHEMA_VERSION = MIGRATIONS[-1][0]


def ensure_migrations_table(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS schema_migrations (
        version INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        applied_at TEXT NOT NULL
    )''')


def applied_versions(conn):
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'").fetchone()
    if not row:
        return set()
    return {r[0] for r in conn.execute('SELECT version FROM schema_migrations').fetchall()}


def current_version(conn):
    versions = applied_versions(conn)
    return max(versions) if versions else 0


def verify_schema_ready(db_path):
    """Fail fast with an operator-facing message if db_path is missing or behind EXPECTED_SCHEMA_VERSION."""
    path = Path(db_path)
    if not path.exists():
        raise RuntimeError(
            f"Database file not found at '{path}'. "
            f"Initialize and migrate it before starting the server: "
            f".venv/bin/python scripts/migrate_db.py --apply --db-path {path}"
        )
    conn = sqlite3.connect(f'file:{path.resolve()}?mode=ro', uri=True)
    try:
        version = current_version(conn)
    finally:
        conn.close()
    if version < EXPECTED_SCHEMA_VERSION:
        raise RuntimeError(
            f"Database schema at '{path}' is at version {version}, expected {EXPECTED_SCHEMA_VERSION}. "
            f"Run '.venv/bin/python scripts/migrate_db.py --apply --db-path {path}' before starting the server."
        )
    return version


def pending_migrations(conn, target_version=None):
    limit = EXPECTED_SCHEMA_VERSION if target_version is None else target_version
    done = applied_versions(conn)
    return [(v, name, fn) for v, name, fn in MIGRATIONS if v <= limit and v not in done]


def apply_migrations(conn, target_version=None):
    """Apply pending migrations up to target_version on an open SQLite connection."""
    ensure_migrations_table(conn)
    pending = pending_migrations(conn, target_version=target_version)
    applied = []
    for version, name, fn in pending:
        fn(conn)
        conn.execute(
            'INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)',
            (version, name, _utc_now()),
        )
        applied.append((version, name))
    return applied


def _backup_db(db_path: Path) -> Path:
    backup_dir = Path(__file__).resolve().parent / 'backups'
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup_path = backup_dir / f'{db_path.stem}-before-migrate-{ts}.db'
    src = sqlite3.connect(f'file:{db_path.resolve()}?mode=ro', uri=True)
    dst = sqlite3.connect(str(backup_path))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return backup_path


def migrate_database(db_path, backup=True, dry_run=False, target_version=None):
    """Inspect or apply versioned migrations on a SQLite database file."""
    db_path = Path(db_path)
    if dry_run:
        conn = sqlite3.connect(f'file:{db_path.resolve()}?mode=ro', uri=True)
        try:
            pending = [(v, name) for v, name, _ in pending_migrations(conn, target_version=target_version)]
            return {
                'current_version': current_version(conn),
                'expected_version': EXPECTED_SCHEMA_VERSION,
                'pending': pending,
            }
        finally:
            conn.close()

    backup_path = str(_backup_db(db_path)) if backup else None
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute('PRAGMA foreign_keys = ON')
        with conn:
            applied = apply_migrations(conn, target_version=target_version)
        fk_errors = conn.execute('PRAGMA foreign_key_check').fetchall()
        integrity = conn.execute('PRAGMA integrity_check').fetchone()[0]
        if fk_errors:
            raise RuntimeError(f'Foreign key check failed: {fk_errors}')
        if integrity != 'ok':
            raise RuntimeError(f'Integrity check failed: {integrity}')
        return {
            'backup': backup_path,
            'applied': applied,
            'current_version': current_version(conn),
            'expected_version': EXPECTED_SCHEMA_VERSION,
            'fk_errors': 0,
            'integrity': integrity,
        }
    finally:
        conn.close()
