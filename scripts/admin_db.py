"""Preview-first local database maintenance. Run --help for commands."""

import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import Config
from admin_tools import (connect, read_order, order_preview, initialize, edit_order,
                         bike_preview, add_bike, lookup_bike)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', default=Config.DB_PATH or 'data/processed/pif.db', help='Existing SQLite database path')
    commands = parser.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init', help='Initialize or upgrade workshop and audit schema; preview by default')
    show = commands.add_parser('show-order', help='Read one order line')
    show.add_argument('order_id', type=int)
    edit = commands.add_parser('edit-order', help='Preview changes to order-owned fields')
    edit.add_argument('order_id', type=int)
    edit.add_argument('--changes', required=True, help='JSON object; use quoted text values or null')
    edit.add_argument('--version', help='Version printed by the preview; required with --apply')
    add = commands.add_parser('add-bike', help='Preview adding an optional inventory record')
    add.add_argument('--values', required=True, help='JSON object matching the inventory source columns')
    lookup = commands.add_parser('lookup-bike', help='Exact global tag lookup')
    lookup.add_argument('tag')
    for command in (init, edit, add):
        command.add_argument('--apply', action='store_true')
        command.add_argument('--actor', help='Existing username for audit attribution, not authentication')
        command.add_argument('--reason', help='Reason recorded alongside the change')
    args = parser.parse_args(argv)
    try:
        if args.command == 'init':
            with closing(connect(args.db)):
                pass  # Fail closed if the intended database does not exist.
            result = (initialize(args.db, args.actor, args.reason) if args.apply else
                      {'applied': False, 'planned_tables': ['bike_inventory', 'volunteers', 'bike_contributions', 'admin_changes', 'volunteer_hours', 'workshop_submissions'],
                       'planned_columns': {'bike_contributions': ['notes'], 'volunteers': ['joined_on', 'is_active']},
                       'message': 'Stop the app; rerun with --apply --actor USER --reason TEXT.'})
        elif args.command == 'edit-order':
            changes = json.loads(args.changes)
            if args.apply:
                result = edit_order(args.db, args.order_id, changes, args.version, args.actor, args.reason)
            else:
                with closing(connect(args.db)) as conn:
                    result = order_preview(conn, args.order_id, changes)
        elif args.command == 'add-bike':
            values = json.loads(args.values)
            if args.apply:
                result = add_bike(args.db, values, args.actor, args.reason)
            else:
                with closing(connect(args.db)) as conn:
                    result = {'applied': False, 'new_bike': bike_preview(conn, values)}
        else:
            with closing(connect(args.db)) as conn:
                result = (read_order(conn, args.order_id) if args.command == 'show-order'
                          else lookup_bike(conn, args.tag))
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except (ValueError, OSError, sqlite3.Error) as exc:
        parser.exit(1, f'No change applied: {exc}\n')


if __name__ == '__main__':
    main()
