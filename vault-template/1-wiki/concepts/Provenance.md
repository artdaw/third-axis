---
type: concept
title: Provenance
owner: model
created: 2026-01-01
compiled: 2026-01-01
confidence: high
sources:
  - 0-raw/inbox/example-source.md
tags:
  - domain/method
---

# Provenance

Every page here names what it was built from. The `sources:` list is not
documentation — it is enforced. A page with an empty list is refused at write
time, and a page citing a file that is not on disk is refused too.

This is the load-bearing idea of the whole structure. Delete it and you have
an ordinary wiki, where a researched page and a guess look identical.

## Connections

- [[Confidence]] — how sure the page is, stated permanently
- [[Contested Example]] — what happens when two sources disagree
