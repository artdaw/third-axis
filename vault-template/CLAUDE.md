# CLAUDE.md

This is a Third Axis vault: a source → wiki → output pipeline. There is no
build and no tests — every operation is a read or write on markdown files.

**Read `_ctx/rules/compile.md` before writing anything.** Cite rules by
number when you make a judgement call.

## Folder map

| Folder | Purpose |
|---|---|
| `0-raw/` | Captured sources. **Immutable.** Never edited after capture; state lives only in `0-raw/_ledger.md`. |
| `1-wiki/` | Compiled knowledge. **Every page needs non-empty `sources:`** — a page without it is a bug. |
| `2-projects/<slug>/` | Active, time-bound work. Each has its own `CLAUDE.md`. |
| `3-output/` | Finished deliverables, built from `1-wiki/` — never straight from `0-raw/`. |
| `4-journal/` | `daily/`, `meetings/`, `briefs/`, `weekly/`. |
| `_ctx/` | The governing rules, agent definitions and templates. |
| `_mem/` | Durable facts about you — profile, goals, people, state. Updated directly, not compiled. |
| `_archive/` | Superseded content. Nothing is deleted; it moves here. |

## The rules, short form

Full text in `_ctx/rules/compile.md`.

1. `0-raw/` is immutable — never edit a source, only its ledger row.
2. Never write to `1-wiki/` from memory — only from a source you are reading.
3. Every claim carries provenance — an empty `sources:` list is a bug.
4. Contradictions surface (both positions, `confidence: contested`) — never
   silently overwritten.
5. `owner: human` pages are append-only — add `## Compiler notes`, never
   rewrite the body.
6. `3-output/` is built from `1-wiki/`, never `0-raw/` directly.
7. Nothing is deleted — superseded content moves to `_archive/`.
8. A source should touch multiple pages, or it was filed, not compiled.
9. Reconcile near-duplicates — never leave two pages saying the same thing.

Rules 1–5 are enforced by scriptorium at write time. The rest are yours to
keep.

## Agents

| Say this | What runs |
|---|---|
| "save this" / "clip this" | **Scribe** — captures to `0-raw/inbox/` |
| "what do I know about…" | **Seeker** — searches `1-wiki/` first, `0-raw/` second |
| "compile my inbox" | **Compiler** — the source→wiki pipeline |

Definitions in `_ctx/agents/`.

## Checking it

```bash
python3 /path/to/scriptorium/scriptorium.py --vault . --lint
```

Reports frontmatter violations, missing provenance, sources that no longer
exist, and orphan files with no ledger row.
