# PIF Portal operations checklist

Updated **2026-11-23**. This is a proposed operating checklist derived from the
source audit. It does not authorize deployment, data cutover, or live email.

## Before local development or testing

1. Read `PROJECT_NOTES.md` and confirm the intended database path.
2. Keep `.env`, `data/`, workbooks, backups, and email previews private and out of
   Git.
3. Use a disposable database for schema changes, migration rehearsals, and tests.
4. Force email to `disabled` or use mocked/test-sink delivery. Never send tests to
   requesters.
5. Run the Python suite from `.venv/bin/python`; run the Node check only where Node
   is installed.

## Before enabling workshop features on a database

1. Stop the app so no web process is writing to the target database.
2. Rehearse `scripts/admin_db.py ... init` against a disposable copy.
3. Review the preview, then use `--apply` with an existing audit actor and clear
   reason only after the backup is confirmed.
4. Verify the application recognizes the workshop schema before exposing public
   volunteer links.

## Before live email or reminders

1. Confirm the sender mailbox, SMTP settings, and the sole controlled test
   recipient outside version control.
2. Test with `EMAIL_MODE=test`; confirm messages reach only the test inbox.
3. Keep `EMAIL_LIVE_ENABLED=false` and reminders off until owner approval of
   content, sender, retention, and monitoring.
4. Enable live delivery and reminders separately. Remember that reminders depend
   on the app process being alive and on scheduler ownership being defined.

## Before a production deployment

The following decisions remain required:

- A production WSGI/server process instead of Flask debug mode.
- HTTPS and reverse-proxy behavior, including trusted forwarded headers.
- A required private `SECRET_KEY`, session-cookie policy, and access-revocation
  approach.
- Staff role/permission model, account provisioning, password reset, and audit
  ownership.
- One scheduler owner if more than one application process can run.
- Backup, restore, update, log-retention, and incident-response procedures.
- Public volunteer identity and privacy policy.

## Historical-data cutover

1. Preserve the source workbook and current database backup.
2. Review unresolved/ambiguous staging records with the project owner.
3. Rehearse import and reconciliation on a copy, preserving app edits and
   provenance.
4. Compare row counts, links, inventory foreign-key integrity, and report metrics.
5. Schedule one maintenance window, stop writers, back up the target, and obtain
   explicit sign-off before applying.

The source audit did not inspect active data. Refer to [database design](database.md)
and [current project notes](../PROJECT_NOTES.md) for the approved migration rules.
