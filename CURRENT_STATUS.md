# CURRENT_STATUS.md — PIF Portal

**Status date:** 2026-11-23 (re-verified 2026-11-23; full code audit completed 2026-11-23)
**Git baseline:** local `main` at `029a613` | `origin/main` at `00c864b`
**Phase:** Development baseline established. SPECIFICATION.md and ARCHITECTURE.md **approved by owner** 2026-11-23.

---

## Test baseline (re-verified 2026-11-23)

| Check | Result |
|---|---|
| Python test suite (160 tests) | **PASS — 160 tests in 8.05 s** (re-verified 2026-11-25 after TASK-202 login CSRF, rate limiting, and POST logout) |
| Python syntax compilation | **PASS** |
| `git diff --check` | **PASS** (no whitespace errors) |
| Node order-action test (`test_order_actions.cjs`) | Configured in CI (`.github/workflows/ci.yml`) — runs on Node 20 runner |
| CI workflow (TASK-105) | **CONFIGURED** — `.github/workflows/ci.yml` (Python 3.12, syntax compilation, safe email overrides, Node test, whitespace check) |
| Live SMTP | **NOT TESTED** — not in scope |
| Scheduler production execution | **NOT TESTED** — not in scope |
| Browser / device / accessibility | **NOT TESTED** — not in scope |
| Active database schema/data | **NOT INSPECTED** — private data not opened |

Test command used:
```sh
PYTHONDONTWRITEBYTECODE=1 EMAIL_MODE=disabled EMAIL_LIVE_ENABLED=false \
EMAIL_REMINDERS_ENABLED=false DB_PATH=/tmp/pif-baseline-test.db \
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```

---

## Implementation status by area

| Area | Status | Evidence |
|---|---|---|
| Staff login | ✅ Implemented and tested | Login CSRF, sliding-window rate limiting, and POST-only CSRF logout verified in `tests/test_auth_security.py` |
| Order Desk | ✅ Implemented and tested (Redesigned) | Independent order cards, 4-section expanded layout, responsive 2-column, Contact button; 156/156 tests pass |
| Order Explorer | ✅ Implemented and tested | Covered in search and workflow tests |
| New Order (multi-recipient) | ✅ Implemented and tested | Intake/workflow tests |
| Order transitions (Open → Contacted → Completed / Cancelled → Open) | ✅ Implemented and tested | Workflow and policy tests |
| Pickup policy (7-day Public, 28-day Pedal Partner, no Specialty deadline) | ✅ Implemented and tested | Policy tests |
| Pickup reminders (APScheduler 15-min job) | ⚠️ Partial — operational behavior unverified | In-process scheduler not production-proven |
| Email (preview / disabled / test / live gates) | ⚠️ Partial — live delivery unverified | Tests use mocks or disabled mode |
| Requester links (expiring, one-use, hashed) | ⚠️ Partial — public reachability deployment-dependent | Intake tests pass |
| Bike Distribution reporting | ✅ Implemented and tested | 7 dashboard regressions |
| Finished Bike Inventory (staff + public self-attribution) | ✅ Complete (TASK-616, TASK-617) | 14,995 bikes, 15,461 contributions, 167 new volunteers active in `pif.db`; 0 FK errors |
| Volunteer profiles (staff create/edit) | ✅ Implemented and populated | Workshop tests; 493 volunteers active in pif.db |
| Volunteer hours (staff correct/void; public add-only) | ✅ Implemented and populated | Workshop/volunteer/impact tests; 5,466 shifts active in pif.db |
| Volunteer historical migration (time clock) | ✅ Complete (TASK-611–614) | Successfully applied to `data/processed/pif.db` with backup; 17,099.13h migrated |
| Shop addresses & operating hours upgrade | ✅ Complete (TASK-615) | Active in `pif.db`: Bentonville, Rogers, Springdale addresses, landmarks, and hours |
| Volunteer impact (year totals, contributed bikes, weekly strip) | ✅ Implemented and tested | Impact tests |
| Controlled maintenance CLI | ✅ Implemented and tested | Admin/migration/repair tests |
| Historical CSV rehearsal | ✅ Implemented and tested | Migration tests (legacy July CSV only) |
| Historical Excel importer / cutover | ❌ Not implemented | Explicitly pending; CSV rehearsal is not the importer |
| Volunteer-hours reporting | ❌ Not implemented | Documented as planned; no route/template found |
| Workshop-activity reporting | ❌ Not implemented | Documented as planned; no route/template found |
| QR artwork / production-reachable URLs | ❌ Not implemented | Waiting on stable production address |
| Production WSGI configuration | ❌ Not implemented | No WSGI entry point or service definition (DEC-001/002 pending) |
| CI Workflow (GitHub Actions) | ✅ Complete (TASK-105) | `.github/workflows/ci.yml` runs Python 3.12 suite, compilation, safe email flags, and Node 20 runner |
| Operational runbook | ❌ Not implemented | No documented operator procedures |

---

## Architecture state

The application is a **Flask 3.1.3 / Jinja / SQLite 3.53.4** server-rendered monolith:

- Python 3.14.7, local `.venv` at project root
- APScheduler 3.11.3 / Flask-APScheduler 1.13.1 (in-process 15-minute reminder job)
- `itsdangerous` for signed form tokens; `werkzeug` for password hashing
- Bootstrap 5.3, Chart.js, jQuery, DataTables loaded from CDN (no local pinning)
- Entry point: `app.py` runs `debug=True` on port 5003 (development only)

All staff share one permission level (confirmed acceptable for initial release — O-002).

---

## Codebase scan & ongoing development status (verified 2026-11-23)

A full audit of the complete project folder confirmed:
- **Core modules**: 12 Python files in root (2,913 LOC total): `admin_tools.py`, `app.py`, `config.py`, `database.py`, `order_intake.py`, `order_search.py`, `pickup_policy.py`, `requester_links.py`, `utils.py`, `volunteer_entry.py`, `volunteer_impact.py`, `workshop.py`.
- **Scripts**: 5 CLI utilities in `scripts/`: `admin_db.py`, `fix_duplicate_shops.py`, `fix_person_ids.py`, `migrate_history.py`, `users.py`.
- **Tests**: 13 test files in `tests/` — 155 unit tests passing cleanly in 6.75 s.
- **Templates & Static Assets**: 23 HTML templates, 5 email templates, 7 JavaScript files in `static/js/`, Sharpie-on-whiteboard CSS (`static/css/whiteboard.css`).
- **Git branches**: All feature branches (`codex/responsive-portal`, `codex/spreadsheet-cleanup`, `codex/database-cleanup`) are 100% merged into `main`. No unmerged branches or WIP code branches exist.
- **Isolated preview code**: `data/previews/order-review-20261008-a770c3/` contains an archived October preview runner (`run.py`); it does not affect main runtime.

---

## Recent owner decisions (2026-11-23 follow-up)

- **DEC-001 (Host Selection)**: Placed on hold / deferred to deployment planning phase while app remains in active development.
- **DEC-003 (`SECRET_KEY` Production Enforcement)**: Placed on hold / deferred to production deployment setup.
- **DEC-004 (Staff Account Governance)**: Resolved — owner confirms no account lifecycle rules are enforced; staff account creation, activation, and modification workflows are intentionally skipped due to small, persistent staff headcount.
- **TASK-104 (`.env.example`)**: Completed — template committed to project root.
- **TASK-204 (Centralize `PRAGMA foreign_keys=ON`)**: Deferred to deployment/migration phase per owner request.
- **Git Sync**: User requested push/sync of approved `design/` documentation and tracking updates.

---

## Open owner decisions blocking next work

The following are unresolved as of 2026-11-23. No implementation work requiring these decisions should proceed without an explicit owner answer.

| ID | Decision |
|---|---|
| Q-001 | Production host (organization site vs. developer home) pending connectivity test; WSGI server and reverse proxy selection |
| Q-002 | Which process owns the APScheduler instance so it runs exactly once |
| Q-003 | `SECRET_KEY` must be mandatory at startup; session/credential rotation plan |
| Q-004 | Staff account provisioning, password reset, disable/revocation procedures |
| Q-005 | Whether public volunteer attribution without authentication is acceptable for deployment |
| Q-006 | Whether order completion should support text tags (matching inventory) or remain numeric-only |
| Q-008 | UAT functional scenarios, acceptance checklist, and Google Sheets switch-over date |
| Q-009 | Request-time DDL vs. explicit versioned migrations |
| Q-010 | SMTP sender, test-recipient policy, preview retention, approval gate for live mail |
| Q-011 | Which document is authoritative; whether stale handoff material should be archived |
| Q-015 | Whether age 1–80 and phone normalization are confirmed intake requirements |
| Q-016 | Whether 7-day / 28-day pickup windows are still correct |
| Q-017 | Whether the top-level New Order shortcut removal is the approved final decision |
| Q-018 | Approved layout: "Desktop unchanged" or unified two-column from 768px |
| Q-019 | Volunteer impact aggregate visibility rules |
| Q-020 | CDN assets: pin with integrity, or self-host |
| Q-021 | Backup retention, RPO/RTO, restore-test cadence |
| Q-022 | Privacy/retention rules for requester data, volunteer records, audit logs, email previews |

Owner-confirmed decisions (no longer blocking): O-001 through O-011, Q-007, Q-014.

---

## Known defects (not yet fixed)

See [design/SPECIFICATION.md §7](design/SPECIFICATION.md) for full debt register. High-priority items:

| ID | Defect | Risk |
|---|---|---|
| DEBT-001 | `app.py` runs `debug=True` on port 5003 | Must not reach production |
| DEBT-002 | `SECRET_KEY` falls back to literal `loremipsum` | Unsafe session secret |
| DEBT-006 | Schema lifecycle split (request-time DDL + CLI) | No single migration contract |
| DEBT-007 | `foreign_keys=ON` only on workshop/CLI connections | Inconsistent integrity enforcement |
| DEBT-010 | Scheduler starts at app import | Multi-process risk of duplicate schedulers |
| DEBT-013 | No global session-cookie security, CSP, or proxy trust config | Security boundary undefined |

---

## Worktree state

> [!NOTE] The local `main` branch is at `029a613`, one merge commit ahead of `origin/main` (`00c864b`). The local merge commit added documentation and reference files only; `app.py` and all Python source are identical to `origin/main`.

**Local-only commits (not yet pushed to `origin/main`):**

| Commit | Description |
|---|---|
| `029a613` | Merge branch `codex/database-cleanup` — added AGENTS.md, CHANGELOG.md, CURRENT_STATUS.md, TASKS.md, VERIFICATION.md, definitions/, progress/pif-technical-audit-2026-11-23.md; updated PROJECT_NOTES.md, README.md, .gitignore, .vscode/extensions.json; design docs, design/database.md, design/git-handoff.md, design/order-workflow-review.md, design/dashboard-count-review.md |

**Modified/untracked relative to committed `main` (`029a613`):**

| File | State | Notes |
|---|---|---|
| `.gitignore` | Modified (working tree) | Staged version differs from HEAD; working-tree change uncommitted |
| `design/SPECIFICATION.md` | Untracked | Reconstructed product spec; under owner review |
| `design/ARCHITECTURE.md` | Untracked | Proposed architecture; under owner review |
| `design/TRACEABILITY_MATRIX.md` | Untracked | Requirements traceability; under owner review |
| `design/operations.md` | Untracked | Proposed operating guidance; under owner review |
| `design/pif-technical-audit-2026-11-23.md` | Untracked | Authoritative read-only audit evidence |
