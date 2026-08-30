# _ctx

The governing context: rules, agent definitions, templates.

- **`rules/`** — the compile rules, frontmatter schema and ledger discipline.
  Rules 1–5 are enforced by scriptorium at write time; the rest are conventions
  you keep. Canonical copies live in `scriptorium/rules/` in the tooling repo.
- **`agents/`** — Compiler, Scribe and Seeker. What each is for, and the
  mistakes each one is prone to.
- **`templates/`** — note templates for your editor.

There is no `check-frontmatter.sh` here on purpose. `scriptorium --lint` does
everything such a script would, and more, without a second implementation to
keep in sync.
