# CHANGELOG.md — PIF Portal

This file records significant changes in reverse-chronological order. Each entry identifies what changed, the evidence basis, and whether a decision or approval is required.

Format: `## [date] — brief description`

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
