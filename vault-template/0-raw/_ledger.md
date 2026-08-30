# Source index

One row per thing you saved. This is what makes a bad source removable: it
records which compiled pages each source touched.

The `source` column is an **identity, not a location** — it keeps the original
path even after a file is archived.

**Status:** `pending` → `compiled` | `unfetched` | `unfetchable` | `rejected` | `superseded`

| source | batch | added | status | compiled | pages produced |
|---|---|---|---|---|---|
| 0-raw/inbox/example-source.md | inbox | 2026-01-01 | compiled | 2026-01-01 | [[Provenance]], [[Confidence]] |
