# CHANGELOG.md — PIF Portal

This file records significant changes in reverse-chronological order. Each entry identifies what changed, the evidence basis, and whether a decision or approval is required.

Format: `## [date] — brief description`

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
