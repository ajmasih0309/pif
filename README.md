# PIF Portal

PIF Portal is a Flask and SQLite application for Pedal It Forward. It supports
order intake and pickup tracking, staff-managed volunteer/workshop records, and
public volunteer entry forms. The interface uses the Sharpie-on-whiteboard style
throughout.

The current code baseline is `main` at `00c864b`. The active database and private
configuration are intentionally outside Git and were not inspected by the latest
documentation audit.

## What the application currently does

| Area | Implemented capabilities |
| --- | --- |
| **Orders** | Order Desk, Order Explorer, New Order, full-text search, type filters, requester links, and line-by-line status actions. |
| **Order workflow** | New submissions create Open lines. Open lines can be Contacted or Cancelled; Contacted lines can be Completed or Cancelled; Cancelled lines restore to Open. |
| **Pickup policy** | Public orders have a 7-day window and Pedal Partner orders a 28-day window after Contacted. Speciality has no fixed deadline. Completion requires a pickup date and a positive whole-number tag; inventory matching is not required. |
| **Reporting** | Bike Distribution counts completed order lines by pickup date, shop, month, and year. Each completed recipient bike counts separately. |
| **Workshop** | Staff can manage volunteers, record finished bikes and contributions, and record/correct/void volunteer hours after the workshop schema is initialized. |
| **Volunteer entry** | Volunteers can use a shop-specific URL to self-report hours or a finished-bike contribution, select an active profile, and optionally remember that profile on their device. |
| **Email** | Order confirmation, pickup-ready, and pickup-reminder templates support preview, disabled, test-sink, and explicitly enabled live SMTP modes. |

Orders and inventory remain independent by design. A completed order can use a
new numeric tag even when the Finished Bike Inventory and volunteer tables are
empty. See [order workflow](design/order-workflow-review.md) for the exact
constraints and known tag limitations.

## Documentation map

- [Current project decisions](PROJECT_NOTES.md)
- [Architecture](design/architecture.md)
- [Database design and maintenance](design/database.md)
- [Order workflow](design/order-workflow-review.md)
- [Dashboard metric review](design/dashboard-count-review.md)
- [Operations and deployment checklist](design/operations.md)
- [Technical audit](design/technical-audit.md)
- [Git workflow and handoff](design/git-handoff.md)

The workbook cleanup and historical-data cutover are deliberately separate from
application development. They remain pending and must not replace the active
database without a reviewed rehearsal and backup.

## Local setup

The project expects a local virtual environment at `.venv`.

```sh
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

Running `app.py` starts Flask’s development server on `http://127.0.0.1:5003`.
This is for local development only; a production serving model has not yet been
defined. See [operations](design/operations.md) before any deployment.

If activation is unavailable, use the project executable directly:

```sh
.venv/bin/python app.py
```

## Configuration and email safety

Configuration is loaded from `.env`, which is ignored by Git. Never commit
credentials, databases, spreadsheet exports, or email previews.

Safe development defaults are:

```dotenv
EMAIL_MODE=preview
EMAIL_PREVIEW_DIR=data/email_previews
EMAIL_LIVE_ENABLED=false
EMAIL_REMINDERS_ENABLED=false
```

- `preview` writes a local HTML preview and does not connect to SMTP.
- `disabled` suppresses all email work.
- `test` sends only to the one configured test recipient.
- `live` requires both `EMAIL_MODE=live` and `EMAIL_LIVE_ENABLED=true`.
- Pickup reminders require their separate `EMAIL_REMINDERS_ENABLED=true` switch.

Email delivery happens after a successful order/status transaction. A missing
email address or mail failure does not undo the saved order action. The code uses
generic SMTP with STARTTLS; it does not contain a Gmail API or OAuth integration.

## Workshop schema setup

Workshop pages require an explicit additive setup on a backed-up database. Stop
the app first and rehearse against a disposable copy before any `--apply` use.

```sh
python scripts/admin_db.py --db /path/to/pif.db init
python scripts/admin_db.py --db /path/to/pif.db init --apply \
  --actor USER --reason 'Enable workshop entry'
```

This setup creates or upgrades workshop/audit tables without importing staged
spreadsheets or changing order history. It backs up the database before writes.
The staff-maintained workshop flows use volunteer IDs to link contributions and
time logs; public forms accept only active volunteers.

## Data maintenance boundaries

- `scripts/admin_db.py` previews and applies controlled order-line corrections,
  inventory inserts, backups, and audits.
- `scripts/migrate_history.py` rehearses migration of the older normalized July
  CSV set only. It is **not** the importer for the pending Excel workbook.
- `scripts/fix_duplicate_shops.py` and `scripts/fix_person_ids.py` are legacy
  repair tools. Use them only with a known database path and a backup.
- `data/` is ignored because it contains private database, workbook, staging,
  backup, and preview material.

See [database design](design/database.md) for schema relationships, limits, and
the required cutover safeguards.

## Tests

Run Python checks with safe email overrides and temporary test databases:

```sh
PYTHONDONTWRITEBYTECODE=1 \
EMAIL_MODE=disabled \
EMAIL_LIVE_ENABLED=false \
EMAIL_REMINDERS_ENABLED=false \
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```

The 2026-11-23 audit passed **155 Python tests in 7.09 seconds**. The repository
also contains a Node built-in test:

```sh
node --test tests/test_order_actions.cjs
```

Node was unavailable in the audit shell, so that check needs to run in an
environment where Node is installed. No test should send real email or use the
active database.

## Current limitations requiring an owner decision

- The direct entry point uses Flask debug mode and is not a production deployment
  design.
- Staff accounts have no role model; authenticated staff have the same portal
  capabilities.
- The session secret must be configured privately; production startup does not
  currently enforce it.
- Public volunteer selection is self-attribution, not volunteer authentication.
- Reporting beyond Bike Distribution is proposed but not implemented.
- Historical workbook migration and final data reconciliation are not complete.

The [technical audit](design/technical-audit.md) records the full verified
inventory, evidence, limitations, and decisions still needed.
