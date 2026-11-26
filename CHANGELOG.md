# CHANGELOG.md — PIF Portal

This file records significant changes in reverse-chronological order. Each entry identifies what changed, the evidence basis, and whether a decision or approval is required.

Format: `## [date] — brief description`

---

## [2026-11-26] — Aligned Order Explorer, New Order, Reporting, Request Links, and Login to unified template (TASK-808)

**Type:** UI consistency
**Git state at time of entry:** local `main`
**Author:** Development agent (Antigravity) / Approved by Project Owner

### Summary

- Applied the `page_header()` macro from [templates/_ui.html](templates/_ui.html) across [templates/add.html](templates/add.html) (preserving `requester_mode` without staff links), [templates/dashboard.html](templates/dashboard.html), and [templates/request_links.html](templates/request_links.html).
- Aligned [templates/login.html](templates/login.html) to `.marker-panel` and `.chalk-header` without inline card styles.
- Verified all `163` Python tests pass.

---

## [2026-11-26] — Unified page shell, CSS design tokens, and shared header primitive (TASK-807)

**Type:** UI architecture / Design system
**Git state at time of entry:** local `main`
**Author:** Development agent (Antigravity) / Approved by Project Owner

### Summary

- Consolidated all inline `<style>` blocks from [templates/base.html](templates/base.html), [templates/index.html](templates/index.html), and [templates/explorer.html](templates/explorer.html) into [static/css/whiteboard.css](static/css/whiteboard.css) under `:root` design tokens (`--portal-font: 'Patrick Hand', cursive`, Order Desk surface/ink/border palette).
- Added [templates/_ui.html](templates/_ui.html) with the reusable `page_header()` macro (left-aligned title, optional subtitle, right-aligned action button) and standardized `.portal-page-header`, `.chalk-header`, `.page-heading`, `.marker-panel`, `#orderTabs`, and DataTables styles.
- Adopted `page_header()` in [templates/index.html](templates/index.html) and [templates/explorer.html](templates/explorer.html).
- Verified 0 inline `<style>` blocks remain in `templates/` and all `163` Python tests pass.

---

## [2026-11-25] — Added UI overhaul and unified template tasks (TASK-807–TASK-810)

**Type:** Planning / UI consistency
**Git state at time of entry:** local `main`
**Author:** Development agent (Antigravity) / Approved by Project Owner

### Summary

Added `TASK-807` through `TASK-810` in [TASKS.md](TASKS.md) to establish a unified template system and consistent visual hierarchy across all staff and public volunteer pages.

---

## [2026-11-25] — Deferred TASK-605 until after TASK-603 historical order cutover

**Type:** Governance / Scheduling
**Git state at time of entry:** local `main`
**Author:** Development agent (Antigravity) / Approved by Project Owner

### Summary

- Marked **TASK-605** (progressive FK constraints on `orders` and `login_logs`) as `⏸` Deferred until after `TASK-603` (historical order cutover/reconciliation), matching `TASK-204`.

---

## [2026-11-25] — Startup schema-version readiness check (TASK-604)

**Type:** Reliability / Operations (`PART-006`)
**Git state at time of entry:** local `main`
**Author:** Development agent (Antigravity) / Approved by Project Owner

### Summary

- Added `verify_schema_ready(db_path)` in [migrations.py](migrations.py) and `check_startup_readiness()` in [app.py](app.py) (`if __name__ == '__main__'`).
- Fails fast with a clear operator message (including the exact `scripts/migrate_db.py --apply` command) if the database file is missing or behind `EXPECTED_SCHEMA_VERSION` (`3`).
- Added unit tests in [tests/test_migrations.py](tests/test_migrations.py); all `163` Python tests pass in `8.804 s`, and `data/processed/pif.db` passes readiness check at version `3`.

---

## [2026-11-25] — Versioned schema migration framework & removal of request-time DDL (TASK-601)

**Type:** Architecture / Schema lifecycle (`DEBT-006`)
**Git state at time of entry:** local `main`
**Author:** Development agent (Antigravity) / Approved by Project Owner

### Summary

1. **Versioned Migration Framework ([migrations.py](migrations.py), [scripts/migrate_db.py](scripts/migrate_db.py)):**
   - Introduced `schema_migrations` tracking table and ordered, idempotent migrations (`v1: core_intake_and_pickup_tables`, `v2: workshop_and_audit_tables`, `v3: numeric_bike_tag_constraints`) with WAL-safe backups and `PRAGMA foreign_key_check` / `PRAGMA integrity_check` verification.
2. **Removed Request-Time DDL:**
   - Removed `ensure_schema()` from [app.py](app.py), [requester_links.py](requester_links.py), and [order_intake.py](order_intake.py).
   - Removed `ensure_pickup_schema()` from [pickup_policy.py](pickup_policy.py).
   - Updated [tests/test_order_workflow.py](tests/test_order_workflow.py) (`create_legacy_database`) to apply `target_version=1` via `apply_migrations()`.
3. **Rehearsal, Active DB Application & Verification:**
   - Added 2 migration framework tests in [tests/test_migrations.py](tests/test_migrations.py); all `162` Python tests pass in `8.920 s`.
   - Rehearsed on a temp copy and applied `scripts/migrate_db.py --apply` to `data/processed/pif.db` (schema version `3`, `0` FK errors, `integrity_check = ok`).

---

## [2026-11-25] — Read-only active database schema and FK inspection (TASK-602)

**Type:** Audit / Documentation
**Git state at time of entry:** local `main`
**Author:** Development agent (Antigravity)

### Summary

Performed a read-only inspection (`?mode=ro`) of `data/processed/pif.db` against [design/database.md](design/database.md):
- **Integrity & Foreign Keys:** `PRAGMA integrity_check = ok`, `0` declared FK violations, and `0` orphaned `orders` references (`contact_id`, `recipient_id`, `shop_name`, `pedal_partner_id`) across 5,712 rows.
- **Schema Drift Noted:**
  - `admin_changes`, `workshop_submissions`, `order_pickup_tracking`, and `pickup_reminder_delivery` are not yet present in `pif.db`.
  - Legacy/staging tables (`bikes`, `bikes_test`, `orders_50`, `orders_old`, `orders_test`) exist in `pif.db`.
  - `orders` lacks declared `REFERENCES` constraints (unblocking **TASK-605**), and `users.username` has legacy `VARHAR(5)` without a `UNIQUE` constraint.
- Marked **TASK-602** ✅ Complete and unblocked **TASK-605** in [TASKS.md](TASKS.md).

---

## [2026-11-25] — Self-hosted all frontend vendor assets and fonts (TASK-106)

**Type:** Availability / Security / Dependency pinning
**Git state at time of entry:** local `main`
**Author:** Development agent (Antigravity) / Approved by Project Owner

### Summary

- Downloaded and self-hosted pinned vendor bundles under `static/vendor/`:
  - Bootstrap `5.3.0` (`bootstrap.min.css`, `bootstrap.bundle.min.js`)
  - jQuery `3.7.1` (`jquery-3.7.1.min.js`)
  - DataTables `1.13.6` (`dataTables.bootstrap5.min.css`, `jquery.dataTables.min.js`, `dataTables.bootstrap5.min.js`)
  - Chart.js `4.4.7` (`chart.umd.min.js`)
  - Patrick Hand font (`patrick-hand.css`, `patrick-hand-latin.woff2`, `patrick-hand-latin-ext.woff2`)
- Updated [templates/base.html](templates/base.html), [templates/explorer.html](templates/explorer.html), and [templates/dashboard.html](templates/dashboard.html) to serve all assets from `/static/vendor/` with zero external CDN requests.
- Verified all `160` Python tests pass.

---

## [2026-11-25] — Unified bike_tag to numeric INTEGER across inventory and orders, and recorded DEC-008/DEC-014 (TASK-401)

**Type:** Schema & validation alignment / Governance
**Git state at time of entry:** local `main`
**Author:** Development agent (Antigravity) / Approved by Project Owner

### Summary

1. **Reusable Numeric `bike_tag` Migration (`TASK-401`)**:
   - Created [scripts/migrate_bike_tag_numeric.py](scripts/migrate_bike_tag_numeric.py) (`--dry-run` / `--apply`, WAL-safe backup into `backups/`).
   - Rehearsed on a temporary copy and applied to `data/processed/pif.db` (backup: `backups/pif-before-bike-tag-numeric-20261125T072700Z.db`):
     - Corrected 4 legacy non-numeric inventory tags (`61`02` → `6102`, `596ffy` → `5966`, `2781Sch` → `2781`, `L3060` → `3060`).
     - Deleted test placeholder `Xxxx` (`inventory_id=1713`) and its contribution row.
     - Converted 2 zero-value `orders.bike_tag` rows (`325`, `326`) to `NULL`.
     - Rebuilt `bike_inventory` and `orders` with `bike_tag INTEGER` and positive-integer `CHECK` constraints (`14,994` inventory bikes, `0` FK errors, `integrity_check = ok`).
2. **Application & Validation Alignment**:
   - Enforced numeric-only positive integer `bike_tag` validation in [admin_tools.py](admin_tools.py), [workshop.py](workshop.py), [volunteer_entry.py](volunteer_entry.py), [templates/inventory_form.html](templates/inventory_form.html), and [templates/volunteer_finished_bike.html](templates/volunteer_finished_bike.html).
   - Updated unit tests in [tests/test_workshop.py](tests/test_workshop.py), [tests/test_volunteer_entry.py](tests/test_volunteer_entry.py), and [tests/test_admin_tools.py](tests/test_admin_tools.py); all `160` tests pass in `8.378 s`.
3. **Owner Decisions Recorded**:
   - **`DEC-014` / `Q-020`:** Self-host vendor assets (`TASK-106` unblocked).
   - **`DEC-008` / `Q-009`:** Follow best-practice versioned schema maintenance and startup readiness check (`TASK-601`, `TASK-602`, `TASK-604` unblocked).

---

## [2026-11-25] — Resolved CON-008 / DEC-006: numeric-only bike tags across inventory and orders (TASK-004, TASK-401)

**Type:** Governance / Product contract decision
**Git state at time of entry:** local `main`
**Author:** Development agent (Antigravity) / Approved by Project Owner

### Summary

- Recorded owner decision for `DEC-006` / `Q-006` / `CON-008`: Bike Tag is **numeric-only** across both `bike_inventory.bike_tag` and `orders.bike_tag`, and both tables must share the same numeric data type so refurbished bikes can be referenced by tag at order pickup.
- Marked **TASK-004** (`CON-001`–`CON-008`) ✅ Complete in [TASKS.md](TASKS.md).
- Promoted tag-type & validation unification from deferred `TASK-D05` to **TASK-401** (Ready 🟡: audit existing `bike_inventory` tags first, then align schema & validation with rehearsal and backup).

---

## [2026-11-25] — Synchronized owner decisions and resolved documentation conflicts (TASK-003, TASK-004)

**Type:** Governance / Documentation synchronization
**Git state at time of entry:** local `main`
**Author:** Development agent (Antigravity) / Approved by Project Owner

### Summary

Updated [design/SPECIFICATION.md](design/SPECIFICATION.md), [design/TRACEABILITY_MATRIX.md](design/TRACEABILITY_MATRIX.md), [TASKS.md](TASKS.md), and [CURRENT_STATUS.md](CURRENT_STATUS.md) to reflect owner confirmations:
1. **`DEC-010` / `Q-015` (Resolved):** Confirmed age range 1–80 and phone normalization (plain 10-digit string stored in `contacts.contact_phone_number` by `order_intake.py`, formatted `(123) 456-7890` for web display only by `utils.format_phone()`).
2. **`DEC-011` / `Q-016` (Resolved):** Confirmed 7-day Public and 28-day Pedal Partner pickup windows. Marked **TASK-003** complete.
3. **`CON-001`–`CON-007` (Resolved):** Confirmed New Order under `Orders` menu (`Q-017`), 2-column desktop/tablet layout (`Q-018`), organic test-count growth (`160 tests`), SMTP setup/testing, feature-driven schema evolution (`TASK-602` gate before deployment), and no-grouping independent order cards (`TASK-806`).
4. **`CON-008` (In Progress — TASK-004):** Remains open for owner review regarding tag format alignment between `bike_inventory` (text) and `orders.bike_tag` (numeric `REAL`).

---

## [2026-11-25] — Login CSRF, rate limiting, POST logout, and repo hygiene closure (TASK-202, TASK-803, TASK-804)

**Type:** Security hardening / Repo hygiene
**Git state at time of entry:** local `main`
**Author:** Development agent (Antigravity) / Approved by Project Owner

### Summary

1. **Login CSRF & Rate Limiting (`TASK-202`, `DEBT-004`)**:
   - Added CSRF token validation to `POST /login` in [app.py](app.py) and [templates/login.html](templates/login.html) using `order_intake.form_token` / `check_token`.
   - Added thread-safe sliding-window `LoginRateLimiter` in [utils.py](utils.py) (5 failed attempts per 300 s per client IP, returning HTTP `429` when exceeded and resetting on successful login).
2. **POST-Only CSRF Logout (`TASK-202`, `DEBT-005`)**:
   - Restricted `/logout` in [app.py](app.py) to `methods=['POST']` with `check_token(..., 'logout')` validation.
   - Updated the navbar Logout link in [templates/base.html](templates/base.html) to a `POST` form with a hidden `csrf_token`.
3. **Repo Hygiene Closure (`TASK-803`, `TASK-804`)**:
   - Verified `definitions/` and `.vscode/extensions.json` are already committed and tracked on `main` (`029a613`) with a clean working tree; marked `TASK-803` and `TASK-804` complete in [TASKS.md](TASKS.md).
4. **Verification**:
   - Added 4 regression tests in [tests/test_auth_security.py](tests/test_auth_security.py); full Python suite passes (`160 tests` in `8.051 s`).

---

## [2026-11-25] — Compact expanded Order Desk card layout and 2x2 Bike Requirements grid (TASK-806)

**Type:** UI refinement / Space efficiency / Visual hierarchy
**Git state at time of entry:** local `main`
**Author:** Development agent (Antigravity) / Approved by Project Owner

### Summary

Refined the expanded Order Desk card in [templates/_order_cards.html](templates/_order_cards.html) and [static/css/whiteboard.css](static/css/whiteboard.css) to reduce excessive vertical height while keeping key bike criteria scannable:
1. **Side-by-Side Contact & Recipient Information (`col-12 col-md-6`)**:
   - Separated **Contact Information** (Contact person, Phone, Email, Pedal Partner when present) and **Recipient Information** (Recipient name, Age when available) into compact, equal-height (`h-100`) side-by-side sections on tablet/desktop (`>= 768px`), stacking cleanly on mobile (`< 768px`).
   - Reduced section padding, heading margins, and key-value spacing to eliminate oversized panel treatment.
2. **Dedicated Bike Requirements 2 × 2 Grid**:
   - Moved **Bike Requirements** into a full-width (`col-12`) section beneath Contact and Recipient with a consistent 2 × 2 grid (`.req-field-grid`) for **Height**, **Bike style**, **First choice**, and **Second choice** (rendering `—` when missing so alignment never breaks).
   - Preserved existing color distinctions, prominent values, and readable labels with compact tile padding.
   - Moved **Bike tag** and **Picked up** date (when present) into a compact metadata footer (`.req-meta-footer`) inside Bike Requirements.
3. **Compact Full-Width Notes**:
   - Placed **Notes** below Bike Requirements (`col-12`) with reduced padding while preserving complete note text and line breaks (`white-space: pre-wrap`).
4. **Verification**:
   - All 156 Python tests pass in 8.905 s.
   - Verified rendered HTML structure for both complete and incomplete order records.

---

## [2026-11-24] — Hardened Order Desk responsive layouts and CSS cache prevention (TASK-806)

**Type:** Bug fix / Layout resilience / Cache prevention
**Git state at time of entry:** local `main`
**Author:** Development agent (Antigravity) / Approved by Project Owner

### Summary

Resolved the issue where the Order Desk appeared locked into a single-column layout on laptop screens:
1. **Root Cause Analysis**:
   - Two factors contributed:
     - First, `.desk-order-list` had previously been set to a single column `grid-template-columns: minmax(0, 1fr)` at all screen widths. The baseline behavior (`@media (min-width: 768px) { .desk-order-list { grid-template-columns: repeat(2, minmax(0, 1fr)); } }`), which placed order cards side-by-side in 2 columns on desktop/tablet, was restored.
     - Second, inside each expanded order card, relying purely on custom CSS Grid declarations without standard Bootstrap utility classes was susceptible to local browser stylesheet caching (`whiteboard.css` had no cache-busting query parameter).
2. **Underlying Fix**:
   - Restored `.desk-order-list` 2-column card grid for tablet and desktop (`@media (min-width: 768px) { grid-template-columns: repeat(2, minmax(0, 1fr)); }`) in both `whiteboard.css` and `index.html`.
   - Structured `.desk-order-body` with native Bootstrap 5 responsive grid classes:
     - Container: `<div class="row g-3 desk-order-body">`
     - Contact Information (left column): `<div class="col-12 col-md-6 desk-section desk-contact-info">`
     - Recipient & Bike Requirements (right column): `<div class="col-12 col-md-6 desk-section desk-bike-requirements">`
     - Notes (full-width beneath both): `<div class="col-12 desk-section desk-order-notes">`
   - Added CSS cache-buster `?v={{ app_version }}` to `<link rel="stylesheet" href="{{ url_for('static', filename='css/whiteboard.css') }}?v={{ app_version }}">` in `base.html` so client browsers automatically refresh the stylesheet.
   - Retained pure CSS grid fallback in `whiteboard.css`.
3. **Verification**:
   - All 156 Python tests pass in 6.99 s.
   - Verified Bootstrap `col-12 col-md-6` layout behavior on mobile (<768px, 100% stacked) and desktop/tablet (>=768px, 50% side-by-side with full-width notes).

---

## [2026-11-24] — Fixed expanded order card responsive grid structure (TASK-806)

**Type:** Bug fix / Layout refinement / Responsive design
**Git state at time of entry:** local `main`
**Author:** Development agent (Antigravity) / Approved by Project Owner

### Summary

Resolved the issue where expanded order cards displayed Contact Information and Recipient & Bike Requirements in a single column on tablet and desktop:
1. **Root Cause Identified**:
   - The earlier implementation wrapped Contact Information and Recipient & Bike Requirements in an unnecessary `.desk-sections-row` container inside `.desk-order-body`, while Notes was rendered outside it.
   - `.desk-order-body` was configured as `display: flex; flex-direction: column;`, decoupling Notes from the grid columns and making the internal grid susceptible to content-size blowout.
2. **Underlying Fix**:
   - Flattened the child section structure of `.desk-order-body`: Contact Information, Recipient & Bike Requirements, and Notes are now direct children of the expanded card grid container.
   - Defined explicit CSS grid tracks on `.desk-order-body`:
     - **Desktop & Tablet (`min-width: 768px`)**: `grid-template-columns: minmax(0, 1fr) minmax(0, 1fr)` with `align-items: start`. `.desk-contact-info` explicitly assigned to `grid-column: 1; grid-row: 1;`; `.desk-bike-requirements` explicitly assigned to `grid-column: 2; grid-row: 1;`; `.desk-order-notes` explicitly assigned to `grid-column: 1 / -1; grid-row: 2;` (spanning the full width beneath both columns).
     - **Mobile (`max-width: 767.98px`)**: `grid-template-columns: 1fr` with Contact Information on row 1, Recipient & Bike Requirements on row 2, and Notes on row 3.
   - Added `.desk-sections-row { display: contents; }` fallback.
   - Injected layout rules into `index.html`'s in-page style block to prevent browser cache from serving stale stylesheets.
3. **Verification**:
   - Layout verified across mobile (375px), tablet (768px, 820px), and desktop (1024px, 1200px, 1440px) viewports.
   - All 156 Python unit and integration tests pass cleanly (6.898 s).

---

## [2026-11-24] — Enhanced Order Desk visual hierarchy, responsive layout, field separation, and top-level actions (TASK-806)

**Type:** Bug fix / UI Enhancement / Field separation / Accessibility
**Git state at time of entry:** local `main`
**Author:** Development agent (Antigravity) / Approved by Project Owner

### Summary

Refined and completed the Order Desk implementation per owner review:
1. **Responsive Two-Column Layout**:
   - Re-established strict two-column layout on tablet and desktop screens (`min-width: 768px`) with `grid-template-columns: minmax(0, 1fr) minmax(0, 1fr)`.
   - Contact Information strictly occupies the left column; Recipient & Bike Requirements strictly occupies the right column.
   - Notes section spans the full width of the card beneath both columns.
   - Cleanly stacks into a single column on mobile screens (<768px).
2. **Correct Recipient / Contact Field Separation**:
   - Fixed field leakage: Recipient name is exclusively rendered in Recipient & Bike Requirements, never in Contact Information.
   - Contact Information contains only Contact person, Phone, and Email (plus Pedal Partner if present).
   - Recipient & Bike Requirements contains Recipient name, Age (when available), Height, Bike style, First choice, Second choice, and Bike tag.
   - Missing contact or recipient names render explicit fallback labels (`Unnamed contact`, `Unnamed recipient`) without shifting columns.
3. **Top-Level Actions Dropdown**:
   - Replaced bottom-of-card action area with a compact, clearly identifiable `Actions` dropdown button at the top header of each card.
   - Accessible in both collapsed and expanded card states without scrolling through card details.
   - Status-appropriate actions: Open (`Contact`, `Cancel order`, `Open in Explorer`), Contacted (`Save pickup` form with date and tag, `Cancel order`, `Open in Explorer`), Cancelled (`Restore to Open`, `Open in Explorer`), Completed/All (`Open in Explorer`).
   - Click propagation stopped to prevent toggling the card when interacting with the menu or forms.
   - Stacking context managed via `z-index` and Bootstrap events so open dropdown menus are never clipped or hidden behind neighboring cards.
4. **Strong Visual Prominence for Key Bike Details**:
   - Height, First bike choice, Second bike choice, Bike style, and Bike tag given high-contrast badge treatment in collapsed summary.
   - Expanded card features prominent highlight cards with semantic color themes, bold typography, and clear scannable labels.
5. **Verification**:
   - All 156 unit and integration tests pass cleanly in 7.245 s.
   - DOM and field separation verified across Open, Contacted, Cancelled, Completed, and All tabs.

---

## [2026-11-24] — Implemented owner-approved Order Desk redesign (TASK-806)

**Type:** Feature / Presentation layer redesign / Technical debt resolution
**Git state at time of entry:** local `main`
**Author:** Development agent (Antigravity) / Approved by Project Owner

### Summary

Implemented the owner-approved Order Desk presentation redesign across all tabs (Open, Contacted, Cancelled, Completed, All):
1. **Structure & Grouping Removal**:
   - Removed contact-person / bulk-order grouping (`group_data()`) from `app.py` index route.
   - Displayed every recipient/bike request as an independent, self-contained order card.
   - Preserved individual order lifecycle without adding any order-header database table or bulk lifecycle state.
   - Deterministic sorting applied across views: Open and Contacted orders sorted oldest first by `(order_date_iso, order_id)`; Completed orders sorted newest pickup first by `(pickup_date_iso, order_id)`; Cancelled and All orders sorted newest first by `(order_date_iso, order_id)`.
   - Bike-type filtering remains deferred.
2. **Collapsed Card Layout**:
   - Summary displays `Contact person name → Recipient name` (`{{ order.contact_name or 'Unnamed contact' }} → {{ order.recipient_name or 'Unnamed recipient' }}`), handling missing names independently without identity substitution.
   - Summary displays status badge (`Open`, `Contacted`, `Completed`, `Cancelled`), order metadata (`Order #`, date, shop, category, notes indicator, pedal partner), and key requirements pills (`Height`, `1st choice`, `2nd choice`, `Style`, `Tag`, `Picked up`).
   - For Contacted orders, displays pickup deadline window and overdue status if applicable.
   - Clear disclosure toggle: `View details & actions` / `Hide details`.
3. **Expanded Card Layout (4 Sections)**:
   - **Section A (Contact information)**: Contact person, Recipient, Phone, Email, and Pedal Partner.
   - **Section B (Recipient & bike requirements)**: Age, Height, Bike style, First choice, Second choice, Bike tag, Picked up date.
   - Responsive two-column grid (`.desk-sections-row`) displaying Sections A and B side-by-side on desktop (`min-width: 768px`) and stacked on mobile.
   - Removed separate contact details `<details class="desk-contact-details">` disclosure as its information is now incorporated directly.
   - **Section C (Notes)**: Visible notes section rendering `order.notes` with safe HTML escaping.
   - **Section D (Actions)**: Status-appropriate actions.
4. **Action Updates**:
   - Renamed button `Mark contacted` to `Contact`. Retained `Cancel order`, `Restore to Open`, and `Save pickup` form.
   - Maintained all existing email triggers and safeguards (`EMAIL_MODE=disabled`; live email delivery disabled).
   - Preserved Order Explorer direct links (`Open #<id> in Explorer`).
5. **Verification**:
   - All 156 Python unit and integration tests pass cleanly in 7.060 s (`PYTHONDONTWRITEBYTECODE=1 EMAIL_MODE=disabled EMAIL_LIVE_ENABLED=false EMAIL_REMINDERS_ENABLED=false DB_PATH=/tmp/pif-test-$$.db .venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v`).
   - `git diff --check` passes with zero whitespace errors.

---

## [2026-11-24] — Applied bike inventory migration to active database (TASK-616, TASK-617)

**Type:** Data migration / Production execution / Operational milestone
**Git state at time of entry:** local `main` at `2d982f8`
**Author:** Development agent (Antigravity) / Approved by Project Owner

### Summary

With explicit owner approval, successfully executed the historical bike inventory and contributions migration against the active production database `data/processed/pif.db` using `scripts/migrate_bike_inventory.py --apply`.
- **Pre-execution Backup**: Created `data/processed/backups/pif-before-bike-inventory-20261124T195158Z.db` (5.8 MB).
- **Bike Inventory**: Loaded 14,995 globally unique canonical bikes into `bike_inventory` spanning August 2021 through October 2026, with normalized wheel sizes and bike types.
- **Bike Contributions**: Loaded 15,461 contribution rows into `bike_contributions` linked to `bike_inventory(inventory_id)`, accommodating 466 multi-contributions/reused tags with variation details recorded in `notes`.
- **Volunteer Roster Provisioning**: Provisioned 167 new volunteer profiles active in the 2025–2026 moving window (including top builder `Joe Maneiro` with 418 lifetime bikes), bringing the total registered volunteer roster in `volunteers` to 660 profiles.
- **Attribution & Moving Window**: 12,461 contributions (80.6%) linked to registered volunteer profiles (via direct matches, automated aliases, and newly provisioned 2025–2026 volunteers). 2,710 pre-2025 entries and 290 2025+ single/org entries remain unlinked with original text preserved in `recorded_name`.
- **Integrity Verification**: `PRAGMA foreign_key_check` returned zero errors; `PRAGMA integrity_check` returned `ok`. All 156 Python tests pass cleanly (7.90 s).

---

## [2026-11-24] — Adopted moving 2-year window policy (2025–2026) for volunteer migration and created review register

**Type:** Data migration policy / Tool enhancement / Staff documentation
**Git state at time of entry:** local `main` at `32491d0`
**Author:** Development agent (Antigravity) / Approved by Project Owner

### Summary

1. **Owner Policy Baseline (Moving 2-Year Window)**:
   - Owner decided that staff focus and volunteer profile management shall prioritize the moving 2-year window (**2025 through 2026**).
   - Historical records prior to 2025 that do not match existing profiles are kept unlinked (`volunteer_id = NULL`), preserving the original name string in `recorded_name`.
   - Obvious name abbreviations (e.g. `David Tovey` $\rightarrow$ `David T`, `Donn Schmidt` $\rightarrow$ `Donn S`, `Ann Neumann` $\rightarrow$ `Ann N`, `Charlie Miller` $\rightarrow$ `Charles Miller`, `Marty H` $\rightarrow$ `Marty Heyne`) are mapped automatically across all years.
   - Clean, full person names active in 2025–2026 are auto-provisioned into `volunteers` (167 profiles provisioned; `is_active` set based on 180-day cutoff).
2. **Staff Review Document Created**:
   - Created `design/volunteer-reconciliation-2025-2026.md` detailing automated alias mappings, provisioned 2025–2026 profiles (including top builder `Joe Maneiro` with 418 lifetime bikes), and a checklist of ambiguous single names (e.g. `Kenny`, `Justin`, `Cory`, `John`) and corporate groups (`Walmart`, `Staff`) for staff review.
3. **Rehearsal & Quality Verification**:
   - Rehearsed updated `scripts/migrate_bike_inventory.py --apply` on `/tmp/pif-bike-rehearsal.db`: 14,995 bikes, 15,461 contributions (12,461 linked, 80.6% attribution rate; 2,710 pre-2025 kept null; 290 2025+ single/org kept null).
   - Zero foreign key errors (`PRAGMA foreign_key_check` clean); integrity `ok`; all 156 unit and integration tests passing (6.61 s).

---

## [2026-11-24] — Implemented bike inventory migration tool and completed rehearsal (TASK-616, TASK-617)

**Type:** Data migration tool / Rehearsal / Verification
**Git state at time of entry:** local `main` at `ab6538c`
**Author:** Development agent (Antigravity) / Approved by Project Owner

### Summary

1. **Migration Tool (`scripts/migrate_bike_inventory.py` — TASK-616)**:
   - Built reusable CLI script with `--dry-run` and `--apply` options.
   - Filters out 9 placeholder/test/null tags (`TEST`, `TEST2`, `TEST3`, `Need`, `Trailer bike`, missing tags).
   - Inserts 14,995 globally canonical unique bike tags into `bike_inventory` with normalized wheel sizes and bike types.
   - Inserts 15,461 contribution rows into `bike_contributions` linked to `bike_inventory(inventory_id)`.
   - Accommodates 466 multi-contributions and reused tags by linking to the existing bike ID with historical variations captured in `notes`.
   - Automatically links 11,249 contributions (72.7%) to active `volunteers(volunteer_id)` via direct and unambiguous first-name/last-initial matching, while retaining full original entered string in `recorded_name`.
2. **Rehearsal & Quality Verification (TASK-617)**:
   - Executed full rehearsal on isolated copy at `/tmp/pif-bike-rehearsal.db`.
   - Verified `PRAGMA foreign_key_check`: clean (0 errors) and `PRAGMA integrity_check`: `ok`.
   - Verified application domain functions: `admin_tools.lookup_bike` retrieves bikes with contributors and variation notes; `volunteer_impact.yearly_impact` correctly aggregates historical bike contributions (e.g. Tom Woodcock: 40 in 2021, 56 in 2022, 65 in 2023, 55 in 2024, 47 in 2025).
   - Verified test suite: all 156 unit and integration tests pass cleanly (6.97 s) against the populated rehearsal database.
   - Awaiting explicit project owner approval before applying migration to active database (`data/processed/pif.db`).

---

## [2026-11-24] — Planned historical bike inventory migration (TASK-616, TASK-617) and completed raw data audit

**Type:** Data migration planning / Codebase audit
**Git state at time of entry:** local `main` at `1694517`
**Author:** Development agent (Antigravity) / Approved by Project Owner

### Summary

1. **Backlog Planning (TASK-616, TASK-617)**:
   - Added `TASK-616` to develop reusable migration logic for the `Finished Bike Inventory` sheet in `data/raw/PIF 2025 .xlsx`.
   - Added `TASK-617` to rehearse on a database copy, verify foreign keys/integrity, and execute one-time migration against `data/processed/pif.db` with backup.
2. **Raw Dataset Audit (15,470 records, 2021-08-17 to 2026-10-03)**:
   - **Shops**: 8,197 Bentonville (`BV Shop`), 5,677 Rogers (`RAC Shop`), 1,581 Springdale (`Sdale Shop`), 15 composite entries (`RAC Shop, BV Shop`).
   - **Bike Tags**: 15,016 unique canonical tags; 445 repeated tags (accounting for 898 rows); 1 missing tag; 8 placeholder/test tags (`TEST`, `TEST2`, `TEST3`, `Need`, `Trailer bike`) matching exclusions documented in `design/database.md`.
   - **Multi-Contribution Mechanics**: 73 repeated tags represent the same bike (multiple shifts/contributors); 372 represent reused physical tags over different years/shops, to be preserved via `bike_contributions` notes while maintaining `bike_inventory.bike_tag` uniqueness.
   - **Volunteer Name Matching**: 9,835 rows match active volunteer profiles directly; first-name + last-initial heuristic matches an additional 1,418 rows (72.7% total auto-match). Unmatched names retain full original string in `bike_contributions.recorded_name` with nullable `volunteer_id`.

---

## [2026-11-24] — Added GitHub Actions CI workflow (TASK-105) and archived legacy git handoff (TASK-805)

**Type:** DevOps / Documentation / Maintenance
**Git state at time of entry:** local `main` at `488dafb`
**Author:** Development agent (Antigravity) / Approved by Project Owner

### Summary

1. **GitHub Actions CI Workflow (TASK-105)**:
   - Created `.github/workflows/ci.yml` with automated testing on `push` and `pull_request` to `main`.
   - `python-tests` job: sets up Python 3.12, installs dependencies from `requirements.txt` and `openpyxl`, runs recursive syntax compilation (`python -m compileall -q .`), and executes the complete 156-test Python test suite under non-negotiable safe email overrides (`EMAIL_MODE=disabled`, `EMAIL_LIVE_ENABLED=false`, `EMAIL_REMINDERS_ENABLED=false`) with isolated runner temp database.
   - `node-tests` job: sets up Node.js 20.x and executes the built-in Node test runner for `tests/test_order_actions.cjs`.
   - `whitespace-check` job: validates git diff for trailing whitespace and formatting errors.
2. **Archived Legacy Git Handoff (TASK-805)**:
   - Added an explicit warning notice and archival banner to `design/git-handoff.md` indicating it describes superseded branch states (`2fd083b` and `00c864b`).
   - Directed developers to authoritative living documents: `AGENTS.md`, `design/SPECIFICATION.md`, and `design/ARCHITECTURE.md`.
   - Resolved contradiction `CON-004` and proposed requirement `NFR-011` in `design/TRACEABILITY_MATRIX.md`.
3. **Cleaned Reference Scripts**:
   - Removed temporary reference directory `scripts/for_reference/` per owner confirmation.

---

## [2026-11-24] — Applied volunteer time clock migration and shop upgrade to active database (TASK-611 to TASK-615)

**Type:** Data migration / Schema upgrade / Operational execution
**Git state at time of entry:** local `main` at `1ad9a48`
**Author:** Development agent (Antigravity) / Approved by Project Owner

### Summary

Successfully executed the one-time migration against the active database `data/processed/pif.db` using `scripts/migrate_volunteer_clock.py --apply`.
- **Pre-execution Backup**: Created `/Users/abhishekjohnmasih/Documents/01_John/02_Activities/01_Code/04_PythonVenv/pif/data/processed/backups/pif-before-volunteer-clock-20261124T073832Z.db`.
- **Shops Upgrade (TASK-615)**: Added `shop_id` (1, 2, 3), `address`, `landmark`, and `store_hours` for Bentonville, Rogers, and Springdale. Cleaned rogue NULL shop row.
- **Volunteers Directory (TASK-611, TASK-612)**: Standardized and inserted 493 unique volunteer profiles with `joined_on` date and 180-day `is_active` flag (192 active, 301 inactive).
- **Volunteer Hours (TASK-613, TASK-614)**: Inserted 5,466 shift logs (1,025,948 minutes = 17,099.13 hours) across Bentonville (2,284 raw), Rogers (1,347 raw), and Springdale (1,077 raw). Applied Option B catch-up backfill on open shop days for 25 entries > 24 hours (generating 783 3-hour shifts tagged 'Catchup hours').
- **Integrity Verification**: `PRAGMA foreign_key_check` returned zero errors; `PRAGMA integrity_check` returned `ok`. All 156 Python tests pass cleanly (7.10 s).

---

## [2026-11-24] — Planned Option B catch-up shift backfill and shops table upgrade (TASK-611 to TASK-615)

**Type:** Architecture refinement / Planning
**Git state at time of entry:** local `main` at `9eab145`
**Author:** Development agent (Antigravity) / Project owner instruction

### Summary

Owner confirmed the resolution of the >24-hour time clock entries (**Option B**): break catch-up entries into standard 3-hour shifts on prior days the shop was open, tagged with note `'Catchup hours'`.
Additionally, planned **TASK-615** to upgrade the `shops` table with physical addresses, landmarks, and store operating hours for Bentonville, Rogers, and Springdale.

---

## [2026-11-24] — Planned volunteer directory and time clock historical migration (TASK-611 to TASK-614)

**Type:** Planning / Data migration roadmap
**Git state at time of entry:** local `main` at `9eab145`
**Author:** Development agent (Antigravity) / Project owner request

### Summary

Added tasks TASK-611 through TASK-614 to `TASKS.md` for migrating volunteer profiles and historical hours from `data/raw/PIF Volunteer Reporting time clock.xlsx`. Conducted technical verification against active application codebase (`workshop.py`, `volunteer_entry.py`, `volunteer_impact.py`, `admin_tools.py`) and identified key schema alignment and data quality requirements:
- Column naming alignment: application expects `is_active` (INTEGER 0/1) and `joined_on` (TEXT ISO date).
- Hours storage alignment: application tracks integer `minutes` (e.g. 2.5h = 150m) and shop code `shop_name` ('B'/'R'/'S').
- Raw data audit: 4,708 valid entries, 956 trailing blank rows, 25 entries with >24 hours requiring discussion/reconciliation against single-shift constraints.

---

## [2026-11-23] — TASK-801 applied: Fixed bare except handlers in utils.py and added unit tests

**Type:** Code improvement / Technical debt remediation (DEBT-012)
**Git state at time of entry:** local `main` at `9568412`
**Author:** Development agent (Antigravity)

### Summary

Applied **TASK-801** ([DEBT-012](file:///Users/abhishekjohnmasih/Documents/01_John/02_Activities/01_Code/04_PythonVenv/pif/design/SPECIFICATION.md#L182)). Replaced bare `except:` clauses in [utils.py](file:///Users/abhishekjohnmasih/Documents/01_John/02_Activities/01_Code/04_PythonVenv/pif/utils.py) with explicit, targeted exception tuples:
- `format_date`: changed `except:` to `except (ValueError, TypeError, IndexError):`.
- `clean_int`: changed `except:` to `except (ValueError, TypeError):`.
- Added unit regression test `test_utils_formatting_helpers` in `tests/test_order_cards.py`.
- Full test suite re-verified: **156 tests passing in 10.18 s** (increased from 155).

---

## [2026-11-23] — Owner decisions on host, secret key, staff governance, and task prioritization

**Type:** Owner decisions / Task updates
**Git state at time of entry:** local `main` at `029a613` | `origin/main` at `00c864b`
**Author:** Project owner / Development agent (Antigravity)

### Decisions recorded

- **DEC-001 (Production Host)**: Placed on hold / deferred to deployment planning phase as app is still in development.
- **DEC-003 (`SECRET_KEY` Production Enforcement)**: Placed on hold / deferred to deployment setup.
- **DEC-004 (Staff Account Governance)**: Resolved — owner confirmed no account lifecycle rules are enforced; staff creation/modification is intentionally skipped due to small, persistent staff headcount.
- **TASK-104 (`.env.example`)**: Completed by owner; template created in project root with app and email variables.
- **TASK-204 (Centralize `PRAGMA foreign_keys=ON`)**: Deferred to deployment/migration phase per owner instruction.
- **TASK-801 (Fix bare excepts in utils.py)**: Clarified to owner; ready for review/application.

---

## [2026-11-23] — Milestone: Specification & Architecture Approved by Owner; Codebase Audited; UTM Protocol Established

**Type:** Product milestone / Documentation / Architecture contract
**Git state at time of entry:** local `main` at `029a613` | `origin/main` at `00c864b`
**Author:** Project owner (approval) / Development agent (Antigravity)

### Summary

The project owner formally reviewed and approved `design/SPECIFICATION.md` and `design/ARCHITECTURE.md`. This completes **TASK-001** and **TASK-002** in `TASKS.md`, establishing the authoritative product requirements and architectural target for all subsequent development.

A complete codebase scan was conducted across all directories to catalog ongoing code and ensure no rogue or unmerged work exists. Additionally, the Universal Transferable Memories (UTM) protocol was codified in `AGENTS.md` and applied across all repository artifacts.

### Key Milestones & Findings

1. **Owner Approval of Tier 1 Documents**:
   - `design/SPECIFICATION.md`: Formally approved as the single source of truth for product rules, actor flows, and scope.
   - `design/ARCHITECTURE.md`: Formally approved as the single source of truth for system boundaries, component design, and operational model.
   - Traceability updated in `design/TRACEABILITY_MATRIX.md`.

2. **Complete Codebase Audit**:
   - 12 root Python modules (2,913 LOC total).
   - 5 CLI maintenance utilities in `scripts/`.
   - 13 test suites (155 unit tests passing cleanly in 6.75 s).
   - 23 primary/sub-templates + 5 email templates in `templates/`.
   - 7 JavaScript front-end action scripts in `static/js/` + Sharpie whiteboard CSS.
   - Git branches inspected: all feature branches (`codex/responsive-portal`, `codex/spreadsheet-cleanup`, `codex/database-cleanup`) are 100% merged into `main`. No unmerged branches or WIP code branches exist.
   - Isolated preview runner in `data/previews/` confirmed archived and non-conflicting.

3. **Universal Transferable Memories (UTM) Protocol Established**:
   - Codified in `AGENTS.md` §Universal Transferable Memories (UTM) Protocol.
   - Mandates synchronized persistence of decisions, task status, verification evidence, and operational state across every step so that any future agent or developer has complete, unbroken context.

---

## [2026-11-23] — Baseline establishment task: documents updated and tests re-verified

**Type:** Documentation / verification
**Git state at time of entry:** local `main` at `029a613` | `origin/main` at `00c864b`
**Author:** Development agent (Antigravity)

### Summary

Completed the "Establish Development Baseline" task. No implementation code was changed. All changes are documentation corrections and additions.

### Discrepancies identified and resolved

| Item | Previous state | Corrected state |
|---|---|---|
| AGENTS.md baseline commit reference | `00c864b` | `029a613` (local HEAD), `00c864b` (origin/main) |
| CURRENT_STATUS.md baseline commit reference | `00c864b` (stated "aligned with origin/main") | Local HEAD is `029a613`; `origin/main` remains `00c864b` |
| CURRENT_STATUS.md test time | `7.17 s` | `6.748 s` (re-verified run) |
| CURRENT_STATUS.md worktree table | Listed files as "New" that are now committed | Replaced with accurate committed/untracked breakdown |
| VERIFICATION.md baseline commit reference | `00c864b` | `029a613` / `00c864b` |

### Discrepancies remaining (not resolved — owner required)

| Item | Description |
|---|---|
| Local `main` ahead of `origin/main` | `029a613` is a local merge commit not yet pushed. Owner decision needed: push or keep local. |
| `design/SPECIFICATION.md` untracked | Reconstructed spec not committed; under owner review. |
| `design/ARCHITECTURE.md` untracked | Proposed architecture not committed; under owner review. |
| `design/TRACEABILITY_MATRIX.md` untracked | Not committed; under owner review. |
| `design/operations.md` untracked | Not committed; under owner review. |
| `design/pif-technical-audit-2026-11-23.md` untracked | Audit evidence not committed. |
| `.gitignore` working-tree modification | Modified in working tree vs HEAD; not staged or committed. |

### Test re-verification

```
155 tests in 6.748 s — PASS
Command: PYTHONDONTWRITEBYTECODE=1 EMAIL_MODE=disabled EMAIL_LIVE_ENABLED=false
         EMAIL_REMINDERS_ENABLED=false DB_PATH=/tmp/pif-baseline-$$-new.db
         .venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```

Consistent with all previous runs. No regression introduced.

### No implementation changes

No application code, schema, database, or private configuration was modified. The active database was not opened. No email was sent.

---

## [2026-11-23] — Development baseline established

**Type:** Documentation / baseline
**Git state at time of entry:** `main` at `00c864b` (aligned with `origin/main`)
**Author:** Development agent (Antigravity)

### Summary

Completed the initial audit and specification reconstruction phase. No implementation code was changed. All files created or updated are documentation only.

### Files created

| File | Purpose |
|---|---|
| `AGENTS.md` | Updated from 3-line stub to full development conventions, safety rules, test command, and documentation authority map |
| `CURRENT_STATUS.md` | Current verified implementation state: test baseline, area-by-area status, open decisions, known defects, worktree state |
| `TASKS.md` | Outstanding work organized by tier with blocking decisions, spec/debt references, and deferred items |
| `VERIFICATION.md` | Evidence register: test runs, code quality checks, feature coverage, explicit unverified items, and gaps |
| `CHANGELOG.md` | This file |
| `design/SPECIFICATION.md` | Reconstructed product specification with owner-confirmed rules (O-001 through O-011) |
| `design/ARCHITECTURE.md` | Proposed architecture (conservative; preserves Flask/SQLite; not yet approved) |
| `design/TRACEABILITY_MATRIX.md` | Requirements-to-implementation traceability matrix |

### Test baseline re-verified

```
155 tests in 7.17 s — PASS
Command: PYTHONDONTWRITEBYTECODE=1 EMAIL_MODE=disabled EMAIL_LIVE_ENABLED=false
         EMAIL_REMINDERS_ENABLED=false DB_PATH=/tmp/pif-baseline-test.db
         .venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```

Consistent with the 2026-11-23 audit result (155 tests in 7.09 s).

### Decisions incorporated (owner-confirmed 2026-11-24)

The following owner decisions are recorded in `design/SPECIFICATION.md` and `design/TRACEABILITY_MATRIX.md`. They do not authorize cutover, deployment, or feature development.

- **O-001:** Bulk submission is an entry convenience; each bike request is processed independently.
- **O-002:** One staff permission tier acceptable for initial release.
- **O-003:** 24/7 Debian server; Tailscale for remote administration; host location conditional on connectivity test.
- **O-004:** Reporting is low priority; count completed bike lines by pickup year/shop; missing shop defaults to Bentonville.
- **O-005:** Developer executes migration; UAT is functional workflow acceptance (not historical-data cleanup); Google Sheets abandoned at portal transition.
- **O-006:** Include all available historical data at current scale.
- **O-007:** UAT scope is functional; historical ambiguity is explicitly deferred.
- **O-008:** Google Sheets to be abandoned at switch-over, not maintained in parallel.
- **O-009:** Shop internet reliability has no standardized threshold; owner will test.
- **O-010:** Owner plans daily offsite backups for application data and code repository.
- **O-011:** Production server/proxy/service choices not yet selected; agent to assist with deployment research.

### Remaining open questions

22 questions remain unresolved (Q-001 through Q-022, excluding Q-007 and Q-014 which are owner-confirmed). See `design/SPECIFICATION.md §9` and `CURRENT_STATUS.md` for the full list.

### No implementation changes

No application code, schema, database, or private configuration was modified. The active database was not opened. No email was sent.

---

## [2026-11-23] — Repository audit performed (read-only)

**Type:** Audit (no changes)
**Git state:** `main` at `00c864b`
**Author:** Development agent (Antigravity), read-only audit run

### Summary

A full read-only audit of the `main` branch was performed. Source code, documentation, test suite, and Git state were reviewed. No files were changed during the audit itself.

### Audit findings summary

- 155 Python tests passed in 7.09 s with temporary databases and disabled/mocked email.
- Python syntax compilation passed.
- `git diff --check` passed (no whitespace errors).
- Node `test_order_actions.cjs` not run (Node unavailable).
- 19 technical debt items identified (DEBT-001 through DEBT-019).
- 9 documented partial implementations (PART-001 through PART-009).
- 10 unimplemented items (TODO-001 through TODO-010).
- 8 documented conflicts between project documents (CON-001 through CON-008).
- 10 owner questions requiring decisions.

Full audit report: [`progress/pif-technical-audit-2026-11-23.md`](progress/pif-technical-audit-2026-11-23.md)

---

## [pre-2026-11-23] — Application development history

The application grew from an order desk (Flask/SQLite) to a staff portal with volunteer/workshop capabilities. The following represents the reconstructed commit history (from `git log`). These are code changes; they predate this CHANGELOG.

| Commit | Description |
|---|---|
| `00c864b` | Merge branch `codex/database-cleanup` |
| `7ffc731` | Add pickup deadlines and unified order desk |
| `8d4e8c5` | Merge workshop and order improvements |
| `3be53af` | Add workshop workflows and refine order intake and reporting |
| `e85d6e5` | Merge workshop and order improvements |
| `dca6fec` | Add workshop workflows and refine order intake and reporting |
| `2fd083b` | Improve responsive layouts, navigation, search and footer |
| `a234915` | Overhaul design and added new features (search bar, etc.) |
| `cae04da` | Added columns to order table |
| `d50b156` | Added columns to order table |
| `1679c4a` | Update LICENSE |
| `443690d` | Added login logs |
| `fba5c08` | Added Explorer Page and resolved data issue |
| `af792d7` | Added Explorer Page and resolved data issue |
| `c00e4d1` | Update requirements for production |
| `f9f0cd9` | Upgraded database and added more functionalities |
| `c65805b` | Added image for PIF logo |
| `9053378` | Code cleanup and added logo |
| `de32ca5` | Added email triggers |
| `e16d84e` | Added email triggers |

Detailed rationale for pre-audit decisions is not fully recoverable from the commit history. See `design/TRACEABILITY_MATRIX.md §5` (Explicitly rejected approaches) for the evidence limitations.
