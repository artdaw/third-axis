# Compiler

Turn captured sources into compiled knowledge, and keep the vault healthy.

**Read `rules/compile.md` before touching any file.** Obey by number — when
you decide something, name the rule.

## Four phases, in order

Do not skip 2–4 because phase 1 found nothing. A run with zero pending
sources still checks health and still writes a summary.

### 1. Compile

**Step 0 — orphan check, before anything else.** Call `vault_lint`. A raw file
with no ledger row will never be compiled and nothing will ever flag it. Add a
row before proceeding; that row is what makes it visible to every future run.

Then, for each `pending` source from `vault_pending`:

- **Read the whole file**, not the frontmatter and first paragraph. A file
  that looks like a 95%-empty template can still hold one real section.
- **Classify.** Real body → extract. Bare link with a URL → fetch it, write
  the retrieved body as a *new* source beside the original (never into it —
  rule 1), mark the original `superseded`, and compile the fetched file. A
  fetch that returns a cookie banner, a JS shell or a paywall stub is a
  failure, not content.
- **Extract distinct concepts.** A source usually introduces more than one.
  Rule 8: one page and no links means you filed it, not compiled it.
- **Take the title from the source's own frontmatter**, never the filename —
  filenames carry migration cruft.
- **Write only what you just read.** If you cannot point at the line, do not
  write the claim.
- **Link both directions.** Two peer pages that reference each other link both
  ways. A hub linking down to members without the reverse link is fine.
- **Contradictions use `mode: contested`.** Both positions stay.
- **Update the ledger row**: status, compiled date, and every page produced.

### 2. Staleness

Pages whose sources no longer exist at their listed path, or whose `compiled`
date is older than a source's `added` date — meaning the source changed after
the page was last touched. Report; do not silently rewrite human-owned pages.

### 3. Duplicates

Near-identical titles, or overlapping `sources:` lists. Rule 9: merge into the
stronger page, archive the weaker, record the merge. Be careful — one book
feeding two distinct method pages is correct decomposition, not duplication.

### 4. Summary

Sources compiled, pages created and updated, contradictions flagged,
staleness and duplicate findings, and how many `pending` remain.

## The one thing to get right

Confidence is a claim about evidence, not about effort. `low` is a valid,
honest outcome and the tool will let you write it. Raising it because the page
looks thin is the failure this whole system exists to prevent.
