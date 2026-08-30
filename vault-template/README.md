# vault-template

A working Third Axis vault. Clone it, point the tools at it, start writing.

```
CLAUDE.md         how an agent should work in this vault — read first
Dashboard.md      your entry point; the tools never read it

0-raw/            what you saved — immutable, never edited after capture
  _ledger.md      one row per source: status, and which pages it produced
  inbox/          new captures land here
  clips/ notes/ docs/ threads/

1-wiki/           what you worked out — every page cites its sources
  concepts/ entities/ topics/
  index.md              the map
  open-questions.md     what your sources disagree about

2-projects/       active, time-bound work; one folder each, own CLAUDE.md
3-output/         finished work, built from 1-wiki and never from 0-raw
  articles/ decks/ deliverables/ posts/
4-journal/        daily/ meetings/ briefs/ weekly/

_ctx/             the governing rules, agent definitions, templates
  rules/ agents/ templates/
_mem/             durable facts about you — profile, goals, people, state
_archive/         superseded content; nothing is deleted, it moves here
```

This mirrors a vault that has been in daily use for months, minus its owner's
content. `_mem/` ships as empty scaffolds by design — it is the one folder
that is only ever written by hand.

The example pages are not filler. Each one demonstrates a rule:

| Page | Shows |
|---|---|
| `Provenance.md` | `sources:` is enforced at write time, not a convention |
| `Confidence.md` | marked `low`, honestly, and permitted to stay that way |
| `Contested Example.md` | two sources disagreeing, both kept, neither deleted |
| `open-questions.md` | the register of what you disagree with yourself about |

Delete them once you have your own. Keep the shape.

## Start

```bash
git clone <this repo> my-vault && cd my-vault
python3 /path/to/third-axis/scriptorium/scriptorium.py --vault . --lint
```

It should say `no rule violations`. It is Obsidian-compatible as-is — open the
folder as a vault and everything renders, because it is only markdown.
