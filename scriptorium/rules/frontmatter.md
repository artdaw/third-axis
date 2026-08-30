# Frontmatter schema

## Compiled page

```yaml
---
type: concept | entity | topic
title: Matter Protocol
owner: model            # model = regenerable, human = append-only
created: 2026-08-23     # never changes
compiled: 2026-08-30    # the last run that touched this page
confidence: high | medium | low | contested
sources:                # NON-EMPTY. Vault-relative paths.
  - 0-raw/clips/2026-04-11-karpathy.md
tags:
  - domain/smart-building
---
```

Every field except `tags` is required. `scriptorium` refuses the write if one
is missing, if `confidence` is not in the list, or if `sources` is empty or
names a file that is not on disk.

## Raw source

```yaml
---
type: source
source-kind: clip | note | transcript | doc | thread
title: <original title>
added: 2026-08-23
origin: <url, or how it was captured>
---
```

## Naming

The filename **is** the link target, so the filename is the canonical title.
No `|` in any title or filename — the ledger is a markdown table parsed on
`|`, and one pipe corrupts every row after it.
