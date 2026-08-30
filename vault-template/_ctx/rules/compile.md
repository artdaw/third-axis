# Compile rules

These govern every write into the compiled layer. Cite them by number — when
you make a judgement call you should be able to name the rule.

1. **Captured sources are immutable.** Never edit a file in the raw layer.
   Record state in the ledger instead. The capture is the record of what was
   actually seen; editing it destroys the only evidence.
2. **Never write from memory.** Only from a source you are reading right now.
   A URL you have fetched and read counts — the rule forbids recollection,
   not retrieval. What stays forbidden is writing what a page *probably* says
   because you recognise the author or the repo.
3. **Every claim carries provenance.** A compiled page with an empty
   `sources:` list is a bug, not a draft.
4. **Contradictions surface; they do not overwrite.** Append both positions,
   set `confidence: contested`, and log the conflict. The later source is not
   automatically the correct one.
5. **Human-owned pages are append-only.** Never rewrite the body of a page
   marked `owner: human`. Append a `## Compiler notes` section instead.
6. **Outputs are built from the compiled layer, never from raw directly.**
   Deliverables draw on processed understanding.
7. **Nothing is deleted.** Superseded content moves to an archive and the page
   that replaced it gets a pointer.
8. **A source should touch multiple pages.** If a source produced exactly one
   page and no links, it was filed, not compiled — redo it.
9. **Reconcile near-duplicates.** Never leave two pages saying the same thing.

## What compiling actually means

Reading a source and producing: one page per **distinct concept** it
introduces (not one page per source), updates to **existing** pages it
touches, links in **both directions**, and a ledger row recording every page
produced.

## Confidence

`high` · `medium` · `low` · `contested`

**Never raise a stated confidence past what the source supports.** A page
built from one passing reference that does not explain its subject is `low`,
and stays `low`. Rounding up to `medium` to make a page look finished is the
most common way a knowledge base starts lying to its owner.
