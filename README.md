# PIF Portal

Flask and SQLite portal for bike requests, recipient details, and pickup tracking.

From the project root, activate the existing environment:

```sh
source .venv/bin/activate
```

For an existing imported database, run these repairs before starting the updated app:

```sh
python scripts/fix_duplicate_shops.py
python scripts/fix_person_ids.py
```

Both scripts use `DB_PATH` from `.env` (default: `data/processed/pif.db`), accept
`--db PATH`, and back up the database in a sibling `backups` directory before
changing it. They can be run again safely. The person-ID repair preserves existing
IDs and order records, and stops if it encounters ambiguous IDs or an unexpected
schema. Stop the app while applying database repairs.

Run the app:

```sh
python app.py
```

The development server listens on port 5003. Email defaults to local preview mode;
no SMTP connection is made, even if mailbox credentials are present. Preview HTML
files are saved under `data/email_previews/` (git-ignored and not served by the app).
Open a file locally to review its subject, intended recipient, and message. These
files contain private order details; remove them when no longer needed.

Email settings are loaded from `.env` into Flask. Safe defaults are:

```dotenv
EMAIL_MODE=preview
EMAIL_PREVIEW_DIR=data/email_previews
EMAIL_LIVE_ENABLED=false
EMAIL_REMINDERS_ENABLED=false
```

`EMAIL_MODE=disabled` suppresses email entirely. For an explicitly authorized
delivery test, `EMAIL_MODE=test` requires one `MAIL_TEST_RECIPIENT`; both the To
header and SMTP envelope use only that address, with a `[TEST]` subject prefix.
It never falls back to the requester or sender when the test address is missing.
SMTP needs `MAIL_SERVER`, `MAIL_PORT` (STARTTLS, default 587), `MAIL_USERNAME`,
`MAIL_PASSWORD`, and `MAIL_DEFAULT_SENDER` (a plain email address).

Real requester delivery requires both `EMAIL_MODE=live` and
`EMAIL_LIVE_ENABLED=true`. Only enable these after the sending mailbox and message
content are approved. Daily pickup reminders have an independent
`EMAIL_REMINDERS_ENABLED` switch and stay off while using historical/test data.
Unknown modes, missing configuration, and delivery failures block sending without
undoing saved orders. Preview files are never queued for later delivery. Changing
email settings requires an app restart. No account credentials are included in the
repository, and no provider-specific mailbox setup has been performed.

My Desk and Data Explorer share a search bar and All / Public / Pedal Partner /
Speciality filters. Search names, phone numbers (with or without punctuation),
emails, notes, bike tags, dates, and order details. Multiple words must all match
the same bike request; `#123` finds exactly order 123. Search is applied before
status tabs or pagination, and type counts reflect the search across every
status. Both spellings of Specialty/Speciality use the Speciality filter.

Press Enter or Search to apply a query; type buttons apply immediately. Results
open on the All tab, with matching recipients expanded. Order ID links move
between the two views, and filter URLs can be bookmarked. Clear all resets the
view. Search and filtering do not change stored records.

My Desk renders only the selected status, with 25 order groups per page. Groups
stay together, and search and status counts still cover all matching records.
Order actions preserve the selected page and filters, show progress immediately,
and prevent repeated clicks while saving. Cancel confirmation can be declined
without disabling the controls.

New Order uses responsive recipient cards, a keyboard-accessible bike-picture
picker, and server validation that keeps entries when a field needs correction.
Each opened form has its own submission key: retrying that form cannot create a
duplicate, while a fresh form can create a legitimate repeat request. These new
forms also require a session-bound form token. Success and warning messages have
distinct appearances.

Under **More → Requester Links**, staff can create a link for a selected shop,
order type, and optional Pedal Partner. Links expire after 1, 7 (default), or 14
days. Copy the link immediately after creation and share it manually; the full
link is not retained in the history. The history shows Unused, Used, Expired, or
Revoked status and allows staff to revoke unused links. These routes add the
`request_invites` and `order_submissions` tables automatically without changing
historical orders.

A requester can open a link repeatedly, correct errors, and include multiple
recipients. One successful submission creates Open orders and consumes the link
in the same database transaction. Concurrent submissions and retries cannot
create another request. The requester sees no staff navigation or contact
suggestions and cannot change staff-selected routing. Only token hashes are
stored; link pages disable caching and referrer sharing. Requester submissions
show an on-screen receipt and do not send email. Staff order notifications retain
their existing behavior.

Links use the same browser origin as the staff portal. Open the portal using the
intended requester-reachable address when generating links. Network exposure and
Tailscale configuration remain deployment responsibilities; this change does not
configure either. Keep a stable private `SECRET_KEY` in `.env` for sessions.

The July CSV data is currently for app development and testing. The production
historical import is waiting for the latest Excel workbook. Keep that workbook
unchanged, inspect its sheets and overlaps, then prepare a cleaned staging import
and a reconciliation report before switching the app to the new data. Workbook row
numbers are not app order IDs. Missing dates and possible duplicate requests need
source review; matching names alone are not enough to merge requests.

`scripts/migrate_history.py` rehearses cleanup of the **existing July normalized
CSV set only** (`orders`, `contacts`, `recipients`, `pedal_partners`, and `shops`).
It is not an importer for the upcoming Excel workbook or the older
`orders_data.csv`, which uses a different order-ID namespace. Current app values
win when they differ from this older baseline, including cleared fields; later
app records, original IDs, audit fields, users, and inventory tables are retained.

Run a preview into a new directory:

```sh
python scripts/migrate_history.py --output-dir data/processed/history-preview
```

This leaves the active database unchanged and writes `preview.db`, `report.json`,
and `summary.md`. The report includes source hashes, field changes, preserved app
edits, missing facts, and possible duplicates. It does not delete orders or guess
missing values. Reports and database copies contain private data and stay under
the git-ignored `data` directory.

For an intentional July-data cleanup only, `--apply` backs up to `before.db`,
locks out concurrent writes, validates links and database integrity, and commits
once in a transaction. A migration ledger makes a repeat run a no-op and rejects
different source files after the first application. Stop the app before applying.
No such application is needed while waiting for the latest workbook.

Run the automated checks (temporary databases; no real email):

```sh
python -m unittest discover -s tests -p 'test_*.py' -v
```

Submission-feedback checks use Node's built-in test runner (no npm packages):

```sh
node --test tests/test_order_actions.cjs
```
