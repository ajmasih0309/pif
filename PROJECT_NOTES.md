# Project context

Updated 2026-10-08. This file records decisions for future work on PIF Portal.

- User prefers the compact Order Desk cards on desktop too. Supersedes the
  mobile-only layout below: one column below 768px, two columns above. Shared
  `_order_cards.html` and `order_cards.js` replace the duplicate desktop tables
  and mobile-only template/script. Order Explorer keeps its table. Search results
  stay collapsed until opened, with exact Order ID links retained. No workflow,
  business-rule, database or email-setting changes.

- Mobile Order Desk refinement: below 768px, compact order cards replace stacked
  table cells. Explicit View bikes/Hide bikes and recipient View details & actions
  controls; one expanded order and one bike per order. Native details controls
  with JS accordion fallback, separate contact details, compact nonempty bike
  facts, full notes and labelled pickup date/tag/Save pickup. Desktop unchanged.
  Actions reuse existing endpoints, confirmation, pending feedback and return
  filters/page. No new business rules or database changes. Mobile form regression
  tests cover contact, both cancellation paths, restore and completion on a
  disposable database; browser checked 390px multi-bike expansion and pickup.
  All 143 Python tests and 3 Node order-action tests pass. Changes are uncommitted
  after the user's dca6fec commit; no push or merge performed in this pass.

- Git handoff prepared 2026-10-08: application changes stay on
  `codex/database-cleanup`, separate from `codex/spreadsheet-cleanup`. User will
  commit/push/merge and sync locally using `design/git-handoff.md`. Remote main
  fetched and primary checkout clean at 2fd083b. No commit, push, merge, active
  schema upgrade or historical-data cutover performed during handoff. Refreshed
  README, old page names and admin CLI help. Full 141 Python / 3 Node checks pass.

- Typography preference confirmed: Sharpie throughout the website. Use the
  existing Patrick Hand font for entered values, dropdowns, dates, help/error
  text, colour options and volunteer totals as well as labels and headings.
  This replaces the earlier plain-font overrides for readability.

- Follow-up numeric entry refinement: phone now formats partial numbers as each
  digit is typed and supports deletion across separators. Help asks for 10 digits
  without +1 or 1. Server normalization remains unchanged. Age still permits a
  blank value or whole years 1–80; invalid input now shows an immediate inline
  message and blocks submission. Copied recipient details refresh validation.

- New Order refinement (2026-10-08): required/optional indicators share one
  label style, including every recipient field; optional status is no longer
  inside dropdown placeholders. Added field guidance and explicit first-choice
  versus backup-choice instructions. Photo buttons say Choose from photos and
  the dialog identifies the recipient and choice being filled.
- User explicitly requested optional age validation of 1–80 whole years, now
  enforced in shared staff/requester HTML and server validation. Existing data
  unchanged. Contact phone formats complete numbers as (479) 555-0123, including
  pasted +1 numbers; server continues storing only normalized digits. Phone and
  email remain optional. All 141 Python and 3 Node tests pass; browser checked
  phone display, age range and photo selection. Preview form left empty for review.

- Order-flow review (2026-10-08): prioritize New Order → Open, Open →
  Contacted/Cancelled, Contacted → Completed/Cancelled and Cancelled → Open.
  Explain assumptions and basic requirements before enforcing new business
  constraints. Inventory and volunteers may remain empty; orders must work
  independently. Current pickup accepts an unregistered positive integer tag,
  with no inventory lookup or tag uniqueness check. Restore always returns Open.
  See `design/order-workflow-review.md` for existing rules and tag limitations.
- Added regression coverage for the full flow with blank contact channels and
  all workshop tables empty; existing coverage also runs without inventory schema.
  Only user-facing stale-action copy changed (My Desk → Order Desk); no new
  validation or business rule was introduced. All 139 Python tests and 3 Node
  order-action tests pass.
- Previous temporary preview disappeared. Replacement port-5004 preview uses an
  isolated copy at the primary checkout's ignored
  `data/previews/order-review-20261008-a770c3/preview.db`; `run.py` in that folder
  runs this development worktree with email and scheduler disabled. Existing
  staff credentials retained. Maintenance initialization applied only to that
  preview copy, with backup. Active database and staging remain untouched.

- Order reconciliation resumed by explicit user request (2026-10-05): match
  staging to the cleaned current database, use its correct values for confident
  matches, and preserve conflicting field details plus both sets of instructions
  in Notes. Keep ambiguous matches for review. No active database cutover.

- Main baseline: `2fd083b` (responsive layouts, navigation, search and footer),
  following `a234915` (workflow fixes, search, requester links, email previews).
- Preserve the simple Sharpie-on-whiteboard design. Pagination belongs above
  tables. Order links belong in an Order ID column, not under recipient names.
- Existing operations cover request intake, Open → Contacted → Completed,
  cancellation/restoration, search, filtering and one-use requester links.
- Email provider is Google Workspace for `@pedalitforward.org`. No mailbox
  credentials have been supplied. Stay in preview mode with live delivery and
  scheduled reminders disabled; never send test messages to requesters.
- Home hosting and Tailscale/network configuration are outside app scope.
- The current database contains July-era development data plus later app edits.
  The latest workbook must be cleaned separately before a one-time cutover.
  Do not replace the active database or delete suspected duplicates by guessing.
- Older `orders_data.csv` and normalized July `orders.csv` have different ID
  namespaces. Their rows cannot be merged by order ID. Preserve original files,
  provenance, recent edits, backups and a reconciliation report.
- New scope: remove obsolete code; provide safe order-line corrections for an
  administrator (a local CLI is acceptable); add an optional bike-inventory
  lookup and document the database relationships.
- Bike inventory is now in scope for optional lookup only. An order must remain
  usable without a matching inventory record. Source columns: Timestamp, Shop,
  Bike Tag #, Make, Model, Colour, Wheel Size, Bike Type, Volunteer's Name.
- Bike tags are unique across all shops and years (confirmed by the user).
- Latest workbook: `data/raw/PIF 2025 .xlsx` in the primary checkout, received
  2026-10-04. Spreadsheet-specific cleanup rules still require source review.
- Ignore the workbook's `Date Picked Up` column. Keep `Recently Deleted`,
  `bad form` and `Online Form Responses` separate from active orders for review.
- Prepared work is isolated in managed worktrees: `codex/database-cleanup` for
  code, local admin tools and inventory schema; `codex/spreadsheet-cleanup` for
  workbook staging. These changes have not been merged or applied to the active DB.
- First workbook staging retains 6,251 candidate order rows and 15,470 inventory
  rows; 445 repeated tag groups involve 898 rows. User now authorizes earliest
  timestamp to choose bike details (source row breaks ties), keeping all contributor
  labels in linked records. Ignore missing-tag inventory rows and default unknown,
  multiple or missing inventory shops to B. Preserve the raw source and audit trail.
  Use volunteers plus bike_contributions, with nullable volunteer IDs until matched.
  Numeric leading zeros identify the same bike. Exclude explicit placeholder tags
  TEST/TEST2/TEST3/Need/Trailer bike/Xxxx; review other nonnumeric tags.
  Revised inventory staging: 14,995 unique tags, 15,461 contribution entries,
  9 excluded rows and 15 source shop defaults. Four nonnumeric tags remain flagged.
  Pickup-to-status mapping and preservation of recent app edits remain cutover work.
- Order cleanup rules confirmed 2026-10-05: email and phone are optional, including
  blank formula results. Missing order dates use valid `Pick up` values; otherwise
  remain for review. A usable recipient name fills a missing contact name. Remove
  standalone relationship labels (Son/Daughter/Child 1/etc.) from recipient names,
  retaining the source labels for review. Missing/ambiguous order shops default to B.
  Latest pass: 97 dates filled, 44 contact names filled, 52 labels cleared, 256 shops
  defaulted. No active DB cutover. Staff/requester forms now also permit blank phone
  and email; notifications are skipped when no email exists. Supplied values still
  get format validation, and contacts with no channels are not merged by name alone.
- Dashboard now counts Completed order lines by pickup date, without a recipient
  join that could multiply or hide legacy orders. Comparisons share shop/month
  filters; year defaults to the current year and includes historical pickup years.
  Invalid filters are handled safely. The page explains the metric and offers reset.
- Terminology: the user wants existing list totals called orders, not bike requests.
  One multi-bike submission creates several recipient/order-line records today;
  overall count calculations are unchanged pending the grouped-order count choice.
  Dashboard labels explicitly say Bikes Completed and count each completed bike
  separately, including multiple bikes in the same order. Intake explains one
  recipient per bike. No schema or historical-data changes are part of this pass.
- Verification: 94 app Python tests pass, including seven dashboard regressions.
  The last data pass had 11 inventory/order cleanup tests passing; prior
  3 Node checks remain applicable (no frontend changes). Full relational inventory
  rehearsed on a disposable database copy: 14,995 bikes, 15,461 contributions,
  existing orders preserved, integrity and both inventory FK checks OK.
- Dashboard month labels now use Jan–Dec, retaining numeric filter values.
  Read-only 2025 audit confirms 3,396 completed bikes for B/R/S, equal to the
  sum of bikes across 1,342 display groups. Missing shops, repeated tags and
  order-date versus pickup-date differences still need report reconciliation;
  see design/dashboard-count-review.md. No historical data was changed.
- Reconciliation lives in codex/spreadsheet-cleanup: 5,190 unique app matches from
  6,251 source rows; 224 ambiguous, 219 possible, 618 without confident matches.
  Recovered pickup dates resolve 888 missing order dates under the earlier rule.
  721 of 1,915 previously flagged rows are cleared; 1,194 remain, plus six newly
  flagged current-data cases. All rows and 522 unmatched current app lines remain
  preserved. The review output is PIF-reconciled-staging.xlsx; full audit/snapshot
  under data/processed/order-reconciled-20261005-v2 in the primary checkout.
  Inventory/contributions unchanged; 17 reconciliation and 11 cleanup tests pass.

## Reporting navigation refinement — 2026-10-06

- Latest placement: Reporting lives inside Workshop, with no separate top-level
  link. Workshop and Reporting are highlighted when viewing /dashboard.

- User removed the separate top-level New Order shortcut; New Order remains under
  Orders. Impact Dashboard is now Reporting in navigation, heading and browser title.
  Existing completed-bike report is identified as Bike Distribution within it.
  /dashboard URL and its filters/count logic remain unchanged.
- User is considering broader reports. Proposed next sections: Volunteer Hours
  (nonvoid hours by month/shop, distinct volunteers who logged time) and Workshop
  Activity (distinct finished bikes, recorded contributions). These additional
  sections are suggestions, not implemented reports. Keep unknown/unassigned data
  explicit and do not equate contribution entries with distinct bikes.

## Portal page names and navigation — 2026-10-06

- PIF Portal is the umbrella name. Orders is the first navigation group: Order Desk
  (formerly My Desk; still the home page), Order Explorer (formerly Data Explorer),
  New Order, Request Form Links (formerly Requester Links).
- Workshop groups Finished Bikes, Volunteer Hours, Volunteers, Volunteer Form Links.
  The latter is now directly discoverable in navigation. Detail/edit pages highlight
  their parent section. Impact Dashboard replaces Dashboard/Analytics Dashboard and
  stays directly accessible; New Order also stays as a prominent top-level shortcut.
- Page headings, browser titles and cross-links use the same names. Related staff
  forms use Record Finished Bike, Log/Correct Volunteer Hours, Edit Volunteer and
  Volunteer Summary. Existing routes, QR URLs and public entry workflows unchanged.
- 138 Python tests pass. Renamed main titles/headings verified in the local browser;
  grouped mobile navigation verified at 390px. No data/schema changes in this pass.

## Volunteer joined date and active status — 2026-10-06

- Volunteers management now shows Joined on and Active/Inactive status. New profiles
  default to today's Chicago date and Active; date can be blank if unknown.
  Staff can edit date/status per profile, including reactivation, with validation,
  optimistic conflict checks, atomic audit and retry protection. No deletion.
- Inactive profiles remain in management/history and can be used by staff for
  historical work. Public name searches, remembered-name selection and new public
  hours/bike submissions require active profiles. Existing work is preserved.
- Maintenance v5 adds nullable volunteers.joined_on and is_active INTEGER NOT NULL
  DEFAULT 1 CHECK(is_active IN (0,1)). Existing people get active status and unknown
  joining dates. Backup/audit upgrade applied only to disposable port-5004 preview.
  Web requests never migrate; active DB and staging remain unchanged.
- 138 Python tests pass, including upgrades/backups/rollback, invalid/stale edits,
  audit failures, inactive public selection and preserved history. Volunteers page
  visually verified; no test profiles were added to the real-data preview.

## Volunteer yearly summary — enabled, 2026-10-06

- User explicitly approves everyone's aggregate totals being visible after name
  selection. No summary should show without a selected/remembered volunteer.
  Log Hours remains add-only; no public edit, void or delete capability.
- This approval resolves the earlier automatic review block on aggregate access.
  The remembered-name cookie remains a preference, not identity verification.
- Log Hours now loads the selected person's summary through a token-checked,
  read-only POST /volunteer/impact. No public contact details, notes or raw logs.
  Switching names cancels stale loads; no selection hides the panel entirely.
  Remembered people get a server-rendered summary. The receipt shows updated totals.
- Calendar-year totals run through today across shops: nonvoid minutes by work_date,
  distinct inventory IDs by contribution recorded_at. Offset timestamps convert
  to America/Chicago; naive historical timestamps use local date. Undated,
  unparseable and unlinked contributions do not count for a person's year.
  Repeated contributions to one bike count once; active weeks union both sources.
- Two compact rows show active/empty/future weeks, with accessible text. No ranking
  or streak pressure. Staff preview remains /volunteers/<id>/impact.
- Browser checks on a separate synthetic database verified initially hidden state,
  switching volunteers, saving 2h17m, updated total, remembering and Not you hiding
  the summary. Only synthetic test time was added; active data/staging untouched.
- Verification: 132 Python tests pass; volunteer JavaScript parses successfully.
  Port-5004 preview refreshed with the completed flow; synthetic test server stopped.

## Finished Bike form refinements — 2026-10-06

- Tag, shop and bike details share one always-visible section. New tag entry keeps
  optional make/model suggestions; existing tags retain the contribution confirmation.
- Wheel sizes use standard dropdown options (including Other); bike type uses A–F
  and the same six pictures as New Order. Basic colours use a dropdown with named
  swatches, including Multicolour/Other. Blank details remain allowed. New public
  submissions validate listed choices; old inventory values are not rewritten.
- The form links directly to volunteer hours, preserving the selected shop.
  Remembered volunteer preference continues to be shared between both forms.

## Individual Finished Bike contributions — 2026-10-06

- Supersedes the earlier public helper-selection flow below: each volunteer reports
  their own contribution separately using the same bike tag. Optional notes belong
  to that contribution. A name mentioned in notes does not create attribution.
- Public form now submits one volunteer ID, with a note of up to 2,000 characters.
  Staff bike details show each contribution's volunteer ID, timestamp and note.
  Original bike details remain unchanged; hours stay separate. Staff batch entry
  remains available. Old public helper selections are rejected for review.
- Maintenance v4 adds nullable bike_contributions.notes, preserving existing rows,
  IDs and provenance. Explicit CLI initialization backs up and audits the upgrade;
  web requests never migrate. Only the disposable port-5004 preview was upgraded.
- 125 Python tests and 3 Node tests pass, including two-person attribution to one
  bike, note escaping, retries, schema upgrades and rollback. Phone layout checked
  at 390px. Active database and historical staging remain unchanged; email disabled.

## Working conventions

- Next development step approved 2026-10-05: volunteer-facing Finished Bikes is now
  implemented at `/volunteer/finished-bike?shop=B`, with R/S supported. Shared
  remember preference with hours, name lookup, optional bike suggestions, up to
  20 extra helpers and automatic UTC finished timestamp. Staff create profiles.
- Existing tags require a reviewed-record confirmation before contributions are
  added. Original bike details/shop/timestamp remain unchanged. Check tag and
  helper searches never save; retries are idempotent. No hours are inferred.
  Both form URLs are listed per shop for QR creation. No schema migration.
- Verified 122 Python and 3 Node tests, plus synthetic phone browser checks for
  name/helper lookup, checking without saving, two-contributor new bike, remembered
  next entry and duplicate-tag confirmation. Active DB and staging untouched.

- Volunteer-facing flow clarified 2026-10-05: staff alone add volunteers through
  management; volunteers scan a reusable shop QR, look up their own name, and can
  opt into remembering it on their phone. Hours and Finished Bikes are ultimately
  volunteer-facing, but this pass focuses only on hours. Management is accepted.
- Added `/volunteer/log-hours?shop=B` (R/S supported), with name lookup, signed
  180-day remember preference, Not you/forget, America/Chicago date default,
  editable QR-derived shop, exact hours/minutes and collapsed optional details.
  No staff login for submission; no public contact details, time history or edits.
  Hours are self-reported with explicit attribution. No new tables or migration.
- Staff hours page provides shop-specific URLs for QR creation. Actual QR artwork
  waits for the phone-reachable production address; network exposure is unchanged.
- Verification now 116 Python tests and 3 Node tests passing. Browser check at
  390px used a separate synthetic database: search/select, 2h17m save, receipt,
  remembered next visit with blank duration, and forgetting all passed. The new
  real preview form is open on port 5004, with original preview data preserved.

- Workshop pages added 2026-10-05: Finished Bikes, Volunteers and Volunteer Hours
  under one navigation menu, using existing staff authentication. The user chose
  a simple entry page and manual hours: volunteer, work date, hours, shop and
  optional activity/notes. Shop may be unassigned for non-shop activity.
- Shared volunteer IDs connect independent bike contributions and time sessions.
  Namesakes require explicit different-person confirmation; optional contact
  fields are not required. New bike entries support multiple volunteers,
  remembered shop and suggested details. Existing tags keep original details
  and allow additional contributions. No automatic time inference or allocation.
- Additive maintenance v3 adds volunteer_hours and workshop_submissions. Time
  entries store integer minutes, enforce daily totals <=24 hours, allow audited
  corrections with version checks, and retain voided records outside totals.
  Form retries are idempotent. Staged spreadsheets have not been imported.
- Workshop verification: 108 Python tests and 3 existing Node tests pass; workshop
  JavaScript parses successfully. Schema applied only to the disposable port-5004
  preview database, with backup and email disabled. Browser policy blocked reload
  of the existing preview tab, so visual verification remains outstanding.

- Run tests against temporary databases and mock SMTP/scheduler startup.
- Keep data, backups, credentials and email previews out of Git.
- Retain the tested repair and July migration tools until the production data
  migration is complete. Older unsafe prototype importers are not authoritative.
- Keep spreadsheet cleanup separate from application/schema work.
