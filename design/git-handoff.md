# Git workflow and handoff

Updated **2026-11-23**. This document replaces the completed historical handoff
instructions that referred to an unmerged application branch.

## Current repository baseline

- Audited branch: `main`
- Audited revision: `00c864b389024ec8ed3b28df3d4d93a5c009a9ed`
- Remote relationship at audit time: `main` matched `origin/main`
- Historical worktrees may still exist. Their presence does not mean they contain
  unmerged work; inspect each branch before relying on it.

The audit observed a staged `.vscode/extensions.json` and an untracked
`definitions/` directory. They were not created or changed by the audit. Decide
whether they are intentional project artifacts before staging or committing them.

## Before making a change

```sh
git status --short
git branch --show-current
git fetch origin
git log --oneline --decorate -5
```

Read `PROJECT_NOTES.md` before implementation. Keep `.env`, SQLite databases,
workbooks, email previews, backups, and other private data out of Git.

## Feature branch workflow

Create a focused branch from current main. Use the `codex/` prefix unless a
different team convention is agreed.

```sh
git switch main
git pull --ff-only origin main
git switch -c codex/<focused-change>
```

Before commit, run the relevant safe checks and inspect the change:

```sh
git diff --check
PYTHONDONTWRITEBYTECODE=1 EMAIL_MODE=disabled EMAIL_LIVE_ENABLED=false \
EMAIL_REMINDERS_ENABLED=false .venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
git status --short
git diff --stat
```

The Node order-action test also belongs in validation where Node is available:

```sh
node --test tests/test_order_actions.cjs
```

## Commit and merge

Stage only intended files. In particular, do not use `git add -A` until ignored
private data and unrelated editor artifacts have been reviewed.

```sh
git add <intended-files>
git diff --cached --check
git diff --cached --stat
git commit -m "Describe the focused change"
git push -u origin codex/<focused-change>
```

Merge through the team’s approved review process. A rejected push or merge is not
a reason to force-push. After merging, synchronize a local clone with:

```sh
git switch main
git pull --ff-only origin main
```

## Database and configuration boundary

Git does not synchronize `.env`, SQLite databases, workbook inputs, backups, or
email preview files. A code merge does not authorize a database migration or
historical-data import. Follow [database maintenance](database.md) and the
[operations checklist](operations.md) separately.
