# PIF Portal — Reconstructed Product Specification

> Prepared: 2026-11-24 (owner clarifications incorporated)  
> **Owner review status: APPROVED by project owner — 2026-11-23**  
> Implementation baseline audited: `main` at `029a613` (local HEAD) | `origin/main` at `00c864b`  
> Full code audit completed: 2026-11-23 — all 11 Python modules, 5 CLI scripts, 30 templates, 7 JS files verified  
> Source basis: supplied project source set (`README.md`, `PROJECT_NOTES.md`, `architecture.md`, `database.md`, `operations.md`, `order-workflow-review.md`, `dashboard-count-review.md`, `git-handoff.md`, `technical-audit.md`, `pif-technical-audit-2026-11-23.md`) plus owner clarifications dated 2026-11-24

This is a reconstruction for owner review, not a declaration that the current implementation is correct or that every observed behavior was previously approved. Do not use this document as authorization for a migration, production deployment, security exception, or feature change.

## 0. How to read this document

The requested three-layer development separation is applied as:

1. **Specification — what and why:** user needs, product rules, scope, acceptance conditions, and unresolved decisions.
2. **Architecture — how:** system boundaries, components, data flow, operational model, and technical constraints.
3. **Implementation — what exists:** code and test evidence, gaps, defects, and traceability.

Evidence labels:

- **AUDIT-VERIFIED:** directly reported by the 2026-11-23 repository audit from source, tests, or tracked documentation.
- **DOC-REPORTED:** the audit says a tracked project document records the item, but that primary document was not available for direct review here.
- **INFERENCE / PROPOSAL:** a reconstruction or recommendation, not an approved project decision.
- **OWNER DECISION:** cannot be finalized without the project owner.
- **NOT VERIFIED:** deliberately outside the audit's evidence, often because it depends on private data or a live environment.

A feature being implemented or tested does **not** by itself prove that its current behavior is the approved requirement.

## 1. Product overview

PIF Portal is currently a server-rendered web application supporting a bicycle program's order desk and a growing set of workshop and volunteer workflows. The audited implementation covers staff order intake and tracking, requester-facing links, pickup reminders and email, finished-bike inventory, volunteer records and time logging, volunteer impact information, a limited distribution dashboard, and database maintenance utilities.

The original product statement, target users, organizational goals, and success measures are **not recoverable from the audit alone**. The above is a description of current scope, not a complete approved product vision.

### 1.1 Actors evidenced by the audit

| Actor | Evidenced interaction | Important qualification |
|---|---|---|
| Staff user | Logs in; manages orders; uses workshop, inventory, volunteer, and maintenance-related workflows | All authenticated staff share the same permission level; owner confirmed this is acceptable for the initial release. |
| Requester | Uses a staff-issued, expiring, one-use link to submit an order request | Public URL reachability depends on deployment. |
| Volunteer | Uses public forms to attribute hours or finished-bike contributions to a selected volunteer record | Name selection is attribution, not identity verification or authentication. |
| Operator / maintainer | Runs database initialization, backup/audit, repair, and migration CLIs | Operator ownership and runbooks are not defined. |

## 2. Confirmed requirements

The following are the strongest requirement-like statements supported by the audit. The primary project documents are now available and have been reviewed. Original discussion history beyond these documents is still not available, so decisions not explicitly recorded there remain provisional.

| ID | Requirement / product constraint | Evidence and qualification |
|---|---|---|
| REQ-001 | The historical Excel workbook cutover is not complete; the active database must not be replaced as part of the current work. | DOC-REPORTED. The audit says historical cleanup/cutover is explicitly pending and the active database should not be replaced yet. Exact cutover authority and acceptance process are unresolved. |
| REQ-002 | The historical CSV rehearsal script is not the importer for the current Excel workbook/cutover. | DOC-REPORTED / AUDIT-VERIFIED. The script handles an older normalized July CSV set only. |
| REQ-003 | Finished Bike Inventory is optional; it must not be treated as an order-allocation or availability-reservation system. | DOC-REPORTED. The audit describes this as intentional. Do not silently add allocation semantics. |
| REQ-004 | Public volunteer identity selection is for attribution, not proof of identity or volunteer authentication. | DOC-REPORTED. Public name lookup and self-attribution are intentional in the current design; broader deployment suitability is still an owner decision. |
| REQ-005 | The Order Desk's visual grouping is not durable order identity. | DOC-REPORTED / AUDIT-VERIFIED. The current data model has one `orders` row per recipient/bike line and no order-header identity. This is a constraint of the current model, not necessarily a desired future rule. |
| REQ-006 | The current Bike Distribution dashboard measures completed order-line/bike records by pickup date; it is not a deduplicated physical-bike count or grouped-request count. | DOC-REPORTED. Owner confirms reporting is low priority and the usual view is total bikes processed by year and shop; confirm exact date basis and unknown-shop treatment before changing the current calculation. |
| REQ-007 | The current pickup policy has a 7-day window for Public orders, a 28-day window for Pedal Partner orders, and no fixed Specialty deadline. | AUDIT-VERIFIED as implemented policy. Whether these exact values remain approved policy must be reconfirmed with the owner. |
| REQ-008 | Email delivery must remain guarded: preview is the default; live delivery requires explicit enablement, and reminders have a separate enable switch. | AUDIT-VERIFIED as a safety behavior in code. Whether the current approval gate, sender, recipients, and retention policy are sufficient is unresolved. |

### 2.1 Owner-confirmed requirements (2026-11-24)

These statements come directly from the project owner and supersede the corresponding open questions below:

| ID | Owner-confirmed rule | Specification interpretation |
|---|---|---|
| O-001 | Bulk ordering is an input convenience for an individual or Pedal Partner (an organization/group sponsoring recipients). | A bulk submission creates multiple independent bike requests. Each request is for one bike and is processed on its own timeline according to bike availability. Bulk submission must not imply one shared completion/pickup lifecycle. |
| O-002 | Staff have the same access; this is acceptable for the start. | Initial release uses one staff permission tier. This is an intentional launch decision, not an accidental absence of roles. Revisit only if operational needs change. |
| O-003 | Production is intended to run continuously on a Debian server. Tailscale is the remote-administration basis. Initial deployment is intended as a one-time setup, followed by remote updates and maintenance. The organization-site internet has not yet been tested against a standardized reliability threshold; if it cannot support staff and public-link access, home hosting is the alternative. The owner expects an agent to assist with deployment and to help select current, suitable server/proxy/service components at deployment time. | Tailscale is the selected remote-administration approach. Hosting location remains undecided pending a practical connectivity test; there is no agreed numeric reliability threshold. The exact production stack is intentionally not selected yet and should be researched and chosen with deployment assistance using supported, current options. “One-time deployment” does not remove the need for updates, maintenance, or recovery procedures. |
| O-004 | Reporting is low priority; the usual measure is total bikes processed by year and shop. Use pickup date as the year basis. Records without a shop default to Bentonville. | Retain the existing completed-order-line measure grouped by pickup year and shop. For reporting/migration, treat missing shop as Bentonville under this owner-confirmed rule; preserve source values/provenance so the default is distinguishable from an explicitly recorded Bentonville shop. |
| O-005 | The developer performs historical data migration; staff determine whether the migrated data is correct. Ambiguous historical data is not a UAT concern and will be addressed later. UAT is to establish whether the portal's operational workflows are acceptable to staff. When staff move to the portal, Google Sheets is abandoned as the record-keeping system. | UAT acceptance is primarily functional: staff can create orders, move them through stages, complete orders, and successfully use the other required portal flows. Do not make resolution of ambiguous or historical records a prerequisite for functional UAT. Treat historical-data review as a later workstream. Google Sheets is to be retired at the transition, not maintained as a parallel source of truth; define a final handoff/export and effective switch-over point. |
| O-006 | Include all available historical data if possible; at minimum, the most recent five years are more relevant. Older history should be retrievable on demand. Current data volume is small enough that all available data can be loaded on the main landing page. | Prefer importing and retaining all available history in the application. Do not create a separate archive or hide older records by default at current scale. Keep older data retrievable; introduce on-demand/archive retrieval only if volume or performance later justifies it. Preserve provenance and unresolved flags. |

### 2.2 Requirements that are not yet confirmed

The audit shows these behaviors exist, but does not prove they were explicitly approved as requirements: age validation of 1–80; phone-digit normalization; the precise New Order field set; the exact order transition rules; requester-link expiry duration; the 180-day remembered-volunteer cookie; volunteer profile field semantics; the precise meaning of each dashboard total; and the exact public form abuse controls. Treat them as **implemented behavior pending requirement confirmation**, not as silently approved policy.

## 3. Confirmed architectural decisions

The audit confirms the following intentional constraints or architectural behaviors. It does not include the original decision records, so the table distinguishes current implementation facts from proven approval.

| ID | Decision / constraint | Status of approval evidence |
|---|---|---|
| ADR-001 | Finished-bike inventory is optional and does not reserve or allocate bikes to orders. | Explicitly described by the audit as intentional; preserve unless owner changes it. |
| ADR-002 | Public volunteer identity selection is attribution only, not authentication. | Explicitly described by the audit as intentional; preserve unless owner changes it. |
| ADR-003 | Requester links use random secrets, store only a hash, expire, and are single-use. | Implemented behavior verified by audit; original approval record unavailable. |
| ADR-004 | Email supports preview, disabled, test-sink, and live modes; live mode is gated. | Implemented behavior verified by audit; production mail policy unverified. |
| ADR-005 | The application is currently a Flask/Jinja server-rendered application using SQLite. | Current architecture verified; evidence that this stack was formally approved or is a long-term constraint is absent. |
| ADR-006 | Workshop schema initialization is performed through a controlled maintenance CLI rather than implicitly enabling workshop pages on an unprepared database. | Current architecture verified; the split lifecycle with request-time order schema creation may be accidental technical debt rather than a deliberate target decision. |
| ADR-007 | Pickup reminders use an in-process APScheduler job at 15-minute intervals. | Current implementation verified; scheduler ownership and production process topology are explicitly unresolved. |

No source supplied here establishes that the present monolith, SQLite, in-process scheduler, or mixed schema lifecycle must be retained permanently. Those are current-state facts, not automatically binding future decisions.

## 4. Implemented functionality

“Implemented” means the audit found corresponding source code and, where stated, automated tests. It does not mean production operation or acceptance has been verified.

| ID | Capability | Current behavior found by audit | Verification / limitation |
|---|---|---|---|
| IMP-001 | Staff login | Password-hash verification, signed session containing username, login logging | Routes covered indirectly; no dedicated auth-hardening suite found. No role model. |
| IMP-002 | Order Desk | Responsive grouped cards, status tabs, pagination, search and type filters | Tested at route/template and workflow level. |
| IMP-003 | New Order | Multi-recipient input, validation, normalized phone digits, age 1–80, submission idempotency | Intake/workflow tests. Exact field and validation requirements need owner confirmation. |
| IMP-004 | Order transitions | Open → Contacted → Completed; Open/Contacted → Cancelled → Open; contact timestamp; pickup completion date and numeric tag | Workflow and policy tests. Each database row is a bike/order line, not a durable order header. |
| IMP-005 | Pickup policy | Deadline display, contact timestamps, reminder eligibility | Policy tests. Real scheduled execution is not verified. |
| IMP-006 | Email | Confirmation/pickup messages with preview, disabled, test, and live gates; SMTP STARTTLS | Email/workflow tests use mocks or disabled delivery. Real SMTP is not verified. |
| IMP-007 | Requester links | Staff-issued expiring one-use links; hashed secret; order creation once | Intake tests. Public URL reachability depends on deployment. |
| IMP-008 | Bike Distribution reporting | Completed-bike/order-line counts by pickup date, shop, and month | Seven dashboard regressions. This is the only identified report family. |
| IMP-009 | Finished-bike inventory | Staff inventory search/entry; public self-attributed contributions | Workshop/volunteer tests. Optional lookup only; no allocation or availability. |
| IMP-010 | Volunteer profiles | Staff can create/edit joined date and active status | Workshop tests. No deletion or distinct volunteer roles. |
| IMP-011 | Volunteer hours | Staff can correct/void; public forms are add-only and accept exact minutes | Workshop, volunteer, and impact tests. Public hours are self-reported. |
| IMP-012 | Volunteer impact | Year totals, distinct contributed bikes, weekly strip | Impact tests. Visibility of aggregate information after selecting a name is a product decision in project notes, but exact source decision unavailable. |
| IMP-013 | Controlled maintenance | Backup/audit CLI, additive initialization, legacy repair tools | Admin/migration/repair tests. Operator process and safe path selection need runbook coverage. |
| IMP-014 | Historical CSV rehearsal | Rehearses a legacy normalized July CSV migration | Tests exist; this is not the pending current Excel workbook importer. |

### 4.1 Test baseline

The audit ran the Python suite against temporary databases with outbound email disabled or mocked: **155 tests passed in 7.090 seconds**. Python syntax compilation and `git diff --check` passed. The Node test `tests/test_order_actions.cjs` was not run because Node.js was unavailable on the audit shell. Browser/device behavior, accessibility, live SMTP, actual scheduler operation, deployment networking, backups, and restore were not verified.

## 5. Partially implemented functionality

| ID | Capability | What exists | What remains incomplete or unverified |
|---|---|---|---|
| PART-001 | Pickup reminders | Policy, eligibility, 15-minute in-process job, delivery-claim/receipt tables | Production scheduler ownership, duplicate behavior under the real process topology, actual delivery, monitoring, and runbook. |
| PART-002 | Email operations | SMTP STARTTLS and safe modes | Real mailbox setup, sender identity, test recipient policy, preview retention, and approval gate are unverified. |
| PART-003 | Requester links | Route and token lifecycle | Public reachability, production hostname, HTTPS/proxy configuration, and QR distribution are not established. |
| PART-004 | Historical data migration | Legacy CSV rehearsal and migration idempotency | Current Excel cleanup/import, reconciliation, owner sign-off, production cutover, and rollback are pending. |
| PART-005 | Bike tag workflow | Inventory accepts broader text tags and canonical numeric aliases | Order completion accepts only positive whole-number tags and stores to a legacy `REAL` column. Cross-feature semantics do not align. |
| PART-006 | Database lifecycle | Some order/link/pickup tables are created at request time; workshop schema uses controlled CLI setup | No single versioned schema lifecycle, full startup readiness check, or verified active schema. |
| PART-007 | Reporting | Bike Distribution dashboard | Volunteer-hours and workshop-activity report families are documented as planned but not implemented. |
| PART-008 | Public volunteer access | Public identity search, self-attributed hours/contributions, signed remembered-name cookie | Whether this is acceptable for broader deployment, and whether abuse controls are adequate, remain owner decisions. |
| PART-009 | Production readiness | Local startup instructions and configurable SMTP/database paths | No verified production WSGI/process topology, deployment manifest, CI, health check, environment template, or operations runbook. |

## 6. Unimplemented requirements / missing capabilities

The following items are identified as planned, pending, or absent by the audit. Their inclusion in this list does not invent a priority or delivery date.

| ID | Item | Evidence / qualification |
|---|---|---|
| TODO-001 | Current historical Excel workbook importer and accepted data cutover | Explicitly pending; the CSV rehearsal is not the importer. Do not replace active data before an approved cutover. |
| TODO-002 | Volunteer-hours reporting | Mentioned in README / PROJECT_NOTES as planned; no route/template implementation found. Exact metrics and audiences unknown. |
| TODO-003 | Workshop-activity reporting | Mentioned in README / PROJECT_NOTES as planned; no route/template implementation found. Exact scope unknown. |
| TODO-004 | QR artwork generation and production-reachable public URLs | No artifact generator found; documented as waiting for production address. |
| TODO-005 | Production serving and deployment configuration | No WSGI server configuration, service definition, deployment manifest, or production startup command found. |
| TODO-006 | Operational runbook | No documented process for account provisioning/reset, backup/restore drills, access revocation, public-form misuse, scheduler operations, or incident response. |
| TODO-007 | CI/release workflow | No CI configuration or authoritative release/test procedure found. |
| TODO-008 | Environment template / configuration contract | No `.env.example` or equivalent production configuration reference found. |
| TODO-009 | Automated schema versioning / consistent migration lifecycle | No unified migration framework or startup readiness check found. |
| TODO-010 | Complete security hardening contract | Several controls are absent from tracked configuration; see Section 6. |

## 7. Known defects and technical debt

These are audit findings, not owner-approved scope changes. Severity and remediation order still need owner review.

| ID | Finding | Why it matters |
|---|---|---|
| DEBT-001 | `app.py` directly starts Flask with `debug=True` on port 5003. | Development entry point is not a production serving specification; debug must not be exposed. |
| DEBT-002 | Missing `SECRET_KEY` falls back to literal `loremipsum`. | Predictable session-signing secret; private secret should be mandatory in a production configuration. |
| DEBT-003 | All staff have effectively the same authorization level. | No role/permission model; any authenticated user can access staff functions. Workshop routes re-check username existence, while core order routes only check session username presence. |
| DEBT-004 | Login form has no application form token and no visible rate limiting/lockout. | Increases exposure to login CSRF and credential guessing. No password reset, disable, or MFA implementation was found. |
| DEBT-005 | Logout is a GET action. | State-changing action is not protected by POST/form-token semantics. |
| DEBT-006 | Schema lifecycle is split between request-time table creation and manual CLI initialization. | Makes schema state dependent on which route/operator ran; no single versioned upgrade contract. |
| DEBT-007 | Foreign-key enforcement differs by SQLite connection path. | Workshop/maintenance enable `PRAGMA foreign_keys=ON`; generic web connections do not. Enforcement is therefore not uniform. |
| DEBT-008 | Order browsing loads all joined rows into Python before filtering/grouping/pagination. | May degrade as historical records grow. |
| DEBT-009 | Order completion tag type differs from inventory tag semantics. | Numeric-only completion and legacy `REAL` storage conflict with broader text inventory tags and can create precision/format problems. |
| DEBT-010 | Scheduler starts during application import. | Multi-process or reloader deployment can start multiple scheduler instances; a single owner is not defined. |
| DEBT-011 | UI assets are CDN-loaded without consistent local pinning/integrity metadata. | Availability, reproducibility, supply-chain, and privacy posture depend on third parties; Chart.js is referenced without a version in the template. |
| DEBT-012 | Utility formatting functions use broad/bare exception suppression. | Unexpected defects can be hidden as formatting fallbacks. |
| DEBT-013 | No explicit global session-cookie security configuration, security headers/CSP, HTTPS/proxy configuration, or trusted-proxy policy was found. | Security boundary and reverse-proxy behavior are not defined. |
| DEBT-014 | Login logging trusts `X-Forwarded-For` when present. | Client-supplied forwarding headers can be misleading unless a trusted proxy boundary is configured. |
| DEBT-015 | No backup/restore drill evidence or production operations runbook. | Backups may exist as code paths, but recoverability and operator readiness are unverified. |
| DEBT-016 | Test and handoff documentation is stale. | Historical test totals vary from 94 to 143, while the current audit run passed 155; Git handoff describes an old branch state. |
| DEBT-017 | Active SQLite schema/data were not inspected. | Code tests do not prove the live database has the required schema, valid data, or a safe migration state. |
| DEBT-018 | Staged `.vscode/extensions.json` and untracked `definitions/` were not reconciled. | Ownership, purpose, and whether these belong in source control are unknown. |
| DEBT-019 | Ignored `scripts/users.py` creates a simplistic legacy user-table definition. | It is not a tracked supported management tool; use should not be assumed safe. |

## 8. Deferred features and explicitly non-authoritative historical work

| Item | Current interpretation | Handling rule |
|---|---|---|
| Historical Excel cleanup/cutover | Explicitly pending and separate from the old CSV rehearsal | Do not replace or rewrite the active database until the data source, reconciliation rules, backup, rehearsal, and sign-off are approved. |
| Volunteer-hours and workshop-activity reports | Planned, not implemented | Define metric, audience, filters, and privacy before implementation. |
| QR artwork / production URLs | Deferred until a stable production address exists | Do not generate final QR material against an assumed hostname. |
| Removed import/setup/Streamlit prototypes | Historical Git artifacts; current code treats them as non-authoritative | Do not reintroduce without a specific requirement and owner approval. |
| `scripts/users.py` | Ignored, untracked legacy utility | Do not treat as supported provisioning workflow. |
| Stale Git handoff notes | Superseded by current audited Git state | Archive or rewrite after owner chooses documentation authority. |

The audit does not provide a reliable record of every explicitly rejected approach. Removed prototypes are not automatically evidence that their underlying product ideas were formally rejected. The original history must be supplied to preserve those decisions accurately.

## 9. Unresolved questions requiring owner decisions

These are blockers to a final, approved specification. The audit's ten owner questions are retained and expanded only where the implementation creates a material ambiguity.

| ID | Question | Why it matters / default not assumed |
|---|---|---|
| Q-001 | Which production WSGI server, reverse proxy, service manager, and network exposure controls will be used? Is the organization-site internet sufficiently reliable for staff and public links, or should the server be hosted at the developer's home? | Test the shop connection in practice; no standardized reliability threshold exists yet. Select current supported components with deployment-agent assistance. |
| Q-002 | Which component owns the pickup-reminder scheduler so it runs exactly once? | Current scheduler starts at app import; multi-process/reloader behavior is unsafe to assume. |
| Q-003 | Must `SECRET_KEY` be mandatory at startup, and what is the session/mail-credential rotation and revocation plan? | Current source fallback is unsafe for production. |
| Q-004 | What are the staff account provisioning, password reset, disable/revocation, and audit procedures? | One common staff permission tier is confirmed for the initial release; account lifecycle remains open. |
| Q-005 | Is public name lookup and self-attribution acceptable without volunteer authentication? | Alternative PIN/QR/sign-in approaches must not be introduced or rejected without approval. |
| Q-006 | Should order completion continue to accept numeric-only tags, or support the wider finished-inventory tag format? How should duplicate/repeated tags behave? | **Resolved (2026-11-25):** Owner confirms Bike Tag is **numeric-only**; both `bike_inventory.bike_tag` and `orders.bike_tag` must share the same numeric data type so refurbished bikes in inventory can be matched by tag at order pickup (`TASK-401`). |
| Q-007 | No longer open: use pickup date for the year basis and default missing shop to Bentonville. | Owner-confirmed 2026-11-24. Preserve provenance for defaulted shop values; reporting remains low priority. |
| Q-008 | What are the UAT duration, detailed functional acceptance checklist, and go-live switch-over date? | UAT is for staff acceptance of portal workflows, not historical-data cleansing. Google Sheets will be abandoned when staff move to the portal; define the final export/handoff and switch-over procedure. Historical ambiguity review happens later. |
| Q-009 | Should order/link/pickup tables continue to be created at request time, or should all schema changes use explicit versioned maintenance migrations? | **Resolved (2026-11-25):** Owner confirms best-practice explicit versioned schema maintenance and startup readiness checks (`TASK-601`, `TASK-604`). |
| Q-010 | What SMTP sender, test-recipient policy, local preview retention, and approval gate are required before live mail/reminders? | Live mail was not verified. |
| Q-011 | Which project document becomes authoritative after this transition? Should stale handoff/history material be archived or rewritten? | Current documentation conflicts; a canonical source is needed. |
| Q-012 | Are there additional product goals or constraints from earlier discussions not captured in the supplied project documents? | Current source set is available; older discussion exports may still contain rationale not recorded in these files. |
| Q-013 | Which earlier approaches were explicitly rejected, and why? | Audit alone cannot distinguish formal rejection from abandoned experiments or superseded implementation. |
| Q-014 | Does bulk submission need a shared batch reference for audit/search, even though every bike request is independently processed? | Owner confirms each submitted bike is a separate request with its own availability-driven timeline. A shared batch ID is not currently required or approved; do not add an order-header lifecycle. |
| Q-015 | Are age limits 1–80 and phone-digit normalization still approved intake rules? | **Resolved (2026-11-25):** Owner confirms age 1–80 and phone normalization (plain 10-digit string stored in DB, formatted `(123) 456-7890` for web display only). |
| Q-016 | Are the 7-day Public / 28-day Pedal Partner pickup windows still correct, and what should Specialty behavior be? | **Resolved (2026-11-25):** Owner confirms 7-day Public and 28-day Pedal Partner pickup windows remain active (subject to future adjustment if needed). |
| Q-017 | Should the top-level New Order shortcut remain removed? | **Resolved (2026-11-25):** Owner confirms New Order remains under the `Orders` menu only. |
| Q-018 | Which layout is approved: “Desktop unchanged” or the later unified cards/two-column layout from 768px? | **Resolved (2026-11-25):** Owner confirms two-column layout on desktop/laptop/tablet (`>= 768px`) with independent order cards (`TASK-806`). |
| Q-019 | What is the desired visibility of volunteer impact aggregates after a person is selected? | The audit identifies this as a product decision but the underlying notes are unavailable. |
| Q-020 | Should CDN dependencies remain external, be pinned with integrity metadata, or be self-hosted? | **Resolved (2026-11-25):** Owner selects self-hosting vendor assets (`TASK-106`). |
| Q-021 | What are backup retention, recovery-point, recovery-time, and restore-test objectives? | Owner intends daily offsite backups of application data and the code repository. Retention, encryption, restore objectives, and restore-test cadence remain open. |
| Q-022 | What privacy/retention rules apply to requester data, volunteer records, hours, audit logs, email previews, and public-form submissions? | No complete retention policy was established by the audit. |

## 9.1 Owner-confirmed UAT and operations clarifications (2026-11-24 follow-up)

| ID | Clarification | Requirement / boundary |
|---|---|---|
| O-007 | UAT is to verify that staff find the portal functionality acceptable: order creation, stage transitions, order completion, and the other required flows. Historical-data ambiguity is explicitly out of scope for this UAT objective and will be handled later. | Define UAT scenarios around end-to-end workflow behavior, usability, and staff acceptance. Do not block functional UAT on historical-data cleansing or resolution of ambiguous records. |
| O-008 | Google Sheets is intended to be abandoned when staff move to the portal. | Plan a clear final handoff and switch-over point. Do not design ongoing parallel Google Sheets record keeping as the target operating model. |
| O-009 | Shop internet reliability has no standardized threshold yet; the owner will test whether the main shop can reliably host staff access and public links. | Hosting location remains a decision gate based on practical connectivity testing. If the shop connection is inadequate, developer-home hosting is the stated alternative. |
| O-010 | The owner plans daily offsite backups for application data and the code repository. | Architecture must specify backup automation, offsite destination, protection, retention, verification, and restore testing. Daily offsite backup is an owner-confirmed direction; the detailed policy is not yet approved. |
| O-011 | Production server/proxy/service choices are not selected. The owner expects an agent to assist with deployment and choose suitable current options. | Keep the stack decision open until deployment research and environment checks. Do not present a particular WSGI server, reverse proxy, or service manager as already chosen. |

## 10. Decisions that need reconsideration

These items are not silently changed here. They are candidates for an explicit owner decision because current implementation or documentation creates operational risk or semantic ambiguity.

1. **Production runtime and scheduler topology:** replace the development-server assumption with an approved production process model and a single scheduler owner.
2. **Secret handling:** remove the fallback secret from production use; define startup validation, rotation, and revocation.
3. **Authorization:** decide whether one staff permission level is a real requirement or merely the simplest initial implementation.
4. **Authentication and session protection:** decide login CSRF, rate limiting, account disable/reset, MFA, logout method, cookie flags, security headers, and trusted-proxy behavior.
5. **Schema lifecycle:** converge on one versioned migration and readiness process; remove request-time DDL only after compatibility and deployment sequencing are designed.
6. **SQLite integrity:** enable foreign-key enforcement consistently and assess missing legacy constraints without assuming the live database is safe to rewrite.
7. **Order identity and tag semantics:** decide whether a durable order header is needed and define tag type/uniqueness before altering schema or reporting.
8. **Reporting definitions:** explicitly define the measure represented by “bike,” “order,” “request,” and “completed.”
9. **Public volunteer attribution:** decide whether the current low-friction public model remains acceptable at the intended deployment scale.
10. **Email and background jobs:** define sender, recipients, retention, delivery approval, monitoring, retries, and single-owner scheduling.
11. **Data migration governance:** approve authoritative source workbook, reconciliation, dry-run, backup, sign-off, rollback, and cutover process.
12. **Documentation authority:** consolidate current requirements and decision records; archive stale notes without erasing historical rationale.
13. **External frontend assets:** decide whether to pin, integrity-protect, or self-host CDN assets.
14. **Performance boundary:** establish data-volume expectations and test whether in-memory order filtering remains adequate.

## 11. Acceptance and approval gates

This specification is not approved until the owner:

- confirms whether any additional historical discussions contain requirements or rejected approaches not captured in the supplied project documents;
- confirms the product constraints in Section 2;
- resolves the blocking decisions in Section 9 or explicitly defers them with an owner/date;
- approves or rejects the proposed architecture separately;
- confirms the traceability matrix and accepts its evidence limitations; and
- records the approved version and date.

No implementation change, schema migration, historical cutover, or production deployment is authorized by this draft. Owner-confirmed decisions in this revision do not themselves authorize cutover or launch.

## 12. Source register and limitations

| Source | Use | Limitation |
|---|---|---|
| `pif-technical-audit-2026-11-23.md` | Primary evidence for current code structure, tests, implementation status, known defects, documented conflicts, and open questions | Read-only audit; active database, `.env`, live SMTP, deployment, browser behavior, and private data were not inspected. |
| `README.md`, `PROJECT_NOTES.md`, `architecture.md`, `database.md`, `operations.md`, `order-workflow-review.md`, `dashboard-count-review.md`, `git-handoff.md`, `technical-audit.md` | Primary project context, recorded decisions, current behavior, data model, operating boundaries, historical staging rules | Supplied and reviewed; they still do not expose all original discussion rationale. |
| Original discussions / decision history | Needed to preserve initial intent and rejected approaches | Not available in current conversation sources. |

**Owner action requested:** review the updated owner-confirmed rules and resolve the remaining operational/data-cutover questions. If older discussion exports contain explicit rejected approaches or rationale not reflected in the supplied project documents, provide those before final approval.
