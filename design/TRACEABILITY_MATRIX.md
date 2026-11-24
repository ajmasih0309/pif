# PIF Portal — Requirements and Implementation Traceability Matrix

> Prepared: 2026-11-24 (owner clarifications incorporated)  
> **SPECIFICATION.md and ARCHITECTURE.md approved by owner — 2026-11-23**  
> Baseline: local `main` at `029a613` | `origin/main` at `00c864b` | Full code audit completed 2026-11-23

This matrix links requirement candidates and documented product constraints to current implementation evidence. It deliberately separates **requirement provenance** from **implementation status**. “Implemented” does not mean “approved,” and “not found” does not mean the feature was formally rejected.

## 1. Status legend

### Requirement provenance

- **Audit-backed constraint:** audit says tracked docs/code record an intentional product constraint.
- **Observed behavior:** code implements it, but the original approved requirement is not established.
- **Planned / DOC-REPORTED:** audit says project documentation describes it as planned or pending.
- **Owner decision:** no reliable requirement can be finalized without an owner answer.
- **Proposed quality requirement:** suggested for production readiness; not claimed as historical intent.

### Implementation status

- **Implemented:** source exists and automated evidence is reported.
- **Partial / operationally unverified:** some code exists, but production operation or full scope is not verified.
- **Not implemented:** audit found no corresponding application feature/configuration.
- **Unknown:** cannot be established from audit evidence.
- **Hold:** no implementation change until a product/data decision is made.

## 2. Functional traceability

| ID | Requirement / capability | Provenance | Current implementation | Evidence from audit | Gap / acceptance condition | Owner action |
|---|---|---|---|---|---|---|
| REQ-001 | Staff can authenticate to the portal. | Observed behavior; approval details unknown | Implemented | Werkzeug password-hash verification, signed session, login logging; routes covered indirectly | Define staff lifecycle, session protections, rate limits, and account disable/reset | Confirm desired auth and staff administration model |
| REQ-002 | Staff can browse and search the Order Desk. | Observed behavior | Implemented | Responsive cards, status tabs, pagination, search/type filters; route/template tests | Browser/device/accessibility testing not performed | Confirm current navigation/layout and filters |
| REQ-003 | Staff can submit a New Order with multiple recipients. | Observed behavior; business semantics unresolved | Implemented | Multi-recipient input, validation, normalized phone digits, age 1–80, idempotency; intake/workflow tests | Durable order identity is absent; age/phone rules not confirmed as approved | Decide parent request versus independent order lines; confirm validation rules |
| REQ-004 | Staff can transition order lines through Open, Contacted, Completed, and Cancelled states. | Observed behavior | Implemented | Workflow/policy tests; contact timestamp and pickup completion data | Need approved state machine, permissions, duplicate action behavior, and audit expectations | Confirm state transitions and reopen/cancel rules |
| REQ-005 | Contacting an order line starts pickup timing. | Observed behavior; exact policy DOC-REPORTED | Implemented | Separate contact timestamp and pickup policy tests | Reconfirm Public/Pedal Partner/Specialty timing | Confirm policy values and exceptions |
| REQ-006 | Eligible orders receive pickup reminders. | Observed behavior | Partial / operationally unverified | APScheduler 15-minute job; policy, eligibility, claim/receipt logic | Single scheduler owner, real SMTP, retries, monitoring, production behavior | Choose runtime and scheduler owner; approve reminder policy |
| REQ-007 | Confirmation and pickup notifications are sent through guarded email modes. | Audit-backed safety behavior | Partial / operationally unverified | SMTP STARTTLS; preview/disabled/test/live gates; tests mock or disable mail | Live mailbox, sender, recipient policy, preview retention, approval gate unverified | Approve mail operations policy |
| REQ-008 | Staff can issue requester links for public order submission. | Observed behavior | Partial / deployment-dependent | Random secret, hash stored, expiring one-use link; intake tests | Public reachability, hostname, HTTPS, QR distribution not verified | Confirm link lifetime and public deployment model |
| REQ-009 | The portal provides Bike Distribution reporting. | Observed behavior | Implemented | Completed order-line/bike counts by pickup date/shop/month; seven dashboard regressions | Metric is not deduplicated physical bikes or grouped requests | Choose authoritative reporting measure |
| REQ-010 | Finished Bike Inventory is optional and does not allocate bikes to orders. | Audit-backed constraint | Implemented | Staff inventory search/entry; public self-attributed contributions; tests | Do not add availability/allocation semantics without approval | Confirm optional inventory boundary |
| REQ-011 | Staff can create and edit volunteer profiles. | Observed behavior | Implemented | Joined date and active status; workshop tests | No deletion or role distinction; profile lifecycle/retention unknown | Confirm fields, deletion/deactivation policy |
| REQ-012 | Volunteers can submit their own hours through public forms. | Observed behavior; attribution-only boundary is documented | Implemented | Public add-only exact-minute entries; volunteer tests | Self-report integrity, abuse controls, corrections and privacy need definition | Confirm whether public no-login entry remains acceptable |
| REQ-013 | Staff can correct and void volunteer hour records. | Observed behavior | Implemented | Staff correction/void workflows and tests | Reason codes, audit retention, permissions not established | Confirm correction/void governance |
| REQ-014 | Volunteers can record finished-bike contributions. | Observed behavior; attribution-only boundary is documented | Implemented | Public self-attribution and staff workshop workflows; tests | Define tag validation and mistaken attribution recovery | Confirm public workflow and tag semantics |
| REQ-015 | Volunteer impact information is available. | Observed behavior; visibility is a recorded product decision but source unavailable | Implemented | Year totals, distinct contributed bikes, weekly strip; impact tests | Aggregate/person-level visibility rules need confirmation | Decide who can see which aggregates and when |
| REQ-016 | Controlled database maintenance is available to operators. | Observed behavior | Implemented | Backup/audit CLI, additive initialization, legacy repair scripts; tests | Active schema, backups/restores, operator permissions/runbook unverified | Approve operator workflow and maintenance ownership |
| REQ-017 | Current historical Excel data can be cleaned, imported, reconciled, and cut over. | Planned / DOC-REPORTED | Not implemented | No production workbook importer identified; older CSV rehearsal only | Define authoritative workbook, mapping, exception resolution, rehearsal, backup, sign-off, rollback | Name data owner and approve cutover acceptance contract |
| REQ-018 | Volunteer-hours reporting is available. | Planned / DOC-REPORTED | Not implemented | Described as planned in README / PROJECT_NOTES; no route/template found | Metric, filters, audience, privacy and date rules missing | Confirm scope and priority |
| REQ-019 | Workshop-activity reporting is available. | Planned / DOC-REPORTED | Not implemented | Described as planned; no route/template found | Define activity taxonomy, metrics, audience and filters | Confirm scope and priority |
| REQ-020 | Production QR artwork and phone-reachable public URLs are available. | Planned / DOC-REPORTED | Partial / not implemented as artifact | Routes provide reusable links; no QR generator found; depends on production address | Need stable public URL, HTTPS, QR generation and print/use acceptance | Confirm host and QR artifact requirements |

| REQ-021 | Bulk submission is an entry convenience for an individual or Pedal Partner sponsor; each submitted bike is a separate request, processed independently according to bike availability. | Owner-confirmed 2026-11-24 | Current data model creates one order row per recipient/bike; transitions are per line | Ensure no batch-level completion or shared fulfilment state; optional shared batch reference requires separate approval | Accept current per-line lifecycle; consider batch provenance only if needed |
| REQ-022 | Initial staff access uses one common permission tier. | Owner-confirmed 2026-11-24 | Current application has no role model and staff capabilities are effectively equal | Confirmed for initial release; account lifecycle/security controls remain gaps | Define provisioning, reset, disable and audit procedure |
| REQ-023 | Production runs 24/7 on Debian; remote administration uses Tailscale. Initial deployment is one-time, followed by remote maintenance. Host at organization site if internet supports staff/public-link access; otherwise consider developer home hosting. | Owner-confirmed 2026-11-24 | Current source only documents local Flask development entry point | Host location remains conditional on connectivity test; production server, reverse proxy, public reachability, monitoring, scheduler, backup and recovery are not implemented/verified | Validate connectivity and approve detailed deployment/operations design |
| REQ-024 | Reporting priority is low; usual measure is total bikes processed by year and shop. | Owner-confirmed 2026-11-24 | Bike Distribution report already counts completed order lines by pickup date and shop | Owner confirms pickup-date year basis and Bentonville default for missing shops; retain provenance; defer expanded reports | Keep current report; do not prioritize expansion now |
| REQ-025 | Developer executes historical migration. UAT determines whether staff accept portal functionality (order creation, stage transitions, completion, and other in-scope flows). Historical ambiguity is not a UAT concern and is addressed later. Google Sheets is abandoned when staff move to the portal. | Owner-confirmed 2026-11-24 follow-up | Workbook staging exists; no current-workbook production importer/cutover | Create end-to-end functional UAT scenarios; define final Sheets export/handoff and portal switch-over. Do not block UAT on historical-data cleansing. | Define UAT scenarios and switch-over date/process |
| REQ-026 | Include all available historical data if feasible; prioritize at least the most recent five years. | Owner-confirmed 2026-11-24 | Existing staging figures and rules are documented; no cutover performed | Preserve full history/provenance where possible; five years is relevance baseline, not permission to delete older data | Keep all available history in main app at current scale; preserve provenance and unresolved flags; on-demand/archive retrieval only if future scale requires it |

## 3. Non-functional and operational traceability

| ID | Quality / operational requirement candidate | Provenance | Current implementation / evidence | Gap / acceptance condition | Owner action |
|---|---|---|---|---|---|
| NFR-001 | Run under a production web server, not Flask debug server, on a 24/7 Debian host; location is conditional on connectivity testing. | Owner-confirmed; proposed quality requirement; audit defect | `app.py` runs `debug=True`, port 5003 | Test shop internet for staff/public-link reliability; if inadequate, evaluate developer-home hosting. Select current WSGI server, proxy and service manager with deployment-agent assistance; prove debug disabled. | Run connectivity test and approve deployment design |
| NFR-002 | Session signing secret is private and mandatory in production. | Proposed quality requirement; audit defect | Fallback `loremipsum` used if `SECRET_KEY` absent | Fail startup without secret; define rotation/revocation | Approve secret policy |
| NFR-003 | Initial staff access uses one common permission tier. | Owner-confirmed 2026-11-24 | All staff effectively same level; no role model | Same-access model is accepted for initial release; account provisioning/reset/disable still need definition | Define staff account lifecycle |
| NFR-004 | Login and state-changing actions are protected. | Proposed quality requirement; audit defect | Login lacks app form token and visible rate limit; logout is GET | Add CSRF protection, throttling, secure logout, account disable/reset | Approve auth hardening baseline |
| NFR-005 | Public forms resist abuse and protect privacy. | Partially implemented / owner decision | Restrictive cache/referrer/robots headers; signed remembered-name cookie | Define rate limits, abuse handling, data retention, identity assurance | Decide public access model and privacy policy |
| NFR-006 | Schema migrations are explicit, versioned, and repeatable. | Proposed architecture direction | Request-time schema creation for some tables; CLI setup for workshop | One migration path and readiness check; rehearsal on active schema copy | Approve migration lifecycle |
| NFR-007 | Referential integrity is enforced consistently. | Proposed quality requirement; audit defect | `foreign_keys=ON` in workshop/CLI but not generic web connection | Centralize connection creation and assess legacy constraints | Approve integrity remediation plan |
| NFR-008 | Reminder scheduling runs exactly once per environment. | Audit question / proposed quality requirement | Scheduler starts during app import | Single owner process, durable claim, duplicate-worker tests and monitoring | Choose scheduler owner |
| NFR-009 | Email sending is safe, auditable, and recoverable. | Existing guarded behavior plus owner decisions | Preview/disabled/test/live gates; live delivery not tested | Sender/recipient policy, retention, retries, approval, monitoring | Approve email policy |
| NFR-010 | Application data and code repository receive daily offsite backups. | Owner-confirmed 2026-11-24 follow-up; detailed policy proposed | Backup/audit CLI exists; no verified automated offsite backup | Implement and verify daily offsite backups; define destination, encryption/access, retention, SQLite consistency, RPO/RTO and restore drills | Approve detailed backup and recovery policy |
| NFR-011 | Dependencies and tests are reproducible. | Proposed quality requirement | `requirements.txt`; CI workflow (`.github/workflows/ci.yml`) established for Python suite, compilation, and Node order actions | Pin dependencies, CI, run Node test, document Python environment and safe mail flags | ✅ Implemented via GitHub Actions CI (TASK-105) |
| NFR-012 | UI dependencies have a controlled supply-chain/availability posture. | Owner decision / proposed quality requirement | CDN assets without consistent pinning/integrity metadata | Pin with integrity or self-host; validate offline/network constraints | Choose dependency strategy |
| NFR-013 | Reporting and browsing remain responsive at expected data volume. | Proposed quality requirement | All order rows loaded and filtered/grouped in Python | Establish data-volume target and performance test; optimize only if needed | Provide expected scale / retention |
| NFR-014 | Operational logs do not expose secrets or unnecessary personal data. | Existing positive control plus proposed quality requirement | Audit says mail failures avoid logging email bodies, recipients, credentials | Define broader log policy, retention, access, proxy trust and incident response | Approve logging/privacy policy |
| NFR-015 | Documentation identifies one authoritative source and release procedure. | Audit-identified gap | README, PROJECT_NOTES, handoff notes and test totals conflict | Canonical docs, decision log, release checklist, current test count | Choose documentation authority |

## 4. Product decision / contradiction register

| ID | Topic | Historical or documented conflict | Current implementation / audit finding | Required resolution |
|---|---|---|---|---|
| CON-001 | New Order navigation | PROJECT_NOTES has a later decision to remove the top-level shortcut and an older statement that it remains prominent at top level. | Current navigation places it under Orders only. | Confirm whether shortcut removal is the approved final decision. |
| CON-002 | Desktop layout | PROJECT_NOTES says “Desktop unchanged” in one place; later source/README describe unified cards with two columns from 768px. | Current code uses the later unified card layout. | Confirm desired layout; do not revert based on the older note alone. |
| CON-003 | Test totals | Documentation lists 94, 108, 116, 125, 132, 138, 139, 141, and 143 tests. | Audit run: 155 Python tests passed. | Update docs from a reproducible release command; do not use old counts. |
| CON-004 | Git handoff | `design/git-handoff.md` described an older uncommitted/unpushed state at `2fd083b`. | Audited `main` matches `origin/main` at `00c864b`. | ✅ Resolved: `design/git-handoff.md` marked archived with prominent notice referencing AGENTS.md (TASK-805). |
| CON-005 | Email setup | README says no provider-specific mailbox setup was performed. | Generic SMTP code exists; private environment intentionally not inspected. | Verify operational setup without exposing credentials. |
| CON-006 | Database design | Design documentation is not necessarily reflected in active database. | Active schema and data not inspected. | Inspect active schema before migration/deployment. |
| CON-007 | Order identity | Display grouping could be mistaken for durable order identity. | No order-header table; one row per recipient/bike line. | Decide whether parent request identity is needed. |
| CON-008 | Tag semantics | Inventory accepts broader text tags; order completion is numeric-only and writes to legacy `REAL`. | Two feature areas do not share one consistent tag contract. | Decide canonical tag format and migration strategy. |

| CON-009 | Bulk order semantics | Previously ambiguous whether multi-recipient submission is one order or many. | Owner confirms bulk is entry convenience; each bike request is independent and processed according to availability. | Preserve per-line lifecycle; any batch reference is provenance/display only and needs approval. |
| CON-010 | Production host | Previously unresolved whether local or hosted. | Owner confirms 24/7 Debian server, Tailscale remote administration; main-shop vs developer-home location depends on internet test. | Test connectivity; choose current WSGI/proxy/service stack with deployment-agent assistance; define monitoring, scheduler and recovery. |
| CON-011 | Reporting scope | Report metric and priority previously open. | Owner says low priority; count completed bike lines by pickup year/shop; missing shop defaults to Bentonville. | Preserve provenance for defaulted shop values; defer broader reports. |
| CON-012 | Historical migration and UAT scope | Previously unresolved. | Developer executes migration; staff determine historical data correctness later. UAT is functional workflow acceptance; Google Sheets is abandoned at portal transition. | Separate functional UAT from later historical-data review; define final Sheets handoff and portal switch-over. |

## 5. Explicitly rejected approaches and preservation record

The audit does **not** contain a complete rejected-approach register. The following must not be over-interpreted:

- Removed import/setup/Streamlit prototypes are described as historic and non-authoritative. That does not prove the underlying product approaches were formally rejected.
- `scripts/users.py` is ignored and untracked, and should not be treated as a supported tool. The audit does not establish whether it was explicitly rejected.
- The New Order top-level shortcut appears to have been removed by a later decision, but an older note conflicts. This is a decision conflict, not a clean rejection record.
- The intentional non-allocation inventory boundary and attribution-only volunteer identity boundary should be preserved unless the owner explicitly changes them.

Add original rejected approaches here after the project history is supplied. Do not infer them from absence of code.

## 6. Test and evidence coverage

| Evidence item | Audit result | Traceability implication |
|---|---|---|
| Python unit/integration suite | PASS — 155 tests, 7.090 seconds | Strong evidence for tested code paths, not for production operations or requirement approval. |
| Python syntax compilation | PASS | Syntax only. |
| `git diff --check` | PASS | Tracked-diff whitespace check only. |
| Node order-action test | NOT RUN — Node unavailable | JavaScript order-action behavior remains unverified by this audit. |
| Live SMTP | NOT RUN | Do not claim live email readiness. |
| Scheduler execution in production topology | NOT RUN | Do not claim exactly-once reminder operation. |
| Browser, device, accessibility | NOT RUN | Do not claim visual/accessibility acceptance. |
| Active database schema/data | NOT INSPECTED | Do not claim production schema readiness or cutover safety. |
| Backup/restore, networking, Tailscale, deployment host | NOT VERIFIED | Do not claim operational readiness. |

## 7. Approval workflow

1. Primary project documents have now been supplied and reviewed.
2. Incorporate owner-confirmed rules dated 2026-11-24 and preserve remaining unknowns.
3. Owner resolves or explicitly defers the remaining questions in `SPECIFICATION.md`.
4. Approve `SPECIFICATION.md` as the product contract.
5. Approve `ARCHITECTURE.md` independently as the technical design.
6. Convert approved rows into implementation tasks and acceptance tests.
7. Update this matrix with source references, code locations, tests, release evidence, and approval status.

Until those steps are complete, all three deliverables remain drafts.


## Owner-confirmed clarifications (2026-11-24, follow-ups)

| ID | Clarification | Traceability consequence |
|---|---|---|
| REQ-027 | Missing shop defaults to Bentonville. | Migration and reporting apply the default consistently while preserving original source value and provenance. |
| REQ-028 | Tailscale is the remote-administration basis. | Document Tailscale access, device authorization, and recovery if remote access is unavailable; do not claim configured until tested. |
| REQ-029 | Shop internet reliability has no standardized threshold; owner will test main-shop hosting. Developer-home hosting is the alternative if the connection is inadequate. | Host location remains undecided pending practical staff-access and public-link connectivity testing. |
| REQ-030 | UAT tests staff acceptance of portal functionality: order creation, stage transitions, completion, and other in-scope flows. Historical ambiguity is explicitly deferred until later. | Build functional end-to-end UAT scenarios. Do not make historical-data cleansing a UAT gate. |
| REQ-031 | Google Sheets will be abandoned when staff move to the portal. | Define final export/handoff and switch-over point; do not design ongoing parallel spreadsheet operations as the target model. |
| REQ-032 | Owner plans daily offsite backups for application data and the code repository. | Design automation, offsite destination, protection, retention, verification, and restore testing; detailed policy remains open. |
| REQ-033 | Production WSGI server, reverse proxy, and service manager are not yet selected; owner expects an agent to assist and choose current suitable options during deployment. | Keep the stack decision open until deployment research and host checks; do not represent a specific stack as approved. |
| REQ-034 | Owner intends to load all available historical data in the main application at current scale; older data remains retrievable, and a separate archive is not currently needed. | Preserve full history where feasible; defer archive/on-demand retrieval mechanisms unless scale or performance later requires them. |
