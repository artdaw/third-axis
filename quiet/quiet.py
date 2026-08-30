#!/usr/bin/env python3
"""
quiet — the anti-dashboard.

Every other tool you own is paid to show you more. This one is built to say
nothing. It reads your streams, ranks everything it finds, and prints **one
thing** — or, most days, nothing at all.

There is deliberately no way to make it list everything. If you want
everything, you already have ten apps for that.

    quiet.py                 # one line, or silence
    quiet.py --why           # ...and why that one, and what it suppressed
    quiet.py --score         # how often it managed to stay quiet
    quiet.py --streams       # what it can currently see

Add a stream: drop any executable in ~/.quiet/streams/. It prints JSON lines:

    {"text": "...", "source": "calendar", "due": "2026-09-03", "urgency": 80}

`due` or `urgency` — either is enough. Anything that can print JSON can be a
stream: a calendar export, a Slack digest, a cron job, an MCP client.
"""

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys

HOME = os.path.expanduser("~")
QUIET_DIR = os.path.join(HOME, ".quiet")
STREAM_DIR = os.path.join(QUIET_DIR, "streams")
LOG = os.path.join(QUIET_DIR, "log.jsonl")
CONFIG = os.path.join(QUIET_DIR, "config.json")

DEFAULTS = {
    "vaults": [os.path.join(HOME, "Claude_Cowork", "GlebOS")],
    "repos": [os.path.join(HOME, "Claude_Cowork")],
    "threshold": 60,
    "stale_days": 3,
}

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


# ---------------------------------------------------------------- signals

class Signal(object):
    def __init__(self, text, source, due=None, urgency=None, detail=""):
        self.text = text.strip()
        self.source = source
        self.due = due
        self.detail = detail
        self.urgency = urgency if urgency is not None else self._from_due()

    def _from_due(self):
        if not self.due:
            return 0
        days = (self.due - dt.date.today()).days
        if days < 0:
            return 100
        return {0: 92, 1: 74, 2: 46, 3: 34}.get(days, max(0, 24 - days))

    def when(self):
        if not self.due:
            return ""
        days = (self.due - dt.date.today()).days
        if days < 0:
            return "%d day%s overdue" % (-days, "" if days == -1 else "s")
        return {0: "today", 1: "tomorrow"}.get(days, "in %d days" % days)


def parse_date(text, today=None):
    """'Sunday 6 Sep' | '30 September 2026' | '2026-09-30' | 'due 14 Sep'."""
    today = today or dt.date.today()
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        try:
            return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    m = re.search(r"\b(\d{1,2})\s+([A-Za-z]{3,9})\.?\s*(\d{4})?", text)
    if not m:
        return None
    mon = MONTHS.get(m.group(2)[:3].lower())
    if not mon:
        return None
    day = int(m.group(1))
    year = int(m.group(3)) if m.group(3) else today.year
    try:
        d = dt.date(year, mon, day)
    except ValueError:
        return None
    if not m.group(3) and (d - today).days < -180:
        try:
            d = dt.date(year + 1, mon, day)
        except ValueError:
            return None
    return d


# ---------------------------------------------------------------- streams

def stream_vault(cfg):
    """Deadlines, gates and open commitments inside a markdown vault."""
    out = []
    today = dt.date.today()
    for vault in cfg["vaults"]:
        proj = os.path.join(vault, "2-projects")
        if not os.path.isdir(proj):
            continue
        for slug in sorted(os.listdir(proj)):
            pdir = os.path.join(proj, slug)
            claude = os.path.join(pdir, "CLAUDE.md")
            if not os.path.isfile(claude):
                continue
            try:
                head = open(claude, encoding="utf-8", errors="replace").read(2000)
            except OSError:
                continue
            if "status: active" not in head:
                continue

            for name in sorted(os.listdir(pdir)):
                if not name.endswith(".md"):
                    continue
                path = os.path.join(pdir, name)
                try:
                    text = open(path, encoding="utf-8", errors="replace").read()
                except OSError:
                    continue
                heading = ""
                for line in text.split("\n"):
                    if line.startswith("#"):
                        heading = re.sub(r"^#+\s*", "", line).strip()
                        continue
                    m = re.search(r"(?:\*\*)?(?:Due:|verdict|Decide by|Ship .*?by)\s*"
                                  r"([^.*]{3,40})", line)
                    if not m:
                        continue
                    d = parse_date(m.group(1))
                    if not d or (d - today).days > 7:
                        continue
                    label = heading or re.sub(r"[*#>|`\[\]]", "", line).strip()
                    label = re.sub(r"\s+", " ", label).rstrip(".")[:80]
                    out.append(Signal("%s — %s" % (slug, label),
                                      "%s/%s" % (slug, name), due=d,
                                      detail=re.sub(r"\s+", " ",
                                                    re.sub(r"[*`]", "", line)).strip()[:150]))

        # unfinished commitments in today's daily note
        daily = os.path.join(vault, "4-journal", "daily", str(today.year),
                             "%s.md" % today.isoformat())
        if os.path.isfile(daily):
            try:
                lines = open(daily, encoding="utf-8", errors="replace").read().split("\n")
            except OSError:
                lines = []
            open_items = [l for l in lines if l.strip().startswith("- [ ]") and len(l.strip()) > 8]
            if len(open_items) >= 6:
                out.append(Signal(
                    "%d things still open in today's note" % len(open_items),
                    "daily note", urgency=52,
                    detail="A list this long is a plan you did not make."))
    return out


def stream_git(cfg):
    """Work sitting uncommitted, and commits that never left the machine."""
    out = []
    seen = set()
    for root in cfg["repos"]:
        if not os.path.isdir(root):
            continue
        for name in sorted(os.listdir(root)):
            repo = os.path.join(root, name)
            if repo in seen or not os.path.isdir(os.path.join(repo, ".git")):
                continue
            seen.add(repo)
            dirty = _git(repo, ["status", "--porcelain"])
            if dirty:
                n = len([l for l in dirty.split("\n") if l.strip()])
                last = _git(repo, ["log", "-1", "--format=%ct"])
                age = 0
                if last and last.isdigit():
                    age = (dt.datetime.now() - dt.datetime.fromtimestamp(int(last))).days
                if age >= cfg["stale_days"]:
                    # Rises for three weeks, then decays. Something untouched for
                    # months is abandoned, not urgent, and saying so daily is
                    # precisely the noise this tool exists to remove.
                    if age <= 21:
                        urg = 38 + age * 2
                    else:
                        urg = max(8, 80 - (age - 21))
                    out.append(Signal(
                        "%s has %d uncommitted change%s, last commit %d days ago"
                        % (name, n, "" if n == 1 else "s", age),
                        "git", urgency=urg,
                        detail="Uncommitted work is work nobody else can see."))
            ahead = _git(repo, ["rev-list", "--count", "@{u}..HEAD"])
            if ahead and ahead.isdigit() and int(ahead) > 0:
                out.append(Signal(
                    "%s has %s commit%s never pushed"
                    % (name, ahead, "" if ahead == "1" else "s"),
                    "git", urgency=44))
    return out


def _git(repo, args):
    try:
        r = subprocess.run(["git", "-C", repo] + args, stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL, timeout=8)
        return r.stdout.decode("utf-8", "replace").strip()
    except Exception:
        return ""


def stream_plugins(_cfg):
    """Anything executable in ~/.quiet/streams/ that prints JSON lines."""
    out = []
    if not os.path.isdir(STREAM_DIR):
        return out
    for name in sorted(os.listdir(STREAM_DIR)):
        path = os.path.join(STREAM_DIR, name)
        if not os.access(path, os.X_OK) or os.path.isdir(path):
            continue
        try:
            r = subprocess.run([path], stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, timeout=20)
            body = r.stdout.decode("utf-8", "replace")
        except Exception:
            continue
        for line in body.split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            due = None
            if d.get("due"):
                due = parse_date(str(d["due"]))
            out.append(Signal(str(d.get("text", "")).strip() or "(no text)",
                              str(d.get("source", name)),
                              due=due, urgency=d.get("urgency"),
                              detail=str(d.get("detail", ""))))
    return out


STREAMS = [("vault", stream_vault), ("git", stream_git), ("plugins", stream_plugins)]


# ---------------------------------------------------------------- the point

def load_config():
    cfg = dict(DEFAULTS)
    if os.path.isfile(CONFIG):
        try:
            with open(CONFIG, encoding="utf-8") as fh:
                cfg.update(json.load(fh))
        except (OSError, ValueError):
            pass
    return cfg


def collect(cfg):
    sigs = []
    for _name, fn in STREAMS:
        try:
            sigs += fn(cfg)
        except Exception:
            continue
    dedup, seen = [], set()
    for s in sorted(sigs, key=lambda x: -x.urgency):
        key = s.text.lower()[:60]
        if key in seen:
            continue
        seen.add(key)
        dedup.append(s)
    return dedup


def said_recently(text, hours=20):
    """Have we already said this? Saying it twice is how a quiet tool becomes
    a nagging one, which is the failure mode this whole thing exists to avoid."""
    if not text or not os.path.isfile(LOG):
        return False
    cutoff = dt.datetime.now() - dt.timedelta(hours=hours)
    try:
        with open(LOG, encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if not r.get("said") or r.get("said") != text:
                    continue
                if not r.get("notified"):
                    continue
                try:
                    if dt.datetime.fromisoformat(r["at"]) >= cutoff:
                        return True
                except ValueError:
                    continue
    except OSError:
        return False
    return False


def notify(text, subtitle=""):
    """macOS notification. Silence stays silent — nothing is fired at all."""
    try:
        script = ('display notification %s with title "quiet"%s'
                  % (json.dumps(text),
                     (" subtitle %s" % json.dumps(subtitle)) if subtitle else ""))
        subprocess.run(["osascript", "-e", script],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        return True
    except Exception:
        return False


def record(spoke, chosen, total, notified=False):
    try:
        os.makedirs(QUIET_DIR, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "at": dt.datetime.now().isoformat(timespec="seconds"),
                "spoke": spoke, "considered": total, "notified": notified,
                "said": chosen.text if chosen else None}) + "\n")
    except OSError:
        pass


def score():
    if not os.path.isfile(LOG):
        print("No runs recorded yet.")
        return 0
    runs = []
    with open(LOG, encoding="utf-8") as fh:
        for line in fh:
            try:
                runs.append(json.loads(line))
            except ValueError:
                pass
    if not runs:
        print("No runs recorded yet.")
        return 0
    recent = runs[-50:]
    quiet_n = sum(1 for r in recent if not r["spoke"])
    print("\n  Silent on %d of the last %d runs  (%d%%)"
          % (quiet_n, len(recent), round(100.0 * quiet_n / len(recent))))
    print("  Lifetime: %d runs, spoke %d times.\n"
          % (len(runs), sum(1 for r in runs if r["spoke"])))
    print("  The number to want high is the first one.\n")
    return 0


def selftest():
    """Both of these were real bugs found by running on real data."""
    today = dt.date(2026, 8, 30)
    cases = []

    def check(label, got, want):
        cases.append((got == want, label, "got %r, want %r" % (got, want)))

    # The date on a line is the one after "Due:", not the first one anywhere.
    check("picks Sep not the Added date",
          parse_date("Tuesday 30 Sep", today), dt.date(2026, 9, 30))
    check("iso date", parse_date("2026-09-03", today), dt.date(2026, 9, 3))
    check("full month name", parse_date("6 September 2026", today), dt.date(2026, 9, 6))
    check("rolls to next year", parse_date("5 Jan", today), dt.date(2027, 1, 5))
    check("junk is not a date", parse_date("no date here", today), None)

    # Urgency must decay, or an abandoned repo shouts forever.
    over = Signal("x", "t", due=today - dt.timedelta(days=2))
    now_ = Signal("x", "t", due=today)
    soon = Signal("x", "t", due=today + dt.timedelta(days=1))
    later = Signal("x", "t", due=today + dt.timedelta(days=5))
    check("overdue outranks today", over.urgency > now_.urgency, True)
    check("today outranks tomorrow", now_.urgency > soon.urgency, True)
    check("far future is below threshold", later.urgency < 60, True)

    print("\n  quiet selftest\n")
    for ok_, label, msg in cases:
        print("  %s  %-34s %s" % ("PASS" if ok_ else "FAIL", label, "" if ok_ else msg))
    bad = sum(1 for c in cases if not c[0])
    print("\n  %d/%d\n" % (len(cases) - bad, len(cases)))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(
        description="One thing, or nothing.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--why", action="store_true",
                    help="show why this one, and what was suppressed")
    ap.add_argument("--score", action="store_true",
                    help="how often it stayed quiet")
    ap.add_argument("--streams", action="store_true",
                    help="what it can currently see")
    ap.add_argument("--notify", action="store_true",
                    help="fire a desktop notification if there is something to "
                         "say; do nothing at all if there is not")
    ap.add_argument("--repeat-after", type=int, default=20, metavar="HOURS",
                    help="with --notify, stay quiet about the same thing for "
                         "this long (default 20)")
    ap.add_argument("--selftest", action="store_true",
                    help="check the ranking and date logic")
    ap.add_argument("--threshold", type=int, default=None,
                    help="speak only above this urgency (default 60)")
    a = ap.parse_args()

    if a.score:
        return score()
    if a.selftest:
        return selftest()

    cfg = load_config()
    if a.threshold is not None:
        cfg["threshold"] = a.threshold

    sigs = collect(cfg)

    if a.streams:
        print("\n  vault    %s" % ", ".join(os.path.basename(v) for v in cfg["vaults"]))
        print("  git      %s" % ", ".join(os.path.basename(r) for r in cfg["repos"]))
        n = len(os.listdir(STREAM_DIR)) if os.path.isdir(STREAM_DIR) else 0
        print("  plugins  %d in %s" % (n, STREAM_DIR))
        print("\n  %d signal(s) found, %d above threshold %d.\n"
              % (len(sigs), sum(1 for s in sigs if s.urgency >= cfg["threshold"]),
                 cfg["threshold"]))
        return 0

    loud = [s for s in sigs if s.urgency >= cfg["threshold"]]
    chosen = loud[0] if loud else None

    if a.notify:
        if chosen and said_recently(chosen.text, a.repeat_after):
            record(False, chosen, len(sigs))
            return 0
        fired = notify(chosen.text, chosen.when()) if chosen else False
        record(bool(chosen), chosen, len(sigs), notified=fired)
        return 0

    record(bool(chosen), chosen, len(sigs))

    if not chosen:
        if a.why:
            print("\n  Nothing above threshold %d." % cfg["threshold"])
            if sigs:
                print("  Suppressed %d thing(s), loudest was %d:\n" % (len(sigs), sigs[0].urgency))
                for s in sigs[:5]:
                    print("    %3d  %-9s %s" % (s.urgency, s.source[:9], s.text[:64]))
            print()
        return 0

    when = chosen.when()
    print("\n  %s%s" % (chosen.text, ("  — " + when) if when else ""))
    if a.why:
        print("\n  urgency %d, from %s" % (chosen.urgency, chosen.source))
        if chosen.detail:
            print("  %s" % chosen.detail)
        rest = [s for s in sigs if s is not chosen]
        if rest:
            print("\n  Not shown (%d):" % len(rest))
            for s in rest[:6]:
                print("    %3d  %-9s %s" % (s.urgency, s.source[:9], s.text[:62]))
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
