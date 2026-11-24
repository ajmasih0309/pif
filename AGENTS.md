# AGENTS.md — PIF Portal Development Conventions

**Updated:** 2026-11-23 (development baseline established; re-verified 2026-11-23)
**Authoritative baseline:** `main` at `9568412` | Python: `156 tests / ~7 s`

---

## Mandatory reading before any change

1. Read [PROJECT_NOTES.md](PROJECT_NOTES.md) for current project decisions.
2. Read [design/SPECIFICATION.md](design/SPECIFICATION.md) as the product contract.
3. Read [design/ARCHITECTURE.md](design/ARCHITECTURE.md) for proposed technical design.
4. Read [CURRENT_STATUS.md](CURRENT_STATUS.md) for the latest verified state.
5. Read [TASKS.md](TASKS.md) before starting any implementation work.

---

## Safety rules (non-negotiable)

- **Never send real email** during development or tests. Use `EMAIL_MODE=disabled` or mocked SMTP.
- **Preserve the active database.** Test all database changes on a temporary copy first.
- **Never replace the active database** (`data/processed/pif.db` or the path in `.env`) without an approved backup, rehearsal, and owner sign-off.
- **Never commit** `.env`, databases, workbook exports, email previews, or private credentials.
- **Do not silently change architecture or requirements.** Raise conflicts explicitly and stop.

---

## Development workflow

### Before starting a task

- Confirm the task is listed in [TASKS.md](TASKS.md) and that required owner decisions are resolved.
- Verify no blocking open questions in [design/SPECIFICATION.md §9](design/SPECIFICATION.md) apply.

### Running tests

Always run the full Python test suite with safe email overrides and a temporary database:

```sh
PYTHONDONTWRITEBYTECODE=1 \
EMAIL_MODE=disabled \
EMAIL_LIVE_ENABLED=false \
EMAIL_REMINDERS_ENABLED=false \
DB_PATH=/tmp/pif-test-$$.db \
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```

Expected baseline: **156 tests / ~7 s** (all pass). Never commit if any test fails.

The Node order-action test also exists and must be run when Node is available:

```sh
node --test tests/test_order_actions.cjs
```

Node is currently unavailable on the audit shell; this test is unverified at baseline.

### After completing a task

- Update [CURRENT_STATUS.md](CURRENT_STATUS.md) with the new test count and evidence.
- Update [TASKS.md](TASKS.md) to mark completed items and add any discovered tasks.
- Update [CHANGELOG.md](CHANGELOG.md) with the change.
- Update [design/TRACEABILITY_MATRIX.md](design/TRACEABILITY_MATRIX.md) for any requirement changes.
- Commit with a meaningful message referencing the task ID.

---

## What must not be done without an explicit owner decision

| Prohibited action | Blocking document |
|---|---|
| Replace or rewrite the active database | PROJECT_NOTES §Data migration; REQ-001 |
| Merge historical CSV namespace into active orders | PROJECT_NOTES §Data migration |
| Add order-header table or shared completion lifecycle | SPEC REQ-021; ARCH §Bulk orders |
| Add inventory-allocation semantics to Finished Bikes | SPEC REQ-003; ADR-001 |
| Add volunteer authentication to public attribution forms | SPEC REQ-004; ADR-002 |
| Start live email or reminder delivery | SPEC REQ-008; PROJECT_NOTES §Email |
| Deploy to production | SPEC §11; ARCH §14 |
| Add new reports without an approved metric definition | SPEC REQ-006; ARCH §8 |
| Change pickup window values (7 / 28 days) | SPEC REQ-007 |
| Change tag format or add uniqueness rules to orders | SPEC Q-006; PART-005 |

---

## Code conventions

- Python module files follow the existing pattern: flat modules in the project root, `scripts/` for CLI tools, `tests/` for all tests.
- All tests use temporary SQLite databases. No test may touch `data/` paths.
- Business rules belong in domain modules (`pickup_policy.py`, `order_intake.py`, etc.), not in `app.py` route handlers.
- SQL connection setup (including `PRAGMA foreign_keys`) must go through the central connection factory in `database.py`; do not add per-module connection overrides.
- Do not add request-time DDL (`CREATE TABLE IF NOT EXISTS` in route handlers). Flag it as DEBT-006 technical debt until a migration plan is approved.
- Keep existing docstrings and comments unless they are demonstrably incorrect.

---

## Documentation authority

| Document | Purpose |
|---|---|
| `PROJECT_NOTES.md` | Current project decisions; supersedes older notes |
| `design/SPECIFICATION.md` | Product contract; tracks requirements and open questions (**Approved by owner 2026-11-23**) |
| `design/ARCHITECTURE.md` | Authoritative technical design (**Approved by owner 2026-11-23**) |
| `design/TRACEABILITY_MATRIX.md` | Links requirements to implementation evidence |
| `CURRENT_STATUS.md` | Latest verified implementation state |
| `TASKS.md` | Outstanding work items |
| `CHANGELOG.md` | Record of changes |
| `VERIFICATION.md` | Evidence register |
| `README.md` | Onboarding and usage guide |
| `design/database.md` | Schema details and maintenance procedures |
| `design/operations.md` | Proposed operating guidance (not a production approval) |
| `design/pif-technical-audit-2026-11-23.md` | Authoritative read-only audit evidence |

Do not use `design/git-handoff.md` as a current-state reference. It describes a superseded branch state (`2fd083b`).

---

## Universal Transferable Memories (UTM) Protocol

Every developer or AI agent working on PIF Portal must maintain persistent, self-contained transferable memories across each work step:

1. **Zero Context Loss**: Never rely solely on chat conversation memory. Every decision, architectural agreement, status change, and verification result must be written immediately into the governing project documents (`design/SPECIFICATION.md`, `design/ARCHITECTURE.md`, `CURRENT_STATUS.md`, `TASKS.md`, `VERIFICATION.md`, `CHANGELOG.md`).
2. **Synchronized Documentation**: At each task step, update:
   - `TASKS.md` to reflect task state changes with evidence references.
   - `VERIFICATION.md` with exact command, parameters, execution time, and outcome for all tests or inspections.
   - `CURRENT_STATUS.md` with active blockers, worktree state, and current milestone.
   - `CHANGELOG.md` with a reverse-chronological entry explaining what changed and why.
3. **Traceability**: All requirement and design changes must flow through `design/TRACEABILITY_MATRIX.md` to keep requirements, architecture, code, and test evidence 100% aligned.
