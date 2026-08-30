# The ledger

One row per captured source. This is what makes a bad source removable: it
records which compiled pages each source touched.

```
| source | batch | added | status | compiled | pages produced |
|---|---|---|---|---|---|
```

**The `source` column is an identity, not a location.** It keeps the original
raw path even after the file is archived — the archived location goes in
`pages produced`. Rewriting it hides the row from every query that filters on
the raw prefix, which is the same failure as a file with no row at all: it
exists, but nothing will ever see it.

## Status values

`pending` → `compiled` | `unfetched` | `unfetchable` | `rejected` | `superseded`

- **pending** — captured, not yet compiled. The work queue.
- **compiled** — produced at least one page; `pages produced` says which.
- **unfetched** — a bare link whose body was never captured, or an unfilled
  template. **Not terminal** — it can be re-captured.
- **unfetchable** — a URL that was attempted and failed permanently (paywall,
  login wall, dead link). Record the HTTP status and the date, so retrying
  later is a decision rather than a guess.
- **rejected** — nothing to capture at all.
- **superseded** — folded into another page or replaced; point at what
  replaced it.

## Orphans

A file in the raw layer with no ledger row is invisible to every later step —
it will never be compiled and nothing will ever flag it, because the queue
only looks at rows that already exist. `vault_lint` reports orphans on every
run. Compare on Unicode **NFC**: macOS stores filenames as NFD, git emits NFC,
and the two look identical while comparing unequal.
