# PIF Portal project notes

Updated **2026-11-23** after a read-only source audit of `main` at `00c864b`.
This is the current decision record. Earlier implementation history was
consolidated here to avoid treating old previews, test totals, or Git handoffs as
current state.

## Current application decisions

### Orders

- **PIF Portal** is the product name. Navigation groups pages as **Orders** and
  **Workshop**. Orders contains Order Desk, Order Explorer, New Order, and Request
  Form Links. Workshop contains Finished Bikes, Volunteer Hours, Volunteers,
  Volunteer Form Links, and Reporting.
- The home page is **Order Desk**. It uses compact cards at every width: one column
  below 768px and two columns at or above 768px. Order Explorer remains the table
  view for detailed review.
- Use **orders** for list totals, not “bike requests.” A multi-bike intake creates
  one `orders` row per recipient/bike line; the application has no order-header
  table. Card groups are a display convention, not a durable order identity.
- Shared search covers order data and supports All, Public, Pedal Partner, and
  Speciality. Search/filtering is read-only and happens before status tabs and
  pagination.
- New Order and requester forms allow optional email and phone. Supplied values
  are validated; phone is saved as normalized digits. Age is optional but, when
  present, must be a whole number from 1 to 80.
- Keep the Sharpie-on-whiteboard design and Patrick Hand typography throughout,
  including entered field values and help/error text.

### Order workflow and pickup policy

- The required initial workflow is: New submission → Open; Open → Contacted or
  Cancelled; Contacted → Completed or Cancelled; Cancelled → Open.
- Actions operate per order line. Completing one recipient does not complete every
  line from a multi-recipient submission.
- Public pickup windows are 7 calendar days and Pedal Partner windows are 28
  calendar days from Contacted in America/Chicago. Speciality has no fixed
  deadline. The deadline does not auto-cancel or block pickup.
- Completion currently requires a valid pickup date and a positive whole-number
  bike tag. The tag may be new; no inventory lookup, availability rule, or tag
  uniqueness rule is enforced for an order. Do not add one without an approved
  business rule.
- Pickup-ready mail and optional reminder mail must never block a saved order
  transition. Reminders are checked every 15 minutes only when explicitly enabled;
  missing email, invalid contact dates, Speciality, expired, cancelled, and
  completed lines are skipped.

### Workshop and volunteer entry

- Finished Bike Inventory is an **optional lookup and contribution record**, not an
  inventory-allocation system. Orders must remain usable if inventory is empty or
  unavailable.
- Bike tags are unique globally across shops and years in the inventory model.
  Numeric leading zeros identify the same bike. Orders still use legacy numeric
  tag storage, so inventory and order tag formats are not fully aligned.
- One bike can have multiple contributions. Each public volunteer reports their
  own contribution and optional note; a name in a note does not create attribution.
  Hours are separate and never inferred from a contribution.
- Staff add volunteer profiles. Public forms let volunteers look up active names,
  select their own profile, and optionally remember it on that device for 180 days.
  This is an attribution convenience, not identity authentication.
- Volunteers have an optional joined date and active flag. Inactive people retain
  history but cannot be selected on public forms until staff reactivate them.
- Volunteer hours are manually entered in exact whole minutes. Public entry is
  add-only; staff corrections/voids require a reason, version check, and audit.
- Everyone’s aggregate year-to-date totals can appear only after a volunteer is
  selected or remembered. The summary does not expose contact details, notes, or
  individual logs.

### Reporting

- Reporting is under Workshop. The current implemented report is **Bike
  Distribution**.
- It counts completed order lines as bikes completed, using `pickup_date`, selected
  shop, month, and year. It does not count grouped requests or distinct inventory
  tags.
- Volunteer-hours and workshop-activity reporting are proposed future work. Keep
  unknown/unassigned data explicit and do not equate contributions with distinct
  bikes without defining the metric.

## Email and safety

- SMTP setup is private and must remain in `.env`; it is never committed or copied
  into documentation.
- Default development behavior is preview or disabled mode. Live delivery requires
  explicit live mode and an enable flag. Reminders need their own enable flag.
- Do not send development/test messages to requesters. Tests must use mocks or a
  controlled test recipient and temporary databases.

## Data migration and preservation

- The active database contains development-era order data and later application
  edits. It must not be replaced while workbook reconciliation remains pending.
- The latest workbook and raw exports remain private source material. Preserve raw
  files, provenance, recent edits, backups, and reconciliation output.
- The old `orders_data.csv` and normalized July CSV set have different ID
  namespaces. Do not merge them by order ID.
- The pending Excel cleanup keeps Recently Deleted, bad form, and Online Form
  Responses separate for review. `Date Picked Up` is ignored; missing order dates
  may use a valid `Pick up` date, otherwise remain for review.
- Contact email/phone may be blank. A usable recipient name can fill a missing
  contact name. Generic relationship labels such as Son/Daughter are not recipient
  names and stay in source/review context. Missing/ambiguous shops default to B
  only under the reviewed migration rules.
- Inventory cleanup excludes blank tags and clear placeholders
  `TEST`, `TEST2`, `TEST3`, `Need`, `Trailer bike`, and `Xxxx`; other unusual tags
  remain for review. For repeated tags, preserve contributions and source
  provenance while using the earliest row’s bike details under the approved staging
  rule.
- No historical-data cutover, active-database replacement, or duplicate deletion
  is authorized by these notes.

## Operational state and current evidence

- `main` and `origin/main` were aligned at `00c864b` during the 2026-11-23 audit.
- The audit passed **155 Python tests in 7.09 seconds** with email disabled/mocked
  and temporary databases. Node was unavailable in that audit shell, so the
  repository’s Node order-action test was not rerun.
- The audit did not open the active database, `.env`, workbooks, or email previews.
  It is not evidence that a live environment is configured or ready.
- The app’s direct entry point is a Flask debug server. Production serving,
  scheduler ownership, access roles, secret enforcement, deployment, backup/restore
  practice, and final data cutover remain owner decisions.

## Documentation and work boundaries

- Treat [README.md](README.md) as the onboarding/usage guide and the `design/`
  documents as implementation, operations, and audit references.
- Treat [design/architecture.md](design/architecture.md) and
  [design/operations.md](design/operations.md) as proposed operating guidance;
  they do not approve a production deployment by themselves.
- Use [design/database.md](design/database.md) for schema details and guarded
  maintenance procedures. Workshop setup uses a backed-up CLI process; it does not
  import staged spreadsheets.
- Avoid using historical Git handoff claims, old preview paths, or old test totals
  as current facts. The current source audit is
  [design/technical-audit.md](design/technical-audit.md).
