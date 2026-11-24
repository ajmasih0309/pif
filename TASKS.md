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
| DEC-005 | Whether public volunteer attribution without authentication is acceptable for deployment | TASK-301 |
| DEC-006 | Tag format for order completion: numeric-only or align with inventory text format | TASK-401 |
| DEC-007 | UAT functional scenarios, acceptance checklist, Google Sheets switch-over date | TASK-501 |
| DEC-008 | Request-time DDL vs. explicit versioned migrations | TASK-601 |
| DEC-009 | SMTP sender, test-recipient policy, preview retention, approval gate | TASK-701 |
| DEC-010 | Confirm age 1–80 and phone normalization as approved intake requirements | TASK-003 |
| DEC-011 | Confirm 7-day / 28-day pickup windows still correct | TASK-003 |
| DEC-012 | Confirm approved layout: "Desktop unchanged" or unified two-column from 768px | TASK-004 |
| DEC-013 | Confirm volunteer impact aggregate visibility rules | TASK-302 |
| DEC-014 | CDN assets: pin with integrity metadata, or self-host | TASK-801 |
| DEC-015 | Backup retention, RPO/RTO, restore-test cadence | TASK-102 |
| DEC-016 | Privacy/retention rules for all stored personal data | TASK-801 |

---

## Tier 1 — Specification and architecture approval (prerequisite to all Tier 2+)

| ID | Task | Status | Blocking decisions | Notes |
|---|---|---|---|---|
| TASK-001 | Owner reviews and approves `design/SPECIFICATION.md` | ✅ | None | **Approved by owner 2026-11-23.** Authoritative product contract established. |
| TASK-002 | Owner reviews and approves `design/ARCHITECTURE.md` | ✅ | None | **Approved by owner 2026-11-23.** Authoritative technical architecture established. |
| TASK-003 | Owner confirms all unverified implemented behaviors (§2.2 of SPEC) | 🔴 | DEC-010, DEC-011 | Age/phone/pickup windows/requester expiry/cookie lifetime |
| TASK-004 | Owner resolves all documentation conflicts (CON-001 through CON-008 in TRACEABILITY_MATRIX) | 🔴 | DEC-012 | Navigation shortcut, desktop layout, test totals, stale handoff |

---

## Tier 2 — Security and production readiness (after Tier 1 approved)

| ID | Task | Status | Blocking | SPEC/DEBT ref | Notes |
|---|---|---|---|---|---|
| TASK-201 | Require `SECRET_KEY` from env; fail startup without it; remove `loremipsum` fallback | 🔴 | DEC-003 | DEBT-002 | Add startup validation; document rotation procedure |
| TASK-202 | Add login CSRF token and rate limiting; convert logout to POST with CSRF | 🔴 | DEC-004 | DEBT-004, DEBT-005 | Do not add MFA or roles without DEC-004 decision |
| TASK-203 | Disable `debug=True` in production entry point; add WSGI entry point | 🔴 | DEC-002 | DEBT-001 | Separate `app.py` dev runner from production WSGI entry |
| TASK-204 | Centralize SQLite connection creation; enable `PRAGMA foreign_keys=ON` on all connections | ⏸ | None | DEBT-007 | Deferred to deployment/migration phase per owner decision |
| TASK-205 | Assign single scheduler owner; remove import-time APScheduler startup | 🔴 | DEC-002 | DEBT-010 | Production process model must be decided first |
| TASK-206 | Add global session cookie security config (Secure, HttpOnly, SameSite) and security headers | 🔴 | DEC-001, DEC-002 | DEBT-013 | Requires HTTPS proxy knowledge |
| TASK-207 | Define and document trusted reverse-proxy forwarding header policy | 🔴 | DEC-001, DEC-002 | DEBT-014 | Currently trusts `X-Forwarded-For` without defined proxy boundary |

---

## Tier 3 — Schema and data lifecycle (after Tier 2 or owner-permitted in parallel)

| ID | Task | Status | Blocking | SPEC/DEBT ref | Notes |
|---|---|---|---|---|---|
| TASK-601 | Design and implement versioned migration framework; remove request-time DDL | 🔴 | DEC-008 | DEBT-006, PART-006 | Do not remove request-time DDL until migration plan rehearsed on a copy |
| TASK-602 | Inspect active database schema against tracked design documentation | 🔴 | DEC-008 | DEBT-017 | Must not modify active database; report-only inspection |
| TASK-603 | Implement authorized Excel workbook importer for historical data cutover | 🔴 | DEC-007 | TODO-001 | Needs approved workbook, mapping rules, rehearsal, backup, sign-off. No cutover without all gates. |
| TASK-604 | Add startup schema-version readiness check | 🔴 | DEC-008 | PART-006 | Fail with clear operator message if schema not at expected version |
| TASK-605 | Audit and document active database foreign key gaps; add constraints progressively | 🔴 | TASK-602 | DEBT-007 | Do not add constraints that would reject existing records without reconciliation |

---

## Tier 4 — Operations and deployment (after Tier 2)

| ID | Task | Status | Blocking | SPEC/TODO ref | Notes |
|---|---|---|---|---|---|
| TASK-101 | Research and select production stack (WSGI server, proxy, service manager); produce deployment manifest | 🔴 | DEC-001, DEC-002 | TODO-005 | Agent-assisted; keep selection open until host connectivity test |
| TASK-102 | Implement and verify daily offsite backup automation | 🔴 | DEC-015 | NFR-010 | Define destination, encryption, retention, SQLite WAL handling, restore procedure |
| TASK-103 | Write operational runbook (provisioning, reset, backup/restore drills, incident response) | 🔴 | DEC-004, TASK-101 | TODO-006 | Cannot write until WSGI/process model is chosen |
| TASK-104 | Add `.env.example` configuration template | ✅ | None | TODO-008 | Completed by owner (template added to project root) |
| TASK-105 | Add CI workflow; include Node test prerequisite and safe email overrides | 🟡 | None | TODO-007 | Must run Node `test_order_actions.cjs` in CI |
| TASK-106 | Pin all CDN dependency versions; evaluate adding integrity metadata or self-hosting | 🔴 | DEC-014 | DEBT-011 | Chart.js currently has no version in template |
| TASK-107 | Connectivity test at organization shop for staff access and public link reachability | 🔴 | DEC-001 | O-009 | Owner action; test before choosing host |
| TASK-108 | Configure Tailscale on production host; document device authorization and recovery | 🔴 | TASK-101 | REQ-028 | Do not mark complete until tested |

---

## Tier 5 — Email and notifications (after Tier 2, after DEC-009)

| ID | Task | Status | Blocking | SPEC/PART ref | Notes |
|---|---|---|---|---|---|
| TASK-701 | Define and document SMTP sender, test-recipient policy, preview retention, approval gate | 🔴 | DEC-009 | PART-002 | No live delivery until all gates approved |
| TASK-702 | Implement single-owner scheduler with durable claim, idempotent delivery, retry bounds, monitoring | 🔴 | TASK-205, TASK-701 | PART-001 | Must not start until TASK-205 and TASK-701 complete |
| TASK-703 | Verify live SMTP delivery in staging environment with test-recipient | 🔴 | TASK-701 | PART-002 | Requires approved sender and test policy |

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
| TASK-801 | Fix bare `except` suppression in `utils.py` formatting helpers | 🟡 | DEBT-012 | Low-risk; can be done independently |
| TASK-802 | Move order browsing filters/grouping/pagination into SQL | ⏸ | DEBT-008 | Deferred until data volume justifies it; add regression tests first |
| TASK-803 | Resolve `definitions/` untracked directory ownership and purpose | 🟡 | DEBT-018 | Owner decision: commit, ignore, or remove |
| TASK-804 | Resolve `.vscode/extensions.json` staged change | 🟡 | DEBT-018 | Owner decision: commit or revert |
| TASK-805 | Archive or rewrite `design/git-handoff.md` (describes superseded `2fd083b` state) | 🟡 | CON-004 | Cannot delete without owner approval; mark as archived |

---

## Deferred / explicitly out of scope

| ID | Item | Reason |
|---|---|---|
| TASK-D01 | Volunteer-hours reporting | Planned; no approved metric definition. Define before implementation. |
| TASK-D02 | Workshop-activity reporting | Planned; no approved scope, metric, or audience. Define before implementation. |
| TASK-D03 | QR artwork generation | Deferred until stable production address confirmed. |
| TASK-D04 | Order header / durable request identity | On hold per SPEC Q-014 and ARCH PA-009. Owner confirms not currently needed. |
| TASK-D05 | Tag format unification (order completion ↔ inventory) | On hold per SPEC Q-006. Changes affect schema, migration, and reporting. |
| TASK-D06 | Staff role model beyond one-tier | On hold per O-002. Revisit only if operational needs change. |
| TASK-D07 | Public volunteer authentication (PIN / QR / sign-in) | On hold per Q-005. Must not add or reject without owner decision. |
| TASK-D08 | Reintroduce removed prototypes (Streamlit, legacy import/setup scripts) | Do not reintroduce without specific requirement and owner approval. |
