#!/usr/bin/env python3
"""
scriptorium — provenance enforcement for AI agents.

An MCP server that makes a markdown vault's rules executable. Most vault MCP
servers let an agent read and write notes. This one refuses writes that break
the rules: sources are immutable, every compiled page carries provenance,
human-owned pages are append-only, and nothing is silently overwritten.

Copyright (C) 2026 Gleb Galkin
Licensed under the GNU Affero General Public License v3.0 or later.
See LICENSE, or <https://www.gnu.org/licenses/agpl-3.0.txt>.

Standard library only. No install step. Python 3.8+.

    python3 scriptorium.py --vault /path/to/vault      # run as an MCP server
    python3 scriptorium.py --vault . --lint            # run the checks directly
    python3 scriptorium.py --vault . --selftest        # verify enforcement works
"""

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata

VERSION = "0.1.0"
PROTOCOL = "2024-11-05"

DEFAULTS = {
    "raw": "0-raw",
    "wiki": "1-wiki",
    "output": "3-output",
    "inbox": "0-raw/inbox",
    "ledger": "0-raw/_ledger.md",
    "wiki_dirs": ["concepts", "entities", "topics"],
    "kinds": {"concept": "concepts", "entity": "entities", "topic": "topics"},
    "confidence": ["high", "medium", "low", "contested"],
    "required": ["type", "title", "owner", "created", "compiled", "confidence", "sources"],
}


# --------------------------------------------------------------------------
# vault
# --------------------------------------------------------------------------

class RuleError(Exception):
    """A write was refused because it breaks a vault rule.

    `plain` is the same refusal said without jargon. Both are shown: the rule
    line tells a model exactly what to fix, the plain line tells a person why
    they should be glad it stopped.
    """

    def __init__(self, message, plain=None):
        super().__init__(message)
        self.plain = plain


class Vault:
    def __init__(self, root):
        self.root = os.path.abspath(root)
        if not os.path.isdir(self.root):
            raise SystemExit("no such vault: %s" % self.root)
        self.cfg = dict(DEFAULTS)
        path = os.path.join(self.root, ".scriptorium.json")
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as fh:
                self.cfg.update(json.load(fh))

    # -- paths ------------------------------------------------------------

    def abs(self, rel):
        p = os.path.abspath(os.path.join(self.root, rel))
        if p != self.root and not p.startswith(self.root + os.sep):
            raise RuleError("path escapes the vault: %s" % rel)
        return p

    def rel(self, path):
        return os.path.relpath(os.path.abspath(path), self.root)

    def in_raw(self, rel):
        r = rel.replace(os.sep, "/")
        return r == self.cfg["raw"] or r.startswith(self.cfg["raw"] + "/")

    def wiki_files(self):
        out = []
        for sub in self.cfg["wiki_dirs"]:
            d = os.path.join(self.root, self.cfg["wiki"], sub)
            if not os.path.isdir(d):
                continue
            for name in sorted(os.listdir(d)):
                if name.endswith(".md"):
                    out.append(os.path.join(d, name))
        return out

    def raw_files(self):
        out = []
        base = os.path.join(self.root, self.cfg["raw"])
        ledger = os.path.basename(self.cfg["ledger"])
        for dirpath, _dirs, names in os.walk(base):
            for name in sorted(names):
                if name.endswith(".md") and name != ledger:
                    out.append(os.path.join(dirpath, name))
        return out

    # -- ledger -----------------------------------------------------------

    def ledger_path(self):
        return os.path.join(self.root, self.cfg["ledger"])

    def ledger_rows(self):
        """Return [{source, batch, added, status, compiled, pages, lineno}]."""
        path = self.ledger_path()
        if not os.path.isfile(path):
            return []
        rows = []
        with open(path, encoding="utf-8") as fh:
            for i, line in enumerate(fh, 1):
                parts = line.split("|")
                if len(parts) < 7:
                    continue
                src = parts[1].strip()
                if not src.startswith(self.cfg["raw"] + "/"):
                    continue
                rows.append({
                    "source": src, "batch": parts[2].strip(),
                    "added": parts[3].strip(), "status": parts[4].strip(),
                    "compiled": parts[5].strip(), "pages": parts[6].strip(),
                    "lineno": i,
                })
        return rows

    def ledger_append(self, source, batch, added, status="pending"):
        path = self.ledger_path()
        row = "| %s | %s | %s | %s |  |  |\n" % (source, batch, added, status)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(row)
        return row.strip()


# --------------------------------------------------------------------------
# frontmatter
# --------------------------------------------------------------------------

FM_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def split_front(text):
    m = FM_RE.match(text)
    if not m:
        return None, text
    return m.group(1), text[m.end():]


def parse_front(block):
    """Minimal YAML: scalars and '  - ' lists. Enough for vault frontmatter."""
    data, key = {}, None
    if block is None:
        return data
    for line in block.split("\n"):
        if not line.strip():
            continue
        if line.startswith("  - ") or line.startswith("- "):
            if key:
                data.setdefault(key, [])
                if isinstance(data[key], list):
                    data[key].append(line.split("- ", 1)[1].strip().strip('"\''))
            continue
        if ":" in line and not line.startswith(" "):
            key, _, val = line.partition(":")
            key, val = key.strip(), val.strip()
            data[key] = val.strip('"\'') if val else []
    return data


def dump_front(d):
    out = []
    for k, v in d.items():
        if isinstance(v, list):
            out.append("%s:" % k)
            for item in v:
                out.append('  - "%s"' % item if needs_quote(item) else "  - %s" % item)
        else:
            out.append("%s: %s" % (k, v))
    return "---\n" + "\n".join(out) + "\n---\n"


def needs_quote(s):
    return bool(re.search(r"[:#\[\]{}]|^[\s]|[\s]$", str(s)))


def nfc(s):
    return unicodedata.normalize("NFC", s)


def today():
    return dt.date.today().isoformat()


# --------------------------------------------------------------------------
# the rules — enforcement lives here
# --------------------------------------------------------------------------

def check_write(vault, rel_path, front, mode, existing_text):
    """Raise RuleError if this write breaks a rule. Rules cited by number."""

    # Rule 1 — sources are immutable.
    if vault.in_raw(rel_path):
        raise RuleError(
            "rule 1: %s is under %s/, which is immutable. Captured sources are "
            "never edited. Record state in the ledger instead, or write a new "
            "file beside it." % (rel_path, vault.cfg["raw"]),
            plain='That folder holds the things you saved, exactly as you saved them. Nothing is allowed to change them afterwards — that is the only reason you can trust them later.'
        )

    title = front.get("title", "")

    # Naming — a pipe breaks the ledger table, which is parsed on '|'.
    if "|" in str(title) or "|" in rel_path:
        raise RuleError(
            "naming: '|' is not allowed in a title or filename — the ledger is "
            "a markdown table parsed on '|' and one pipe corrupts every row after it.",
            plain='The character | breaks the index that tracks all your sources. Please pick a title without it.'
        )

    # Rule 3 — provenance is not optional.
    srcs = front.get("sources") or []
    if not isinstance(srcs, list) or not srcs:
        raise RuleError(
            "rule 3: every compiled page carries provenance. 'sources' is empty. "
            "A page without sources is a bug, not a draft — if you cannot point "
            "at what you read, do not write the claim.",
            plain='I did not write that note. You asked me to record something without saying where it came from. Tell me which of your saved sources it came from and I will write it.'
        )
    missing = []
    for s in srcs:
        if s.startswith(vault.cfg["raw"] + "/") and not os.path.exists(vault.abs(s)):
            missing.append(s)
    if missing:
        raise RuleError(
            "rule 2: these sources do not exist on disk, so they were not read:\n  "
            + "\n  ".join(missing)
            + "\nWrite only from a source you are actually reading.",
            plain='The source I was told to credit is not in your vault, which means nobody read it. A citation that points at nothing is worse than no citation.'
        )

    # Frontmatter completeness.
    absent = [k for k in vault.cfg["required"] if k not in front]
    if absent:
        raise RuleError("frontmatter: missing required field(s): %s" % ", ".join(absent))
    conf = front.get("confidence")
    if conf not in vault.cfg["confidence"]:
        raise RuleError(
            "frontmatter: confidence must be one of %s (got %r). "
            "'low' is a valid, honest outcome — never raise a stated confidence "
            "past what the source supports."
            % ("/".join(vault.cfg["confidence"]), conf)
        )

    if existing_text is None:
        return

    old_front = parse_front(split_front(existing_text)[0])

    # Rule 5 — human-owned pages are append-only.
    if old_front.get("owner") == "human" and mode != "compiler-note":
        raise RuleError(
            "rule 5: %s is owner: human and append-only. Never rewrite the body. "
            "Use mode='compiler-note' to append a '## Compiler notes' section instead."
            % rel_path,
            plain='You wrote that page yourself, so I am not allowed to rewrite it. I can add a note at the bottom, and you decide what to do with it.'
        )

    # Rule 4 — contradictions surface; they do not overwrite.
    if mode == "replace":
        raise RuleError(
            "rule 4: refusing to overwrite an existing page. If the new source "
            "agrees, use mode='append'. If it disagrees, use mode='contested' — "
            "both positions are kept, confidence becomes 'contested', and the "
            "conflict is logged. Nothing is silently overwritten.",
            plain='That page already says something. I will add to it, or record that your two sources disagree — but I will not quietly replace what is there. You would never know it happened.'
        )


def lint(vault):
    """Return (findings, counts). A finding is (severity, rule, path, message)."""
    findings = []
    wiki = vault.wiki_files()

    for path in wiki:
        rel = vault.rel(path)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        block, _body = split_front(text)
        if block is None:
            findings.append(("error", "frontmatter", rel, "no frontmatter block"))
            continue
        front = parse_front(block)
        for key in vault.cfg["required"]:
            if key not in front:
                findings.append(("error", "frontmatter", rel, "missing '%s'" % key))
        if front.get("owner") not in ("model", "human"):
            findings.append(("error", "frontmatter", rel,
                             "owner must be model or human, got %r" % front.get("owner")))
        if front.get("confidence") not in vault.cfg["confidence"]:
            findings.append(("error", "frontmatter", rel,
                             "confidence %r not allowed" % front.get("confidence")))
        srcs = front.get("sources") or []
        if not srcs:
            findings.append(("error", "rule 3", rel, "empty sources — provenance missing"))
        for s in srcs:
            if s.startswith(vault.cfg["raw"] + "/") and not os.path.exists(vault.abs(s)):
                findings.append(("warn", "rule 2", rel, "source not on disk: %s" % s))
        if "|" in str(front.get("title", "")):
            findings.append(("error", "naming", rel, "'|' in title breaks the ledger"))

    # Orphans — a raw file with no ledger row is invisible to every later step.
    rows = vault.ledger_rows()
    listed = set(nfc(r["source"]) for r in rows)
    on_disk = set(nfc(vault.rel(p)).replace(os.sep, "/") for p in vault.raw_files())
    for orphan in sorted(on_disk - listed):
        findings.append(("warn", "orphan", orphan, "no ledger row — will never be compiled"))

    counts = {
        "wiki_pages": len(wiki),
        "raw_files": len(on_disk),
        "ledger_rows": len(rows),
        "pending": sum(1 for r in rows if r["status"] == "pending"),
        "orphans": len(on_disk - listed),
        "errors": sum(1 for f in findings if f[0] == "error"),
        "warnings": sum(1 for f in findings if f[0] == "warn"),
    }
    return findings, counts


# --------------------------------------------------------------------------
# operations behind the tools
# --------------------------------------------------------------------------

def op_status(vault, _a):
    _f, c = lint(vault)
    rows = vault.ledger_rows()
    by_status = {}
    for r in rows:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    lines = [
        "vault: %s" % vault.root,
        "wiki pages: %d   raw sources: %d   ledger rows: %d"
        % (c["wiki_pages"], c["raw_files"], c["ledger_rows"]),
        "ledger status: " + (", ".join("%s %d" % (k, v) for k, v in sorted(by_status.items())) or "—"),
        "orphans: %d   lint errors: %d   warnings: %d"
        % (c["orphans"], c["errors"], c["warnings"]),
        "search index: %s" % ("zk" if zk_available(vault)
                              else "linear scan  (install zk for a real index)"),
    ]
    return "\n".join(lines)


def zk_available(vault):
    """zk is the index. We do not rebuild what it already does well."""
    if not shutil.which("zk"):
        return False
    return os.path.isdir(os.path.join(vault.root, ".zk"))


def zk_search(vault, query, limit):
    """Ask zk. Returns [(score, label, rel, line)] or None if it could not help."""
    try:
        r = subprocess.run(
            ["zk", "list", "--quiet", "--no-pager", "--match", query,
             "--limit", str(limit), "--format", "{{path}}\t{{title}}"],
            cwd=vault.root, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=15)
    except Exception:
        return None
    if r.returncode != 0:
        return None
    hits = []
    for line in r.stdout.decode("utf-8", "replace").split("\n"):
        line = line.strip()
        if not line:
            continue
        path, _, title = line.partition("\t")
        rel = path if not os.path.isabs(path) else vault.rel(path)
        label = "wiki" if rel.startswith(vault.cfg["wiki"]) else "raw"
        hits.append((50, label, rel, title.strip()))
    return hits


def op_search(vault, a):
    q = (a.get("query") or "").strip()
    if not q:
        raise RuleError("search needs a query")
    scope = a.get("scope", "all")
    limit = int(a.get("limit", 20))
    rx = re.compile(re.escape(q), re.I)

    def scan(paths, label):
        hits = []
        for p in paths:
            try:
                with open(p, encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
            except OSError:
                continue
            rel = vault.rel(p)
            score = len(rx.findall(text))
            if rx.search(os.path.basename(p)):
                score += 10
            if score:
                line = ""
                for ln in text.split("\n"):
                    if rx.search(ln):
                        line = ln.strip()[:160]
                        break
                hits.append((score, label, rel, line))
        return hits

    hits = []
    engine = "grep"
    if zk_available(vault):
        zh = zk_search(vault, q, limit * 2)
        if zh is not None:
            engine = "zk"
            # Keep our ordering rule even on zk results: compiled first.
            hits = [h for h in zh if h[1] == "wiki"] + [h for h in zh if h[1] != "wiki"]
            if hits:
                out = ["%d match(es) for %r via zk index — wiki first:" % (len(hits), q), ""]
                for _score, label, rel, line in hits[:limit]:
                    out.append("[%s] %s" % (label, rel))
                    if line:
                        out.append("      %s" % line)
                return "\n".join(out)

    # Wiki first — compiled understanding outranks raw capture.
    if scope in ("all", "wiki"):
        hits += scan(vault.wiki_files(), "wiki")
    if scope in ("all", "raw") and (scope == "raw" or len(hits) < limit):
        hits += scan(vault.raw_files(), "raw")
    hits.sort(key=lambda h: (-h[0], h[2]))
    if not hits:
        return "no matches for %r" % q
    out = ["%d match(es) for %r — wiki first:" % (len(hits), q), ""]
    for score, label, rel, line in hits[:limit]:
        out.append("[%s] %s  (%d)" % (label, rel, score))
        if line:
            out.append("      %s" % line)
    return "\n".join(out)


def op_read(vault, a):
    rel = a.get("path") or ""
    p = vault.abs(rel)
    if not os.path.isfile(p):
        raise RuleError("not found: %s" % rel)
    with open(p, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def op_pending(vault, _a):
    rows = [r for r in vault.ledger_rows() if r["status"] == "pending"]
    if not rows:
        return "no pending sources — the ledger is clean."
    out = ["%d pending source(s):" % len(rows), ""]
    for r in rows:
        out.append("  %s   (added %s, batch %s)" % (r["source"], r["added"], r["batch"]))
    return "\n".join(out)


def op_capture(vault, a):
    """Write a new raw source and register it. The only sanctioned way in."""
    title = (a.get("title") or "").strip()
    body = a.get("body") or ""
    origin = (a.get("origin") or "").strip()
    if not title:
        raise RuleError("capture needs a title")
    if "|" in title:
        raise RuleError("naming: '|' in a title breaks the ledger table")

    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60] or "untitled"
    name = "%s-%s.md" % (today(), slug)
    rel = "%s/%s" % (vault.cfg["inbox"].rstrip("/"), name)
    p = vault.abs(rel)
    if os.path.exists(p):
        raise RuleError("already exists: %s" % rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)

    front = {
        "type": "source",
        "source-kind": a.get("kind", "note"),
        "title": title,
        "added": today(),
        "origin": origin or "scriptorium-capture",
    }
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(dump_front(front) + "\n" + body.rstrip() + "\n")
    row = vault.ledger_append(rel, a.get("batch", "inbox"), today())
    return "captured %s\nledger row added (status: pending):\n%s" % (rel, row)


def op_write(vault, a):
    """Create or update a compiled page. Every rule is checked before writing."""
    title = (a.get("title") or "").strip()
    kind = a.get("kind", "concept")
    mode = a.get("mode", "create")
    body = (a.get("body") or "").rstrip()
    sources = a.get("sources") or []
    if isinstance(sources, str):
        sources = [sources]

    if not title:
        raise RuleError("write needs a title")
    sub = vault.cfg["kinds"].get(kind)
    if not sub:
        raise RuleError("kind must be one of: %s" % ", ".join(sorted(vault.cfg["kinds"])))

    rel = "%s/%s/%s.md" % (vault.cfg["wiki"], sub, title)
    p = vault.abs(rel)
    existing = None
    if os.path.exists(p):
        with open(p, encoding="utf-8") as fh:
            existing = fh.read()

    old_front = parse_front(split_front(existing)[0]) if existing else {}
    front = {
        "type": kind,
        "title": title,
        "owner": old_front.get("owner", a.get("owner", "model")),
        "created": old_front.get("created", today()),
        "compiled": today(),
        "confidence": "contested" if mode == "contested" else a.get("confidence", "low"),
        "sources": merge(old_front.get("sources") or [], sources),
    }
    tags = a.get("tags") or old_front.get("tags")
    if tags:
        front["tags"] = tags if isinstance(tags, list) else [tags]

    check_write(vault, rel, front, mode, existing)

    if existing is None:
        text = dump_front(front) + "\n# %s\n\n%s\n" % (title, body)
        action = "created"
    else:
        old_body = split_front(existing)[1]
        if mode == "compiler-note":
            if "## Compiler notes" in old_body:
                new_body = old_body.rstrip() + "\n\n" + body + "\n"
            else:
                new_body = old_body.rstrip() + "\n\n## Compiler notes\n\n" + body + "\n"
            front["owner"] = old_front.get("owner", "human")
            action = "appended a compiler note to"
        elif mode == "contested":
            new_body = (old_body.rstrip()
                        + "\n\n## Contested\n\nA later source disagrees with the above. "
                          "Both positions are kept; neither is deleted.\n\n" + body + "\n")
            action = "recorded a contradiction on"
        else:  # append
            new_body = old_body.rstrip() + "\n\n" + body + "\n"
            action = "appended to"
        text = dump_front(front) + new_body

    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(text)
    return "%s %s\nconfidence: %s   sources: %d" % (
        action, rel, front["confidence"], len(front["sources"]))


def merge(old, new):
    out = list(old)
    for s in new:
        if s not in out:
            out.append(s)
    return out


def op_lint(vault, _a):
    findings, c = lint(vault)
    if not findings:
        return "OK — %d wiki pages, %d raw sources, no rule violations." % (
            c["wiki_pages"], c["raw_files"])
    out = ["%d error(s), %d warning(s) across %d pages and %d sources:"
           % (c["errors"], c["warnings"], c["wiki_pages"], c["raw_files"]), ""]
    for sev, rule, path, msg in findings[:200]:
        out.append("%-5s %-11s %s\n            %s" % (sev.upper(), rule, path, msg))
    if len(findings) > 200:
        out.append("... and %d more" % (len(findings) - 200))
    return "\n".join(out)



# --------------------------------------------------------------------------
# audit — automatic, tamper-evident, local
#
# EU AI Act Article 12 requires logs the system generates itself; manual
# recording does not satisfy it. Article 26 requires a deployer to retain them
# for at least six months. So the log is written on every call without being
# asked, and hash-chained so a later edit is detectable rather than deniable.
#
# It never leaves the machine. That is the point, not a limitation.
# --------------------------------------------------------------------------

AUDIT_REL = os.path.join(".scriptorium", "audit.jsonl")
HEAD_REL = os.path.join(".scriptorium", "audit.head")


def audit_path(vault):
    return os.path.join(vault.root, AUDIT_REL)


def _digest(obj):
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def audit_append(vault, tool, args, outcome, rule=None):
    """One line per call, chained to the line before it."""
    if vault.cfg.get("audit") is False:
        return
    path = audit_path(vault)
    prev = "0" * 64
    try:
        if os.path.isfile(path):
            with open(path, "rb") as fh:
                tail = fh.readlines()[-1:] if os.path.getsize(path) else []
            if tail:
                prev = json.loads(tail[0].decode("utf-8")).get("hash", prev)
    except (OSError, ValueError, IndexError):
        pass

    entry = {
        "at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "tool": tool,
        # Arguments are digested, not stored: the log proves what happened
        # without becoming a second copy of the content it describes.
        "args": _digest(args),
        "title": str(args.get("title", ""))[:120],
        "outcome": outcome,
        "rule": rule,
        "prev": prev,
    }
    entry["hash"] = _digest(entry)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        # Anchor: without a recorded head and count, deleting entries off the
        # end leaves a shorter but perfectly valid chain.
        head = os.path.join(vault.root, HEAD_REL)
        count = 1
        if os.path.isfile(head):
            try:
                count = json.load(open(head, encoding="utf-8")).get("count", 0) + 1
            except (OSError, ValueError):
                count = 1
        with open(head, "w", encoding="utf-8") as fh:
            json.dump({"hash": entry["hash"], "count": count,
                       "at": entry["at"]}, fh)
    except OSError:
        pass


def audit_verify(vault):
    """Walk the chain. Any edited or removed line breaks it and says where."""
    path = audit_path(vault)
    if not os.path.isfile(path):
        print("No audit log at %s" % AUDIT_REL)
        return 0
    prev = "0" * 64
    n = 0
    with open(path, encoding="utf-8") as fh:
        for i, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except ValueError:
                print("BROKEN at line %d: not valid JSON" % i)
                return 1
            if e.get("prev") != prev:
                print("BROKEN at line %d: expected prev %s, found %s"
                      % (i, prev[:12], str(e.get("prev"))[:12]))
                print("  A line before this one was edited or removed.")
                return 1
            got = dict(e)
            got.pop("hash", None)
            if _digest(got) != e.get("hash"):
                print("BROKEN at line %d: contents do not match their hash" % i)
                print("  This entry was altered after it was written.")
                return 1
            prev = e["hash"]
            n += 1
    head_path = os.path.join(vault.root, HEAD_REL)
    if os.path.isfile(head_path):
        try:
            anchor = json.load(open(head_path, encoding="utf-8"))
        except (OSError, ValueError):
            anchor = None
        if anchor:
            if anchor.get("count") != n:
                print("BROKEN: log holds %d entries, anchor expects %d."
                      % (n, anchor["count"]))
                print("  %d entr%s removed from the end of the file."
                      % (anchor["count"] - n, "y was" if anchor["count"] - n == 1 else "ies were"))
                return 1
            if anchor.get("hash") != prev:
                print("BROKEN: head is %s, anchor expects %s."
                      % (prev[:12], str(anchor.get("hash"))[:12]))
                return 1
    else:
        print("  No anchor file — truncation from the end cannot be detected.")

    refused = 0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip() and json.loads(line).get("outcome") == "refused":
                refused += 1
    print("\n  Audit chain intact — %d entries, %d refusals." % (n, refused))
    print("  Head: %s" % prev[:32])
    print("  Edits and deletions anywhere in the file break this check.")
    print("  Note: the anchor lives beside the log. Against an attacker with")
    print("  write access to both, ship the head hash somewhere they cannot")
    print("  reach — a SIEM, a WORM bucket, or a second machine.\n")
    return 0


# --------------------------------------------------------------------------
# MCP wiring
# --------------------------------------------------------------------------

TOOLS = [
    {
        "name": "vault_status",
        "description": "Snapshot of the vault: page counts, source counts, ledger "
                       "status breakdown, orphans and lint errors. Call this first.",
        "inputSchema": {"type": "object", "properties": {}},
        "op": op_status,
    },
    {
        "name": "vault_search",
        "description": "Search the vault, compiled pages first and raw sources second — "
                       "compiled understanding outranks raw capture. Returns paths, hit "
                       "counts and the first matching line.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "text to search for"},
                "scope": {"type": "string", "enum": ["all", "wiki", "raw"],
                          "description": "where to look (default all)"},
                "limit": {"type": "integer", "description": "max results (default 20)"},
            },
            "required": ["query"],
        },
        "op": op_search,
    },
    {
        "name": "vault_read",
        "description": "Read one file from the vault by its vault-relative path.",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
        "op": op_read,
    },
    {
        "name": "vault_pending",
        "description": "List sources marked pending in the ledger — the work queue.",
        "inputSchema": {"type": "object", "properties": {}},
        "op": op_pending,
    },
    {
        "name": "vault_capture",
        "description": "Capture a new raw source and register it in the ledger as "
                       "pending. This is the only sanctioned way to add a source; "
                       "existing sources can never be edited.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "body": {"type": "string", "description": "the captured content"},
                "origin": {"type": "string", "description": "URL or provenance note"},
                "kind": {"type": "string", "description": "clip | note | transcript | doc | thread"},
                "batch": {"type": "string"},
            },
            "required": ["title", "body"],
        },
        "op": op_capture,
    },
    {
        "name": "vault_write",
        "description": "Create or update a compiled page. The write is REFUSED if it "
                       "breaks a rule: empty or non-existent sources, a pipe in the "
                       "title, a missing frontmatter field, an overwrite of an existing "
                       "page, or any edit to a human-owned page outside a compiler note. "
                       "Use mode='append' to add, 'contested' when a source disagrees "
                       "with what is already there, 'compiler-note' for human-owned pages.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "page title; also the filename"},
                "kind": {"type": "string", "enum": ["concept", "entity", "topic"]},
                "body": {"type": "string", "description": "markdown body"},
                "sources": {"type": "array", "items": {"type": "string"},
                            "description": "vault-relative paths of sources actually read. Required and must exist."},
                "confidence": {"type": "string", "enum": ["high", "medium", "low", "contested"],
                               "description": "'low' is a valid, honest outcome"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "mode": {"type": "string", "enum": ["create", "append", "contested", "compiler-note"]},
                "owner": {"type": "string", "enum": ["model", "human"]},
            },
            "required": ["title", "body", "sources"],
        },
        "op": op_write,
    },
    {
        "name": "vault_lint",
        "description": "Check every rule across the whole vault: frontmatter validity, "
                       "provenance, sources that no longer exist, pipes in titles, and "
                       "orphan sources with no ledger row.",
        "inputSchema": {"type": "object", "properties": {}},
        "op": op_lint,
    },
]

BY_NAME = dict((t["name"], t) for t in TOOLS)


def public_tools():
    return [{k: t[k] for k in ("name", "description", "inputSchema")} for t in TOOLS]


def handle(vault, req):
    method = req.get("method")
    rid = req.get("id")

    if method == "initialize":
        return ok(rid, {
            "protocolVersion": PROTOCOL,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "scriptorium", "version": VERSION},
        })
    if method in ("notifications/initialized", "notifications/cancelled"):
        return None
    if method == "ping":
        return ok(rid, {})
    if method == "tools/list":
        return ok(rid, {"tools": public_tools()})
    if method == "tools/call":
        params = req.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        tool = BY_NAME.get(name)
        if not tool:
            return ok(rid, {"content": [{"type": "text", "text": "unknown tool: %s" % name}],
                            "isError": True})
        try:
            text = tool["op"](vault, args)
            audit_append(vault, name, args, "allowed")
            return ok(rid, {"content": [{"type": "text", "text": text}]})
        except RuleError as e:
            rule = str(e).split(":")[0][:40]
            audit_append(vault, name, args, "refused", rule=rule)
            text = "REFUSED — %s" % e
            if getattr(e, "plain", None):
                text += "\n\nIn plain terms: %s" % e.plain
            return ok(rid, {"content": [{"type": "text", "text": text}], "isError": True})
        except Exception as e:  # noqa: BLE001 - surface anything as a tool error
            return ok(rid, {"content": [{"type": "text", "text": "error: %s: %s"
                                                                 % (type(e).__name__, e)}],
                            "isError": True})
    if rid is None:
        return None
    return {"jsonrpc": "2.0", "id": rid,
            "error": {"code": -32601, "message": "method not found: %s" % method}}


def ok(rid, result):
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def serve(vault):
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except ValueError:
            continue
        resp = handle(vault, req)
        if resp is not None:
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()


# --------------------------------------------------------------------------
# selftest — proves the refusals actually fire
# --------------------------------------------------------------------------

def selftest(vault):
    cases = []

    def expect_refusal(label, fn):
        try:
            fn()
        except RuleError as e:
            cases.append((True, label, str(e).split("\n")[0][:90]))
            return
        cases.append((False, label, "NOT REFUSED — enforcement is broken"))

    expect_refusal("rule 1  edit under raw/", lambda: check_write(
        vault, vault.cfg["raw"] + "/x.md", {"title": "x"}, "create", None))
    expect_refusal("rule 3  empty sources", lambda: check_write(
        vault, "1-wiki/concepts/X.md",
        {"type": "concept", "title": "X", "owner": "model", "created": today(),
         "compiled": today(), "confidence": "low", "sources": []}, "create", None))
    expect_refusal("rule 2  source not on disk", lambda: check_write(
        vault, "1-wiki/concepts/X.md",
        {"type": "concept", "title": "X", "owner": "model", "created": today(),
         "compiled": today(), "confidence": "low",
         "sources": [vault.cfg["raw"] + "/nope-does-not-exist.md"]}, "create", None))
    expect_refusal("naming  pipe in title", lambda: check_write(
        vault, "1-wiki/concepts/X.md",
        {"type": "concept", "title": "a|b", "owner": "model", "created": today(),
         "compiled": today(), "confidence": "low", "sources": ["x"]}, "create", None))
    expect_refusal("frontmatter  bad confidence", lambda: check_write(
        vault, "1-wiki/concepts/X.md",
        {"type": "concept", "title": "X", "owner": "model", "created": today(),
         "compiled": today(), "confidence": "certain", "sources": ["x"]}, "create", None))
    expect_refusal("rule 4  silent overwrite", lambda: check_write(
        vault, "1-wiki/concepts/X.md",
        {"type": "concept", "title": "X", "owner": "model", "created": today(),
         "compiled": today(), "confidence": "low", "sources": ["x"]},
        "replace", "---\nowner: model\n---\nold body\n"))
    expect_refusal("rule 5  rewrite human page", lambda: check_write(
        vault, "1-wiki/concepts/X.md",
        {"type": "concept", "title": "X", "owner": "human", "created": today(),
         "compiled": today(), "confidence": "low", "sources": ["x"]},
        "append", "---\nowner: human\n---\nold body\n"))

    print("\nscriptorium selftest — every one of these must be REFUSED\n")
    for good, label, msg in cases:
        print("  %s  %-28s %s" % ("PASS" if good else "FAIL", label, msg))
    failed = sum(1 for c in cases if not c[0])
    print("\n%d/%d enforced\n" % (len(cases) - failed, len(cases)))
    return 1 if failed else 0



# --------------------------------------------------------------------------
# onboarding — the part that decides whether a non-developer ever gets started
# --------------------------------------------------------------------------

RAW_NAMES = ["0-raw", "raw", "sources", "00-inbox", "inbox", "Inbox", "clippings"]
WIKI_NAMES = ["1-wiki", "wiki", "notes", "Notes", "permanent", "zettel", "slipbox"]
OUT_NAMES = ["3-output", "output", "outputs", "drafts", "published"]


def _find(root, names):
    listing = dict((n.lower(), n) for n in os.listdir(root)
                   if os.path.isdir(os.path.join(root, n)))
    for want in names:
        hit = listing.get(want.lower())
        if hit:
            return hit
    return None


def _md_subdirs(root, rel):
    """Subfolders of the wiki. Prefer ones with notes in them, but fall back to
    all of them — a freshly created vault has no notes yet, and refusing to
    configure it because it is empty is the worst possible first run."""
    d = os.path.join(root, rel)
    if not os.path.isdir(d):
        return []
    subs = [n for n in sorted(os.listdir(d)) if os.path.isdir(os.path.join(d, n))]
    withmd = [n for n in subs
              if any(f.endswith(".md") for f in os.listdir(os.path.join(d, n)))]
    return withmd or subs


def _kind_name(folder):
    """concepts -> concept, entities -> entity, topics -> topic."""
    if folder.endswith("ies"):
        return folder[:-3] + "y"
    if folder.endswith("s"):
        return folder[:-1]
    return folder


def cmd_setup(root):
    """Look at a folder, work out its layout, and write the config for it."""
    root = os.path.abspath(root)
    print("\nLooking at %s\n" % root)

    raw = _find(root, RAW_NAMES)
    wiki = _find(root, WIKI_NAMES)
    out = _find(root, OUT_NAMES)

    if not raw and not wiki:
        print("  This folder does not look like a vault yet.")
        print("  It has no folder for saved sources and none for your own notes.\n")
        print("  To start a new one here:")
        print("      python3 %s --vault %s --init\n"
              % (os.path.basename(__file__), _q(root)))
        return 1

    cfg = dict(DEFAULTS)
    cfg["raw"] = raw or DEFAULTS["raw"]
    cfg["wiki"] = wiki or DEFAULTS["wiki"]
    cfg["output"] = out or DEFAULTS["output"]

    subs = _md_subdirs(root, cfg["wiki"])
    if subs:
        cfg["wiki_dirs"] = subs
        kinds = {}
        for sub in subs:
            kinds[_kind_name(sub)] = sub
            kinds[sub] = sub
        cfg["kinds"] = kinds
    else:
        cfg["wiki_dirs"] = [""]
        cfg["kinds"] = {"note": ""}

    inbox = os.path.join(cfg["raw"], "inbox")
    cfg["inbox"] = inbox if os.path.isdir(os.path.join(root, inbox)) else cfg["raw"]

    ledger = None
    for cand in (os.path.join(cfg["raw"], "_ledger.md"),
                 os.path.join(cfg["raw"], "ledger.md"), "_ledger.md"):
        if os.path.isfile(os.path.join(root, cand)):
            ledger = cand
            break
    cfg["ledger"] = ledger or os.path.join(cfg["raw"], "_ledger.md")

    print("  saved sources     %s/" % cfg["raw"])
    print("  your notes        %s/%s" % (cfg["wiki"],
                                         ("  (" + ", ".join(subs) + ")") if subs else ""))
    print("  finished work     %s/" % cfg["output"])
    print("  new captures go   %s/" % cfg["inbox"])
    print("  source index      %s%s" % (cfg["ledger"], "" if ledger else "   (will be created)"))

    path = os.path.join(root, ".scriptorium.json")
    if os.path.exists(path):
        print("\n  .scriptorium.json already exists — leaving it alone.")
    else:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, indent=2)
            fh.write("\n")
        print("\n  Wrote .scriptorium.json. Edit it if anything above is wrong.")

    lpath = os.path.join(root, cfg["ledger"])
    if not os.path.isfile(lpath):
        os.makedirs(os.path.dirname(lpath), exist_ok=True)
        with open(lpath, "w", encoding="utf-8") as fh:
            fh.write("# Source index\n\nOne row per thing you saved.\n\n"
                     "| source | batch | added | status | compiled | pages produced |\n"
                     "|---|---|---|---|---|---|\n")
        print("  Created %s." % cfg["ledger"])

    _print_next_steps(root)
    return 0


def cmd_init(root):
    """Create an empty vault with the expected shape."""
    root = os.path.abspath(root)
    made = []
    for d in ["0-raw/inbox", "1-wiki/concepts", "1-wiki/entities", "1-wiki/topics", "3-output"]:
        full = os.path.join(root, d)
        if not os.path.isdir(full):
            os.makedirs(full)
            made.append(d)
    ledger = os.path.join(root, "0-raw/_ledger.md")
    if not os.path.isfile(ledger):
        with open(ledger, "w", encoding="utf-8") as fh:
            fh.write("# Source index\n\nOne row per thing you saved.\n\n"
                     "| source | batch | added | status | compiled | pages produced |\n"
                     "|---|---|---|---|---|---|\n")
        made.append("0-raw/_ledger.md")
    print("\nCreated a vault at %s\n" % root)
    for m in made:
        print("  %s" % m)
    if not made:
        print("  (everything already existed)")
    print("""
  0-raw/     things you saved, never edited afterwards
  1-wiki/    what you worked out, every page citing its sources
  3-output/  finished pieces built from the above
""")
    cmd_setup(root)
    return 0


def _q(p):
    return '"%s"' % p if " " in p else p


def _print_next_steps(root):
    me = os.path.abspath(__file__)
    print("""
  Check it worked:
      python3 %s --vault %s --status

  Let Claude Code use it:
      claude mcp add scriptorium -- python3 %s --vault %s

  Or paste this into another AI app's MCP settings:""" % (_q(me), _q(root), _q(me), _q(root)))
    print(json.dumps({"mcpServers": {"scriptorium": {
        "command": "python3", "args": [me, "--vault", root]}}}, indent=2))
    print()


def main():
    ap = argparse.ArgumentParser(description="scriptorium — rules-enforcing vault MCP server")
    ap.add_argument("--vault", default=os.environ.get("SCRIPTORIUM_VAULT", "."))
    ap.add_argument("--lint", action="store_true", help="run the checks and exit")
    ap.add_argument("--status", action="store_true", help="print a vault snapshot and exit")
    ap.add_argument("--selftest", action="store_true", help="verify the refusals fire")
    ap.add_argument("--verify-audit", action="store_true",
                    help="check the audit chain has not been edited")
    ap.add_argument("--setup", action="store_true",
                    help="work out this folder's layout and write the config for it")
    ap.add_argument("--init", action="store_true",
                    help="create an empty vault here, then set it up")
    ap.add_argument("--version", action="store_true")
    a = ap.parse_args()

    if a.version:
        print("scriptorium %s" % VERSION)
        return 0
    if a.init:
        return cmd_init(a.vault)
    if a.setup:
        return cmd_setup(a.vault)

    try:
        v = Vault(a.vault)
    except SystemExit:
        raise
    if not os.path.isdir(os.path.join(v.root, v.cfg["raw"])):
        sys.stderr.write(
            "\nThis folder does not look like a vault yet — I cannot find a "
            "folder for saved sources.\n\n"
            "  Set up an existing folder:  python3 %s --vault %s --setup\n"
            "  Or start a new vault here:  python3 %s --vault %s --init\n\n"
            % (os.path.basename(__file__), _q(v.root),
               os.path.basename(__file__), _q(v.root)))
        return 2
    if a.selftest:
        return selftest(v)
    if a.verify_audit:
        return audit_verify(v)
    if a.status:
        print(op_status(v, {}))
        return 0
    if a.lint:
        findings, c = lint(v)
        print(op_lint(v, {}))
        return 1 if c["errors"] else 0
    serve(v)
    return 0


if __name__ == "__main__":
    sys.exit(main())
