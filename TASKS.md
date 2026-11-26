# TASKS.md — PIF Portal Outstanding Work

**Updated:** 2026-11-23 (re-verified during baseline establishment task)
**Rules:**
- Do not start a task blocked by an open owner decision (see [CURRENT_STATUS.md](CURRENT_STATUS.md)).
- Do not mark a task complete without verification evidence (test, audit, or owner sign-off).
- Do not perform feature development tasks out of specification order.
- Add newly discovered tasks here before starting them.

Task IDs are stable references. Do not renumber completed tasks.

---

## Status legend

| Symbol | Meaning |
|---|---|
| 🔴 | Blocked — requires owner decision |
| 🟡 | Ready — owner decisions resolved, not yet started |
| 🔵 | In progress |
| ✅ | Complete with evidence |
| ⏸ | Deferred — explicitly deprioritized |

---

## Priority 0 — Owner decisions (not implementation tasks)

These are not code tasks. They block multiple downstream items and require the project owner to respond.

| ID | Decision needed | Blocking tasks |
|---|---|---|
| DEC-001 | Confirm production host: organization site vs. developer home pending connectivity test (⏸ On hold — planned for deployment phase) | TASK-101, TASK-102 |
| DEC-002 | Select WSGI server, reverse proxy, service manager (agent-assisted at deployment time) | TASK-101 |
| DEC-003 | Confirm `SECRET_KEY` mandatory at startup; session rotation/revocation plan (⏸ On hold — planned for deployment phase) | TASK-201 |
| DEC-004 | Staff account provisioning, password reset, disable/revocation procedures | ✅ Resolved: Owner confirms no rules enforced; staff creation/modification lifecycle skipped due to small, persistent headcount |
| DEC-005 | Whether public volunteer attribution without authentication is acceptable for deployment | ✅ Resolved: Owner confirms no-login public volunteer name lookup & self-attribution is approved (`Q-005`) |
| DEC-006 | Tag format for order completion: numeric-only or align with inventory text format | ✅ Resolved: Bike Tag is numeric-only; both `bike_inventory.bike_tag` and `orders.bike_tag` must share the same numeric data type (`TASK-401`) |
| DEC-007 | UAT functional scenarios, acceptance checklist, Google Sheets switch-over date | TASK-501 |
| DEC-008 | Request-time DDL vs. explicit versioned migrations | ✅ Resolved: Follow best-practice versioned schema maintenance & startup readiness check (unblocks `TASK-601`, `TASK-602`, `TASK-604`, `TASK-605`) |
| DEC-009 | SMTP sender, test-recipient policy, preview retention, approval gate | ✅ Resolved: Triggers confirmed (create, Contacted, 1-day-before reminder, optional completion); move to live after app testing & staging `EMAIL_MODE=test` verification (`TASK-701`) |
| DEC-010 | Confirm age 1–80 and phone normalization as approved intake requirements | ✅ Resolved: Age 1–80 and phone normalization approved (plain 10-digit DB storage, `(123) 456-7890` web display) |
| DEC-011 | Confirm 7-day / 28-day pickup windows still correct | ✅ Resolved: 7-day Public / 28-day Pedal Partner confirmed active |
| DEC-012 | Confirm approved layout: "Desktop unchanged" or unified two-column from 768px | ✅ Resolved: Owner approved Order Desk redesign displaying independent order cards with responsive two-column recipient layout stacking on mobile |
| DEC-013 | Confirm volunteer impact aggregate visibility rules | ✅ Resolved: Owner confirms displaying volunteer YTD hours/impact summary after name selection is approved (`Q-019`) |
| DEC-014 | CDN assets: pin with integrity metadata, or self-host | ✅ Resolved: Owner selects self-hosting vendor assets (`TASK-106`) |
| DEC-015 | Backup retention, RPO/RTO, restore-test cadence | TASK-102 |
| DEC-016 | Privacy/retention rules for all stored personal data | TASK-801 |

---

## Tier 1 — Specification and architecture approval (prerequisite to all Tier 2+)

| ID | Task | Status | Blocking decisions | Notes |
|---|---|---|---|---|
| TASK-001 | Owner reviews and approves `design/SPECIFICATION.md` | ✅ | None | **Approved by owner 2026-11-23.** Authoritative product contract established. |
| TASK-002 | Owner reviews and approves `design/ARCHITECTURE.md` | ✅ | None | **Approved by owner 2026-11-23.** Authoritative technical architecture established. |
| TASK-003 | Owner confirms all unverified implemented behaviors (§2.2 of SPEC) | ✅ | None | **Resolved 2026-11-25:** `DEC-010` (age 1–80, 10-digit phone storage / display formatting) and `DEC-011` (7-day / 28-day pickup windows) confirmed by owner. |
| TASK-004 | Owner resolves all documentation conflicts (CON-001 through CON-008 in TRACEABILITY_MATRIX) | ✅ | None | **Resolved 2026-11-25:** All conflicts `CON-001`–`CON-008` resolved (`CON-008` resolved via `DEC-006`: numeric-only tags across inventory and orders, tracked in `TASK-401`). |

---

## Tier 2 — Security and production readiness (after Tier 1 approved)

| ID | Task | Status | Blocking | SPEC/DEBT ref | Notes |
|---|---|---|---|---|---|
| TASK-201 | Require `SECRET_KEY` from env; fail startup without it; remove `loremipsum` fallback | 🔴 | DEC-003 | DEBT-002 | Add startup validation; document rotation procedure |
| TASK-202 | Add login CSRF token and rate limiting; convert logout to POST with CSRF | ✅ | None | DEBT-004, DEBT-005 | Implemented in `app.py`, `utils.py` (`LoginRateLimiter`), `login.html`, `base.html`; 4 regression tests in `tests/test_auth_security.py` |
| TASK-203 | Disable `debug=True` in production entry point; add WSGI entry point | 🔴 | DEC-002 | DEBT-001 | Separate `app.py` dev runner from production WSGI entry |
| TASK-204 | Centralize SQLite connection creation; enable `PRAGMA foreign_keys=ON` on all connections | ⏸ | None | DEBT-007 | Deferred to deployment/migration phase per owner decision |
| TASK-205 | Assign single scheduler owner; remove import-time APScheduler startup | 🔴 | DEC-002 | DEBT-010 | Production process model must be decided first |
| TASK-206 | Add global session cookie security config (Secure, HttpOnly, SameSite) and security headers | 🔴 | DEC-001, DEC-002 | DEBT-013 | Requires HTTPS proxy knowledge |
| TASK-207 | Define and document trusted reverse-proxy forwarding header policy | 🔴 | DEC-001, DEC-002 | DEBT-014 | Currently trusts `X-Forwarded-For` without defined proxy boundary |

---

## Tier 3 — Schema and data lifecycle (after Tier 2 or owner-permitted in parallel)

| ID | Task | Status | Blocking | SPEC/DEBT ref | Notes |
|---|---|---|---|---|---|
| TASK-601 | Design and implement versioned migration framework; remove request-time DDL | ✅ | None | DEBT-006, PART-006 | Implemented `migrations.py` (`schema_migrations`, v1–v3) and `scripts/migrate_db.py`; removed `ensure_schema`/`ensure_pickup_schema` request-time DDL from `app.py`, `requester_links.py`, `order_intake.py`, `pickup_policy.py`; applied to `data/processed/pif.db` with backup; 162/162 tests pass |
| TASK-602 | Inspect active database schema against tracked design documentation | ✅ | None | DEBT-017 | Read-only inspection of `data/processed/pif.db` completed 2026-11-25: `integrity_check = ok`, `0` FK errors, `0` `orders` orphans; documented missing maintenance tables (`admin_changes`, `workshop_submissions`, `order_pickup_tracking`, `pickup_reminder_delivery`), legacy staging tables (`bikes`, `bikes_test`, `orders_50`, `orders_old`, `orders_test`), and FK gaps in `design/database.md` |
| TASK-603 | Implement authorized Excel workbook importer for historical data cutover | 🔴 | DEC-007 | TODO-001 | Needs approved workbook, mapping rules, rehearsal, backup, sign-off. No cutover without all gates. |
| TASK-604 | Add startup schema-version readiness check | ✅ | None | PART-006 | Implemented `verify_schema_ready()` in `migrations.py` and `check_startup_readiness()` in `app.py` (`if __name__ == '__main__'`); fails fast with operator command if DB is missing or behind `EXPECTED_SCHEMA_VERSION`; tested in `tests/test_migrations.py` (163/163 tests pass) |
| TASK-605 | Audit and document active database foreign key gaps; add constraints progressively | ⏸ | TASK-603 | DEBT-007 | Deferred until after `TASK-603` historical order cutover (matches `TASK-204`); 0 current `orders` orphans found in `TASK-602` |
| TASK-401 | Align `bike_inventory.bike_tag` and `orders.bike_tag` to a shared numeric-only data type & validation | ✅ | None | Q-006 / CON-008 | Implemented in `scripts/migrate_bike_tag_numeric.py`, `admin_tools.py`, `workshop.py`, `volunteer_entry.py`; applied to `data/processed/pif.db` with backup `pif-before-bike-tag-numeric-20261125T072700Z.db` (14,994 bikes, 4 corrected, 1 placeholder deleted, 2 zero orders nulled, 0 FK errors, integrity ok, 160/160 tests pass) |
| TASK-611 | Update database schema for `volunteers` (`joined_on`, `is_active`) and ensure `volunteer_hours` table matches app requirements | ✅ | None | REQ-011, REQ-012 | Implemented in `scripts/migrate_volunteer_clock.py` |
| TASK-612 | Create reusable migration code for `volunteers` from `PIF Volunteer Reporting time clock.xlsx` | ✅ | None | REQ-011 | Implemented in `scripts/migrate_volunteer_clock.py` (Title-Case standardization, 180-day cutoff) |
| TASK-613 | Create reusable migration code for `volunteer_hours` table implementing Option B catch-up backfill on open shop days | ✅ | None | REQ-012 | Implemented in `scripts/migrate_volunteer_clock.py` (backfills >24h entries across Mon/Wed/Sat for B/R, Mon/Wed for S with note 'Catchup hours') |
| TASK-614 | Rehearse migration on a test database copy, reconcile entries, and execute one-time migration with backup | ✅ | None | REQ-001 | Applied to `data/processed/pif.db` with backup `pif-before-volunteer-clock-20261124T073832Z.db` (493 vols, 5,466 shifts, 0 FK errors, integrity ok) |
| TASK-615 | Upgrade `shops` table with `address`, `landmark`, and `store_hours` | ✅ | None | REQ-006 | Implemented in `scripts/migrate_volunteer_clock.py` (resolves legacy `bikes` FK mismatch as well) |
| TASK-616 | Create reusable migration code for `Finished Bike Inventory` from `PIF 2025 .xlsx` into `bike_inventory` and `bike_contributions` | ✅ | None | REQ-003, REQ-010 | Implemented in `scripts/migrate_bike_inventory.py` (filters placeholders, deduplicates canonical tags, maps shops, moving 2-year window for new profiles, alias mapping, and review doc `design/volunteer-reconciliation-2025-2026.md`) |
| TASK-617 | Rehearse bike inventory migration on test copy, reconcile records, and execute one-time migration with backup | ✅ | None | REQ-001 | Applied to active `data/processed/pif.db` with backup `pif-before-bike-inventory-20261124T195158Z.db` (14,995 bikes, 15,461 contributions, 167 new volunteers, 0 FK errors, integrity ok, 156/156 tests pass) |

---

## Tier 4 — Operations and deployment (after Tier 2)

| ID | Task | Status | Blocking | SPEC/TODO ref | Notes |
|---|---|---|---|---|---|
| TASK-101 | Research and select production stack (WSGI server, proxy, service manager); produce deployment manifest | 🔴 | DEC-001, DEC-002 | TODO-005 | Agent-assisted; keep selection open until host connectivity test |
| TASK-102 | Implement and verify daily offsite backup automation | 🔴 | DEC-015 | NFR-010 | Define destination, encryption, retention, SQLite WAL handling, restore procedure |
| TASK-103 | Write operational runbook (provisioning, reset, backup/restore drills, incident response) | 🔴 | DEC-004, TASK-101 | TODO-006 | Cannot write until WSGI/process model is chosen |
| TASK-104 | Add `.env.example` configuration template | ✅ | None | TODO-008 | Completed by owner (template added to project root) |
| TASK-105 | Add CI workflow; include Node test prerequisite and safe email overrides | ✅ | None | TODO-007 | Completed: added `.github/workflows/ci.yml` running Python 3.12 test suite, syntax compilation, safe email flags, and Node 20 runner for `tests/test_order_actions.cjs` |
| TASK-106 | Pin all CDN dependency versions; evaluate adding integrity metadata or self-hosting | ✅ | None | DEBT-011 | Self-hosted pinned Bootstrap 5.3.0, jQuery 3.7.1, DataTables 1.13.6, Chart.js 4.4.7, and Patrick Hand font under `static/vendor/` (`base.html`, `explorer.html`, `dashboard.html`); 0 external CDN assets remaining |
| TASK-107 | Connectivity test at organization shop for staff access and public link reachability | 🔴 | DEC-001 | O-009 | Owner action; test before choosing host |
| TASK-108 | Configure Tailscale on production host; document device authorization and recovery | 🔴 | TASK-101 | REQ-028 | Do not mark complete until tested |

---

## Tier 5 — Email and notifications (after Tier 2, after DEC-009)

| ID | Task | Status | Blocking | SPEC/PART ref | Notes |
|---|---|---|---|---|---|
| TASK-701 | Define and document SMTP sender, test-recipient policy, preview retention, approval gate | ✅ | None | PART-002 | `DEC-009` resolved 2026-11-26: SMTP sender & test inbox configured; triggers (create, Contacted, 24h reminder, optional completion) documented; live delivery gated on app testing + `TASK-703` |
| TASK-702 | Implement single-owner scheduler with durable claim, idempotent delivery, retry bounds, monitoring | 🔴 | TASK-205 | PART-001 | `send_due_reminders()` + `pickup_reminder_delivery` already implemented; needs single-owner runner (`TASK-205`) |
| TASK-703 | Verify live SMTP delivery in staging environment with test-recipient | 🟡 | None | PART-002 | `TASK-701` complete; ready for staging test with `EMAIL_MODE=test` when ready |

---

## Tier 6 — UAT and transition (after Tiers 1–4 and TASK-603)

| ID | Task | Status | Blocking | SPEC ref | Notes |
|---|---|---|---|---|---|
| TASK-501 | Define UAT functional scenarios (order creation, transitions, completion, other flows) | 🔴 | DEC-007 | REQ-025, O-007 | Historical data ambiguity is NOT a UAT gate |
| TASK-502 | Execute UAT with staff; collect acceptance sign-off | 🔴 | TASK-501, TASK-603 | O-005 | Requires migrated or controlled test data |
| TASK-503 | Plan and execute Google Sheets final export/handoff and portal switch-over | 🔴 | TASK-502 | O-008, REQ-031 | Define cut-over date and sign-off procedure |

---

## Tier 7 — Technical debt remediation (prioritize after security baseline)

| ID | Task | Status | DEBT ref | Notes |
|---|---|---|---|---|
| TASK-801 | Fix bare `except` suppression in `utils.py` formatting helpers | ✅ | DEBT-012 | Completed: replaced bare `except:` with explicit `(ValueError, TypeError, IndexError)` in `format_date` and `(ValueError, TypeError)` in `clean_int`; regression unit tests added |
| TASK-802 | Move order browsing filters/grouping/pagination into SQL | ⏸ | DEBT-008 | Deferred until data volume justifies it; add regression tests first |
| TASK-803 | Resolve `definitions/` untracked directory ownership and purpose | ✅ | DEBT-018 | Verified already committed and tracked on `main` (`029a613`); working tree clean |
| TASK-804 | Resolve `.vscode/extensions.json` staged change | ✅ | DEBT-018 | Verified already committed and tracked on `main` (`029a613`); working tree clean |
| TASK-805 | Archive or rewrite `design/git-handoff.md` (describes superseded `2fd083b` state) | ✅ | CON-004 | Completed: added archival banner and warning notice pointing developers to `AGENTS.md`, `SPECIFICATION.md`, and `ARCHITECTURE.md` |
| TASK-806 | Implement approved Order Desk redesign without bulk grouping | ✅ | None | Completed: independent order cards per recipient/bike, collapsed card summary (`Contact → Recipient`) with prominent bike criteria badges, expanded 2-column layout (Contact Info on left, Recipient & Bike Requirements on right, full-width Notes beneath), strict recipient/contact field separation, top-level Actions dropdown accessible without scrolling in both collapsed and expanded states; 156/156 tests pass |
| TASK-807 | Establish unified page shell, shared CSS tokens, and reusable template primitives | ✅ | None | Consolidated all inline `<style>` blocks from `base.html`, `index.html`, and `explorer.html` into `whiteboard.css` (`:root` design tokens, left-aligned `.portal-page-header`, `.marker-panel`, `.table`, `#orderTabs`, DataTables); added `templates/_ui.html` `page_header` macro and adopted on `index.html` & `explorer.html`; 163/163 tests pass |
| TASK-808 | Align Order Explorer, New Order, Reporting Dashboard, Request Links, and Login to unified template | ✅ | None | Applied `page_header()` macro and `.marker-panel` consistency across `explorer.html`, `add.html` (preserving requester mode), `dashboard.html`, `request_links.html`, and `login.html`; 163/163 tests pass |
| TASK-809 | Align Staff Workshop pages (Volunteers, Finished Bikes, Volunteer Hours, QR Links) to unified template | ✅ | None | Applied `page_header()` macro across all 9 Staff Workshop templates (`volunteers.html`, `volunteer_profile.html`, `volunteer_impact_preview.html`, `inventory*.html`, `volunteer_hours*.html`, `volunteer_entry_links.html`); 163/163 tests pass |
| TASK-810 | Polish Public Volunteer mobile-first pages (`log-hours`, `finished-bike`, impact card, receipts) to unified template | ✅ | None | Applied `page_header()` across `volunteer_log_hours.html`, `volunteer_finished_bike.html`, `volunteer_hours_thanks.html`, `volunteer_bike_thanks.html`, `volunteer_unavailable.html`, and `request_result.html`, preserving mobile-first ergonomics and zero-staff-nav boundary; 163/163 tests pass |

---

## Deferred / explicitly out of scope

| ID | Item | Reason |
|---|---|---|
| TASK-D01 | Volunteer-hours reporting | Planned; no approved metric definition. Define before implementation. |
| TASK-D02 | Workshop-activity reporting | Planned; no approved scope, metric, or audience. Define before implementation. |
| TASK-D03 | QR artwork generation | Deferred until stable production address confirmed. |
| TASK-D04 | Order header / durable request identity | On hold per SPEC Q-014 and ARCH PA-009. Owner confirms not currently needed. |
| TASK-D05 | Tag format unification (order completion ↔ inventory) | ✅ Moved to `TASK-401` per `DEC-006` (2026-11-25): numeric-only shared data type approved. |
| TASK-D06 | Staff role model beyond one-tier | On hold per O-002. Revisit only if operational needs change. |
| TASK-D07 | Public volunteer authentication (PIN / QR / sign-in) | ✅ Closed per `DEC-005` (2026-11-26): owner confirms no-login name selection is approved; no PIN/QR auth needed. |
| TASK-D08 | Reintroduce removed prototypes (Streamlit, legacy import/setup scripts) | Do not reintroduce without specific requirement and owner approval. |
