# scriptorium

**Provenance enforcement for AI agents.**

An agent that cannot write what it did not read.

Plenty of MCP servers let an agent read and write your notes. This one
*refuses the write* when the claim has no source behind it.

```
vault_write  title="Adoption Gap"  sources=[]

REFUSED — rule 3: every compiled page carries provenance. 'sources' is empty.
A page without sources is a bug, not a draft — if you cannot point at what you
read, do not write the claim.

In plain terms: I did not write that note. You asked me to record something
without saying where it came from. Tell me which of your saved sources it came
from and I will write it.
```

Every refusal says it twice: once so a model knows exactly what to fix, once
so a person knows why they should be glad it stopped.

The interesting part of a knowledge system was never the editor. It is the
constraints: what an agent may write, what it must cite, and what it is not
allowed to quietly overwrite. Those live here as running code instead of as a
paragraph in a prompt that a model may or may not follow.

Standard library only. No install step, no dependencies, Python 3.8+.

## What it enforces

| | |
|---|---|
| **Rule 1** | Captured sources are immutable. Any write under the raw layer is refused. |
| **Rule 2** | Sources listed on a page must exist on disk. You cannot cite what you did not read. |
| **Rule 3** | Provenance is required. An empty `sources:` list is refused. |
| **Rule 4** | Nothing is silently overwritten. An existing page takes `append` or `contested` — and `contested` sets the confidence itself. |
| **Rule 5** | `owner: human` pages are append-only. Only a `## Compiler notes` append is allowed. |
| **Schema** | Every required frontmatter field present; `confidence` from a fixed set. |
| **Naming** | No `|` in a title — the ledger is a markdown table parsed on `|`. |
| **Orphans** | A raw file with no ledger row is reported. It would otherwise never be compiled and nothing would ever flag it. |

Run the refusals yourself:

```bash
python3 scriptorium.py --vault /path/to/vault --selftest
```

## Quick start

```bash
git clone <this repo> && cd scriptorium

# Point it at your notes. It works out the layout and writes the config,
# then prints the exact command to paste next.
python3 scriptorium.py --vault ~/notes --setup
```

`--setup` reads your folder rather than making you describe it. It recognises
`0-raw`/`raw`/`sources`/`Clippings`, `1-wiki`/`notes`/`Notes`/`zettel`, and so
on, and adapts to whatever it finds — tested against an Obsidian vault called
`Clippings/ Notes/ Drafts/` with no hand-editing.

Starting from nothing:

```bash
python3 scriptorium.py --vault ~/notes --init    # creates the folders, then sets up
```

Then:

```bash
python3 scriptorium.py --vault ~/notes --status   # is it seeing everything?
python3 scriptorium.py --vault ~/notes --lint     # what is broken?
./install.sh ~/notes                              # copy in the rules (never overwrites)
```

Any MCP client works — it speaks plain JSON-RPC over stdio. For a client that
takes a config block:

```json
{
  "mcpServers": {
    "scriptorium": {
      "command": "python3",
      "args": ["/abs/path/to/scriptorium.py", "--vault", "/abs/path/to/vault"]
    }
  }
}
```

## Tools

| Tool | What it does |
|---|---|
| `vault_status` | Counts, ledger breakdown, orphans, lint errors. Call it first. |
| `vault_search` | Compiled pages first, raw sources second — compiled understanding outranks raw capture. |
| `vault_read` | Read one file by vault-relative path. |
| `vault_pending` | The work queue: sources captured but not yet compiled. |
| `vault_capture` | Add a source and register it. The only sanctioned way in. |
| `vault_write` | Create or update a compiled page — **enforced**. |
| `vault_lint` | Every rule, across the whole vault. |

## Layout

It assumes a three-layer vault and a ledger:

```
0-raw/          captured sources — immutable
  _ledger.md    one row per source: status, and which pages it produced
  inbox/        where captures land
1-wiki/         compiled knowledge — provenance required
  concepts/ entities/ topics/
3-output/       finished work, built from the compiled layer
```

Different layout? Drop a `.scriptorium.json` in the vault root — see
`.scriptorium.example.json`. Field names, the confidence vocabulary and the
required-field list are all configurable. The *rules* are not, which is the
point.

## What it is not

- **Not a note-taking app.** Use [zk](https://github.com/zk-org/zk) as the
  notebook engine, [basalt](https://github.com/erikjuhani/basalt) or
  `zk-nvim` to read and edit. Both are better than anything worth writing
  from scratch.
- **Not tied to one model.** It is an MCP server over local files. Point any
  MCP-speaking client at it — Claude Code, or a local model through an
  OpenAI-compatible bridge.
- **Not networked.** No telemetry, no cloud, no account. It reads and writes
  files in one directory and refuses to touch anything outside it.

## Why the refusal is the product

A prompt that says "always cite your sources" is a suggestion. A tool call
that returns `REFUSED — rule 3` with the reason is a constraint. The second
one survives context compaction, model swaps, and a long session at 2am.

## License

**AGPL-3.0.** Free to run, read, modify and share. If you offer scriptorium to
others as a network service, you publish your changes.

Worth being precise, because AGPL scares people off for the wrong reasons:
running it locally as an MCP server is **not** offering it as a service. The
network clause exists so that a hosted "provenance-as-a-service" has to stay
open, not to catch you using it on your laptop or your home server.

## Status

`0.1.0` — working, tested against a 159-page vault. The enforcement is real;
the ergonomics are early.

Known gaps: no full-text index (linear scan, fine to a few thousand notes);
`vault_write` does not yet auto-update the ledger's `pages produced` column;
staleness and duplicate detection are reported by `vault_lint` but not fixed
automatically.
