# PIF Portal

Flask and SQLite portal for bike requests, recipient details, and pickup tracking.

Current decisions are in [PROJECT_NOTES.md](PROJECT_NOTES.md). See
[database design and local admin commands](design/database.md) for optional bike
inventory, preview-first order corrections, backup/audit behavior and the ER diagram.

The navigation is organized around the work:

| Area | Pages |
| --- | --- |
| Orders | Order Desk (home), Order Explorer, New Order, Request Form Links |
| Workshop | Finished Bikes, Volunteer Hours, Volunteers, Volunteer Form Links, Reporting |

New Order is available under Orders. Menu labels, page headings and browser titles
match; page URLs remain unchanged. Reporting currently contains Bike Distribution;
volunteer-hours and workshop-activity summaries are planned extensions.

Create a volunteer profile once, then use its ID for both bike contributions and
time logs. These management pages use the existing staff login. Namesakes can have separate
profiles; email and phone are optional.

Finished Bikes provides tag search, shop filtering and a simple entry form with
suggested bike details and multiple volunteer selection. Numeric leading zeros
identify the same tag. An existing tag opens its original record so additional
contributions can be recorded without replacing the bike details. This is an
optional reference, not an availability or allocation system.

Volunteer Hours accepts a volunteer, work date, manual hours, shop and optional
activity/notes. Shop can be left unassigned. For example, `1.5` means 90 minutes.
Filters show totals across all matching entries. Staff can correct an entry or
void it with a reason; the audit retains its history. Bike contributions and hours
are independent: saving one never guesses or creates the other. Form retries do
not create duplicate submissions.

Volunteers use the separate **Log your time** form at
`/volunteer/log-hours?shop=B` (also `R` or `S`). Staff first add their profiles in
Volunteer Management. Volunteers search their name, select the correct volunteer
number if names match, and enter whole hours plus exact minutes. The date defaults
to today in America/Chicago; the shop comes from the link and remains editable.
Activity and notes are collapsed and optional. No staff login is needed.

“Remember me on this phone” is opt-in and stores a signed, HTTP-only volunteer-ID
preference for 180 days; it never grants staff access. “Not you?” clears it. Each
new visit has a blank duration, and unticking the preference on a successful save
also clears it. Successful submission shows a receipt instead of a time-history
page. Public lookup returns at most ten matching names/IDs after two characters;
it does not return contact details. Entries are explicitly attributed as
self-reported, not authenticated volunteer identities.

The staff hours page links to **Volunteer Form Links**, which provides one
reusable URL per shop. QR artwork and the production hostname are not configured
here. Open that page at the intended phone-reachable address before generating
QR codes; localhost links only work on the same computer. Network setup remains
outside this app's scope.

Finished Bike self-entry is available at `/volunteer/finished-bike?shop=B` (R/S
also supported), sharing the remembered volunteer with hours. Volunteers enter
the tag and details together, with make/model suggestions, wheel-size and A–F
bike-type dropdowns, the New Order picture guide and colour swatches. They can
add a note about their own
contribution (up to 2,000 characters). Each volunteer submits separately for the
same tag; the backend links each contribution and note to that volunteer ID. Shop comes from the QR link; finished time is recorded
automatically when saved. Staff still create volunteer profiles.

“Check tag” looks up a tag without saving. An existing tag shows its bike details
and requires explicit confirmation to add contributions. The confirmation is bound
to the reviewed record: the original shop, timestamp and bike details remain
unchanged. Retry protection covers both new bikes and added contributions, and no
hours are created. Staff inventory and hours pages link to the shared QR-link page,
which now provides both forms for each shop. The bike form also links directly
to volunteer hours for the selected shop.

Maintenance v4 adds optional `bike_contributions.notes`, visible beside each
contributor on the staff bike detail page. Names mentioned in notes do not create
additional attributions. Existing contribution records are preserved.

Enable these pages with the additive maintenance migration on a backed-up
database, with the app stopped (rehearse on a disposable copy first):

```sh
python scripts/admin_db.py --db /path/to/pif.db init
python scripts/admin_db.py --db /path/to/pif.db init --apply --actor USER --reason 'Enable workshop entry'
```

This creates/reuses the linked tables without importing staged spreadsheets or
changing orders. Existing maintenance installations can run the same command to
upgrade through v5, including contribution notes and volunteer joining/status fields. Pages show a setup message until initialization is complete.

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

Order Desk and Order Explorer share a search bar and All / Public / Pedal Partner /
Speciality filters. Search names, phone numbers (with or without punctuation),
emails, notes, bike tags, dates, and order details. Multiple words must all match
the same order line; `#123` finds exactly order 123. Search is applied before
status tabs or pagination, and type counts reflect the search across every
status. Both spellings of Specialty/Speciality use the Speciality filter.

Press Enter or Search to apply a query; type buttons apply immediately. Results
open on the All tab, with matching recipients expanded. Order ID links move
between the two views, and filter URLs can be bookmarked. Clear all resets the
view. Search and filtering do not change stored records.

Order Desk renders only the selected status, with 25 order groups per page. Groups
stay together, and search and status counts still cover all matching records.
Order actions preserve the selected page and filters, show progress immediately,
and prevent repeated clicks while saving. Cancel confirmation can be declined
without disabling the controls.

Order Desk uses compact cards with an explicit **View bikes** control on every
screen: one column on phones and two columns from 768px upward.
Open an order to see its recipient list, then **View details & actions** for one
bike. Only one order and one bike within it expand at a time. Contact details are
available separately; empty bike fields are omitted. Pickup has labelled date/tag
inputs and a **Save pickup** button. Order Explorer retains its table for detailed
data browsing; Order Desk uses a single shared set of cards and action forms.

New Order uses responsive recipient cards, a keyboard-accessible bike-picture
picker, and server validation that keeps entries when a field needs correction.
All website text, including field values and help text, uses the Sharpie-style
Patrick Hand font. Required/optional labels sit beside field names. Bike choice
buttons say **Choose from photos**; selecting a photo fills the indicated
recipient’s first or second preference.

Age is optional; supplied values must be whole years from 1 to 80. Invalid ages
show inline feedback and cannot be saved. Phone numbers format as digits are typed
and save as normalized digits only. Guidance asks for ten digits without a country
code. Phone and email are independently optional in staff and requester forms. Supplied
values are validated, and a missing email skips notifications without reporting
a delivery failure. A shared name alone does not merge contacts with no channels.
Each opened form has its own submission key: retrying that form cannot create a
duplicate, while a fresh form can create a legitimate repeat request. These new
forms also require a session-bound form token. Success and warning messages have
distinct appearances.

Under **Request Form Links**, staff can create a link for a selected shop,
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
show an on-screen receipt and do not send email. Staff New Order submissions send one confirmation per
recipient to the contact email after the order saves, subject to the email-mode
gates above. A multi-recipient submission therefore produces multiple emails;
this is not yet a single combined order confirmation.

Links use the same browser origin as the staff portal. Open the portal using the
intended requester-reachable address when generating links. Network exposure and
Tailscale configuration remain deployment responsibilities; this change does not
configure either. Keep a stable private `SECRET_KEY` in `.env` for sessions.

The July CSV data is currently for app development and testing. The production
historical import is being prepared separately from the latest Excel workbook. Keep that workbook
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

### Volunteer year-to-date summary

After a volunteer selects their name (or returns with it remembered), Log Hours
shows this year's exact hours/minutes, distinct bikes worked on, and a compact
weekly activity strip. No name selected means no summary. Totals cover all shops;
voided time is excluded and each bike counts once. Historical work must be linked
to that volunteer ID and dated to count. The save receipt shows the updated total.

Aggregate visibility through name selection is explicitly approved; no volunteer
login is required. The summary does not expose notes, contact details or individual
logs. Public time entry stays add-only; corrections and voids remain staff actions.

### Volunteer joining dates and status

Volunteers management includes Joined on, an Active/Inactive flag, and an
**Edit date / status** link. New profiles default to today and Active; leave the
date blank if unknown. Inactive volunteers retain all history, but cannot be
selected in the volunteer-facing entry forms until staff reactivate them.
Staff can still record historical work. Updates are audited and protect against
concurrent edits. Maintenance v5 adds these fields through the existing backed-up
`admin_db.py init` command; only the disposable preview has been upgraded so far.

For the current development branch, see [commit, merge and local sync instructions](design/git-handoff.md).
