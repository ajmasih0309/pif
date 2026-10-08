# Application branch handoff

Prepared 2026-10-08. Application changes are on `codex/database-cleanup`.
Spreadsheet preparation is on `codex/spreadsheet-cleanup` and is intentionally
excluded. No database cutover or data import is part of this handoff.

## Commit and push the application work

Run these in the application worktree, not the primary checkout. Confirm that
`git branch --show-current` prints `codex/database-cleanup`.

```sh
git branch --show-current
git status --short
git diff --check
git add -A
git diff --cached --stat
git commit -m "Add workshop workflows and refine order intake and reporting"
git push -u origin codex/database-cleanup
```

The commit includes the new application modules, templates, tests and design
documentation, as well as deletion of obsolete prototype importers and the old
Streamlit exploration script. Private databases, spreadsheets, screenshots,
email previews and `.env` stay ignored. No staged import files are included.

## Merge into main

Run these in the primary checkout, where `main` is already checked out. Start
with a clean working tree. Do not switch the application worktree to `main` while
the primary checkout owns that branch.

```sh
git status --short
git switch main
git pull --ff-only origin main
git merge --no-ff codex/database-cleanup -m "Merge workshop and order improvements"
git push origin main
```

If any command fails, stop before the next command and resolve the reported
issue. A rejected push is not a reason to force-push. If GitHub requires pull
requests, open one from `codex/database-cleanup` into `main`, merge it through
GitHub instead of the local merge/push above, then pull `main` locally.

## Sync another local clone

Inside that clone, with any local changes committed or otherwise preserved:

```sh
git switch main
git pull --ff-only origin main
```

The primary checkout used for the merge is already synchronized after a
successful push. Another clone may need its environment refreshed using
`python -m pip install -r requirements.txt`, with its own virtual environment
active. Restart a running app to load the updated Python code.

Git does not synchronize `.env`, the SQLite database or source spreadsheets.
The new Workshop pages require the additive maintenance schema through v5;
only the isolated preview database has been upgraded. Orders remain usable
without inventory or volunteer data. See the README and `design/database.md`
for the separate, backed-up schema initialization procedure when ready. Do not
run historical migration tools just to sync code. Keep email preview/disabled
settings while testing.

## Verification

- 141 Python tests pass using temporary databases and mocked mail delivery.
- 3 Node order-action tests pass.
- Intake and workshop JavaScript syntax checks pass.
- `git diff --check` passes.
- Remote `main` and the clean primary checkout were both `2fd083b` at handoff;
  the application branch changes were uncommitted. No push or merge was performed.
