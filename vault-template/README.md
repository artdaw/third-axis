# vault-template

A working Third Axis vault. Clone it, point the tools at it, start writing.

```
0-raw/          what you saved — immutable, never edited after capture
  _ledger.md    one row per source: status, and which pages it produced
  inbox/        where new captures land
1-wiki/         what you worked out — every page cites its sources
  concepts/ entities/ topics/
  open-questions.md   what your sources disagree about
3-output/       finished work, built from 1-wiki and never from 0-raw
```

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
