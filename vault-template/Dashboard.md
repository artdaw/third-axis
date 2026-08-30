---
type: dashboard
---

# Dashboard

The human entry point. Rename, rewrite, or delete it — the tools don't read
this file.

## Today

- **Pending sources** — what's captured but not yet compiled:
  `scriptorium --vault . ` then `vault_pending`, or read `0-raw/_ledger.md`
- **Latest brief** — `4-journal/briefs/`

## Knowledge

- [[1-wiki/index|Wiki index]] — the map of what you've worked out
- [[1-wiki/open-questions|Open questions]] — what your sources disagree about

## Active projects

One folder per project in `2-projects/`, each with its own `CLAUDE.md`
stating a single goal and what done looks like.

## Health

```bash
python3 /path/to/scriptorium/scriptorium.py --vault . --status
python3 /path/to/scriptorium/scriptorium.py --vault . --lint
```
