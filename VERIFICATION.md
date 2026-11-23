# VERIFICATION.md — PIF Portal Evidence Register

**Updated:** 2026-11-23  
**Baseline:** `main` at `00c864b` (aligned with `origin/main`)

This document records what has been verified, by what method, and what remains unverified. "Verified" means direct evidence was obtained. It does not mean production readiness or owner approval.

---

## 1. Source and test evidence (2026-11-23 audit)

### 1.1 Test suite

| Run | Date | Environment | Command | Result |
|---|---|---|---|---|
| Baseline re-verification | 2026-11-23 | Local `.venv` Python 3.14.7 / SQLite 3.53.4 / temp DB | `PYTHONDONTWRITEBYTECODE=1 EMAIL_MODE=disabled EMAIL_LIVE_ENABLED=false EMAIL_REMINDERS_ENABLED=false DB_PATH=/tmp/pif-baseline-test.db .venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v` | **PASS — 155 tests in 7.17 s** |
| Original audit run | 2026-11-23 | `.venv` / temp DB at `/private/tmp/pif-audit-disabled.db` | Same flags, audit DB path | **PASS — 155 tests in 7.09 s** |

No test failures on either run. Warning messages during email-negative tests are expected test behavior; no real email was sent.

### 1.2 Code quality checks

| Check | Date | Result | Notes |
|---|---|---|---|
| Python syntax compilation | 2026-11-23 | **PASS** | Primary modules and scripts |
| `git diff --check` | 2026-11-23 | **PASS** (no output) | Tracked-diff whitespace check only |
| Node `test_order_actions.cjs` | 2026-11-23 | **NOT RUN** | Node.js unavailable on audit shell |

### 1.3 Git state verification

| Item | Verified value |
|---|---|
| `main` HEAD | `00c864b389024ec8ed3b28df3d4d93a5c009a9ed` |
| `origin/main` | Aligned with local `main` at `00c864b` |
| `git diff --check` | No tracked whitespace errors |

---

## 2. Technology inventory (audit-verified from source)

| Layer | Verified |
|---|---|
| Runtime | Python 3.14.7, local `.venv` |
| Web framework | Flask 3.1.3; Jinja server-rendered templates |
| Scheduler | Flask-APScheduler 1.13.1 / APScheduler 3.11.3; in-process 15-minute reminder job |
| Database | SQLite 3.53.4; path controlled by `DB_PATH`; default `data/processed/pif.db` |
| Authentication | `users` table, Werkzeug password-hash verification, Flask signed session |
| Form protection | Custom `itsdangerous` session-bound signed tokens (not a global CSRF extension) |
| Email | Standard-library SMTP STARTTLS; preview / disabled / test-sink / live modes |
| UI libraries | Bootstrap 5.3, Patrick Hand font, Chart.js, jQuery, DataTables (all CDN-loaded) |
| Test runner | Python `unittest`; Node built-in runner for `test_order_actions.cjs` |
| Packaging | `requirements.txt` only; no `pyproject.toml`, lockfile, CI, or frontend bundler |

---

## 3. Feature-level evidence

For each implemented capability, evidence is the combination of source code presence and passing tests in the test suite above. "Source only" means no corresponding automated test was identified.

| Capability | Evidence type | Test files | Limitation |
|---|---|---|---|
| Staff login / session | Source + indirect test coverage | `test_order_workflow.py`, `test_workshop.py` | No dedicated auth-hardening test suite |
| Order Desk (cards, tabs, pagination, search) | Source + tests | `test_order_cards.py`, `test_order_search.py`, `test_order_workflow.py` | Browser/device/accessibility not tested |
| New Order (multi-recipient, validation, idempotency) | Source + tests | `test_intake.py`, `test_order_workflow.py` | Age/phone rules not confirmed as approved requirements |
| Order transitions (all states) | Source + tests | `test_order_workflow.py`, `test_pickup_policy.py` | Per-row lifecycle only; no order-header |
| Pickup policy (7-day / 28-day deadlines) | Source + tests | `test_pickup_policy.py` | Real scheduler execution not verified |
| Email (guarded modes, SMTP gating) | Source + tests (mocked) | `test_email_delivery.py`, `test_order_workflow.py` | Live SMTP not tested |
| Requester links (expiring, one-use, hashed) | Source + tests | `test_intake.py` | Public URL reachability deployment-dependent |
| Bike Distribution reporting | Source + tests | `test_dashboard.py` (7 regressions) | Counts order lines, not deduplicated bikes |
| Finished Bike Inventory | Source + tests | `test_workshop.py` | Optional; no allocation semantics |
| Volunteer profiles | Source + tests | `test_workshop.py` | No deletion; no role distinction |
| Volunteer hours (staff + public) | Source + tests | `test_volunteer_entry.py`, `test_workshop.py` | Self-reported; integrity controls not verified |
| Volunteer impact | Source + tests | `test_volunteer_impact.py` | Aggregate visibility rules not confirmed |
| Maintenance CLI (backup, audit, repair) | Source + tests | `test_admin_tools.py`, `test_history_migration.py`, `test_shop_migration.py` | Operator runbook not documented |
| Order action JavaScript behavior | Source only (CJS test not run) | `test_order_actions.cjs` | Node unavailable; unverified |

---

## 4. What has NOT been verified

The following are explicitly outside the current evidence base. Do not make claims about these items based on source tests alone.

| Item | Why unverified |
|---|---|
| Live SMTP delivery | Private environment; not in audit scope |
| APScheduler execution in production topology | No production process; multi-process risk undocumented |
| Browser visual behavior, responsiveness, accessibility | No browser testing performed |
| Active database schema and data quality | Private; intentionally not inspected |
| Backup creation and restore from backup | CLI code exists; no restore drill performed |
| Tailscale configuration and connectivity | No network testing performed |
| Production deployment host and stack | No production environment exists yet |
| Staff account lifecycle (provisioning, disable, reset) | No documented procedure |
| Public volunteer form abuse controls | In code; real-world adequacy not assessed |
| Node `test_order_actions.cjs` | Node.js unavailable on this shell |

---

## 5. Document evidence

| Document | Date | Evidence type | Status |
|---|---|---|---|
| `design/pif-technical-audit-2026-11-23.md` | 2026-11-23 | Read-only repository audit; primary evidence source | Current and authoritative |
| `progress/pif-technical-audit-2026-11-23.md` | 2026-11-23 | Audit progress record | Consistent with design version |
| `design/SPECIFICATION.md` | 2026-11-24 | Reconstructed product spec incorporating owner clarifications | Under owner review; not yet approved |
| `design/ARCHITECTURE.md` | 2026-11-24 | Proposed architecture incorporating owner clarifications | Under owner review; not yet approved |
| `design/TRACEABILITY_MATRIX.md` | 2026-11-24 | Requirements-to-implementation links | Under owner review; not yet approved |
| `PROJECT_NOTES.md` | 2026-11-23 | Current project decisions record | Authoritative; supersedes older notes |
| `README.md` | 2026-11-23 | Onboarding and usage guide | Current |
| `design/git-handoff.md` | Stale | Describes superseded `2fd083b` state | Do not use as current-state reference |

---

## 6. Evidence gaps requiring future verification

These must be verified before the corresponding capability is marked production-ready.

| Gap | Required verification method |
|---|---|
| Node `test_order_actions.cjs` | Run `node --test tests/test_order_actions.cjs` in an environment with Node installed |
| Active database schema | Run a report-only inspection (`admin_db.py --db ... audit`) against active DB without modification |
| Live SMTP delivery | Run against approved test-recipient with approved sender, in staging, after TASK-701 |
| Scheduler single-owner behavior | Integration test with two simultaneous workers; verify only one delivers |
| Browser / device / accessibility | Manual or automated browser test across staff-expected devices |
| Backup restore | Restore drill from a recent backup to a temporary environment |
| Production environment startup | Prove `debug=False`, valid `SECRET_KEY`, schema version check passing on a production-like host |
