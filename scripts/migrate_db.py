"""CLI runner for versioned PIF Portal database migrations (TASK-601)."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from migrations import migrate_database  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description='Run versioned schema migrations for PIF Portal.')
    parser.add_argument('--db-path', default='data/processed/pif.db')
    parser.add_argument('--apply', action='store_true', help='Apply pending migrations (default is dry-run).')
    parser.add_argument('--dry-run', action='store_true', help='Report current and pending versions without modifying DB.')
    parser.add_argument('--no-backup', action='store_true', help='Skip backup before applying (for temp copies only).')
    args = parser.parse_args()

    db_path = Path(args.db_path)
    if not db_path.exists():
        raise SystemExit(f'Database not found: {db_path}')

    if args.apply and not args.dry_run:
        result = migrate_database(db_path, backup=not args.no_backup, dry_run=False)
        print('APPLIED:', result)
    else:
        result = migrate_database(db_path, dry_run=True)
        print('DRY-RUN:', result)


if __name__ == '__main__':
    main()
