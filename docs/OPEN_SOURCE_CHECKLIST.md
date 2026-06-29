# Open Source Checklist

Use this before creating the public GitHub repository.

## Must Do Before Publishing

- Revoke and recreate any token that has ever appeared in `.env`.
- Confirm `.env` is not staged or committed.
- Confirm `data/radar.db` is not staged or committed.
- Confirm `data/exports/`, `data/raw/`, and `data/processed/` are not staged.
- Decide whether bundled frontend libraries under `lib/` should remain vendored
  or move to package-managed dependencies.
- Add a license before publishing.
- Add a short public-facing project description and scope disclaimer.

## Good To Do

- Add sample seed data small enough for demos.
- Add a tiny sample export generated from public demo data.
- Add screenshots for the dashboard and World Model graph.
- Add CI for tests.
- Pin dependency versions after the project stabilizes.

## Current Sensitive/Local Files

- `.env`: local-only secrets. Never publish.
- `data/radar.db`: local working database. It may contain cached public data,
  inferred relationships and local analysis state. Keep private unless you
  intentionally create a sanitized demo database.
- Parent workspace files such as `.claude/` and local Chinese notes are not part
  of the open-source repo.

