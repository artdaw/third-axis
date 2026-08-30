# Third Axis

**Provenance as the organising principle.**

Knowledge can be organised by *actionability* (PARA), by *association*
(Zettelkasten), or by **provenance** — what a claim was built from. Only the
third survives an author who cannot be held responsible.

That matters now because something other than you is writing into your notes.

```
vault_write  title="Adoption Gap"  sources=[]

REFUSED — rule 3: every compiled page carries provenance. 'sources' is empty.
A page without sources is a bug, not a draft.

In plain terms: I did not write that note. You asked me to record something
without saying where it came from. Tell me which of your saved sources it came
from and I will write it.
```

## Three parts

| | |
|---|---|
| **`vault-template/`** | The structure. Clone it and you have a working vault in a minute — Obsidian-compatible, because it is only markdown. |
| **`scriptorium/`** | The write path. An MCP server that refuses writes breaking the rules, with a hash-chained audit log. Any model, no network. |
| **`quiet/`** | The attention path. Reads your streams and says **one thing, or nothing.** Measures how often it stayed silent. |
| **`orchestrator/`** | A research spike, clearly labelled as one. Extracts orchestration training data from local agent history and reports the baseline you would have to beat. |

One ethic across all three: **a tool's most useful action is often to refuse.**

## Start

```bash
git clone <repo> third-axis && cd third-axis
cp -r vault-template ~/my-vault

python3 scriptorium/scriptorium.py --vault ~/my-vault --setup
claude mcp add scriptorium -- python3 "$PWD/scriptorium/scriptorium.py" --vault ~/my-vault

python3 quiet/quiet.py --streams
```

Standard library Python, no dependencies, nothing leaves the machine.

## What it enforces

Sources are immutable · cited sources must exist on disk · provenance is
required · nothing is silently overwritten, only appended or marked contested ·
human-owned pages are append-only · frontmatter and confidence are schema, not
convention.

Check the refusals fire, rather than believing the list:

```bash
python3 scriptorium/scriptorium.py --vault ~/my-vault --selftest    # 7/7
python3 quiet/quiet.py --selftest                                   # 8/8
```

## What it is not

**Not a note-taking app.** Use [zk](https://github.com/zk-org/zk) as the
notebook engine and [basalt](https://github.com/erikjuhani/basalt), `zk-nvim`
or Obsidian to read and edit. scriptorium uses zk's index when it is installed.

**Not a sandbox.** It refuses writes through its own tools. An agent with a
shell can write the file directly. It makes the disciplined path the easy one
and the undisciplined path visible — which is what a linter does.

**Not networked.** No telemetry, no account, no calls out.

## Status

Working, tested against a 162-page vault. Used by one person. Known gaps are
in each component's README and they stay there.

## License

AGPL-3.0. Running it locally is not offering it as a service — the network
clause guards a hosted tier, not your laptop.
