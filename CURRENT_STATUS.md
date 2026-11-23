# CURRENT_STATUS.md — PIF Portal

**Status date:** 2026-11-23  
**Git baseline:** `main` at `00c864b` (aligned with `origin/main`)  
**Phase:** Development baseline established. Specification and architecture under owner review.

---

## Test baseline (re-verified 2026-11-23)

| Check | Result |
|---|---|
| Python test suite (155 tests) | **PASS — 155 tests in 7.17 s** |
| Python syntax compilation | **PASS** |
| `git diff --check` | **PASS** (no whitespace errors) |
| Node order-action test (`test_order_actions.cjs`) | **NOT RUN** — Node unavailable in current shell |
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
| Staff login | ✅ Implemented (source-tested) | Routes covered indirectly; no auth-hardening test suite |
| Order Desk | ✅ Implemented and tested | Card/search/workflow tests |
| Order Explorer | ✅ Implemented and tested | Covered in search and workflow tests |
| New Order (multi-recipient) | ✅ Implemented and tested | Intake/workflow tests |
| Order transitions (Open → Contacted → Completed / Cancelled → Open) | ✅ Implemented and tested | Workflow and policy tests |
| Pickup policy (7-day Public, 28-day Pedal Partner, no Specialty deadline) | ✅ Implemented and tested | Policy tests |
| Pickup reminders (APScheduler 15-min job) | ⚠️ Partial — operational behavior unverified | In-process scheduler not production-proven |
| Email (preview / disabled / test / live gates) | ⚠️ Partial — live delivery unverified | Tests use mocks or disabled mode |
| Requester links (expiring, one-use, hashed) | ⚠️ Partial — public reachability deployment-dependent | Intake tests pass |
| Bike Distribution reporting | ✅ Implemented and tested | 7 dashboard regressions |
| Finished Bike Inventory (staff + public self-attribution) | ✅ Implemented and tested | Workshop/volunteer tests |
| Volunteer profiles (staff create/edit) | ✅ Implemented and tested | Workshop tests |
| Volunteer hours (staff correct/void; public add-only) | ✅ Implemented and tested | Workshop/volunteer/impact tests |
| Volunteer impact (year totals, contributed bikes, weekly strip) | ✅ Implemented and tested | Impact tests |
| Controlled maintenance CLI | ✅ Implemented and tested | Admin/migration/repair tests |
| Historical CSV rehearsal | ✅ Implemented and tested | Migration tests (legacy July CSV only) |
| Historical Excel importer / cutover | ❌ Not implemented | Explicitly pending; CSV rehearsal is not the importer |
| Volunteer-hours reporting | ❌ Not implemented | Documented as planned; no route/template found |
| Workshop-activity reporting | ❌ Not implemented | Documented as planned; no route/template found |
| QR artwork / production-reachable URLs | ❌ Not implemented | Waiting on stable production address |
| Production WSGI configuration | ❌ Not implemented | No WSGI entry point, service definition, or CI found |
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
| DEBT-004 | Login form has no CSRF token and no visible rate limiting | Credential guessing / CSRF exposure |
| DEBT-005 | Logout is a GET action | No CSRF protection on logout |
| DEBT-006 | Schema lifecycle split (request-time DDL + CLI) | No single migration contract |
| DEBT-007 | `foreign_keys=ON` only on workshop/CLI connections | Inconsistent integrity enforcement |
| DEBT-010 | Scheduler starts at app import | Multi-process risk of duplicate schedulers |
| DEBT-013 | No global session-cookie security, CSP, or proxy trust config | Security boundary undefined |

---

## Worktree state

Untracked/modified files relative to committed `main`:

| File | State | Notes |
|---|---|---|
| `.gitignore` | Modified | Not committed |
| `.vscode/extensions.json` | Staged (added) | Authorship/purpose unverified |
| `PROJECT_NOTES.md` | Modified | Current decisions updated after audit |
| `README.md` | Modified | Updated post-audit |
| `design/dashboard-count-review.md` | Modified | Updated post-audit |
| `design/database.md` | Modified | Updated post-audit |
| `design/git-handoff.md` | Modified | Updated post-audit |
| `design/order-workflow-review.md` | Modified | Updated post-audit |
| `definitions/` | Untracked | Reference files; purpose unverified |
| `progress/` | Untracked | Audit progress artifacts |
| `design/SPECIFICATION.md` | New (not committed) | Reconstructed product spec |
| `design/ARCHITECTURE.md` | New (not committed) | Proposed architecture |
| `design/TRACEABILITY_MATRIX.md` | New (not committed) | Requirements traceability |
| `AGENTS.md` | Updated | Development conventions |
| `CURRENT_STATUS.md` | New | This file |
| `TASKS.md` | New | Outstanding work |
| `VERIFICATION.md` | New | Evidence register |
| `CHANGELOG.md` | New | Change history |
