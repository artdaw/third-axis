#!/usr/bin/env python3
"""
Turn local Claude Code history into orchestration training data.

One example per routing decision: given the state so far, which tool came next.
Read-only. Nothing leaves the machine — which is rather the point of wanting a
local orchestrator in the first place.

    python3 extract-trajectories.py --stats
    python3 extract-trajectories.py --out train.jsonl
"""
import argparse, collections, glob, json, os, sys

ROOT = os.path.expanduser("~/.claude/projects")


def turns(path):
    """Yield records in file order."""
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                yield json.loads(line)
            except ValueError:
                continue


def brief(text, n=400):
    text = " ".join(str(text).split())
    return text[:n]


def extract(root):
    """Each assistant tool_use is a decision. State = what preceded it."""
    examples = []
    for path in sorted(glob.glob(os.path.join(root, "**", "*.jsonl"), recursive=True)):
        project = os.path.basename(os.path.dirname(path))
        last_user = ""
        recent = []          # rolling window of (tool, ok) already taken this turn
        for d in turns(path):
            t = d.get("type")
            if t == "user" and not d.get("isSidechain"):
                msg = d.get("message") or {}
                c = msg.get("content")
                if isinstance(c, str) and c.strip():
                    last_user = brief(c)
                    recent = []
                continue
            if t != "assistant":
                continue
            content = (d.get("message") or {}).get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if block.get("type") != "tool_use":
                    continue
                name = block.get("name")
                if not name or not last_user:
                    continue
                inp = block.get("input") or {}
                examples.append({
                    "project": project,
                    "goal": last_user,
                    "steps_so_far": list(recent[-6:]),
                    "next_tool": name,
                    "arg_keys": sorted(inp.keys())[:8],
                    "arg_preview": brief(inp.get("command") or inp.get("file_path")
                                         or inp.get("query") or inp.get("pattern") or "", 120),
                })
                recent.append(name)
    return examples


def stats(ex):
    tools = collections.Counter(e["next_tool"] for e in ex)
    projects = collections.Counter(e["project"] for e in ex)
    depth = collections.Counter(len(e["steps_so_far"]) for e in ex)
    goals = len(set(e["goal"] for e in ex))

    print("\n  ORCHESTRATION TRAINING SET — extracted from local history\n")
    print("  Decision points        %6d" % len(ex))
    print("  Distinct goals         %6d" % goals)
    print("  Distinct tools         %6d" % len(tools))
    print("  Projects               %6d" % len(projects))

    print("\n  Tool distribution (the label space):")
    total = sum(tools.values()) or 1
    top = tools.most_common(12)
    width = max(len(t) for t, _ in top)
    for name, c in top:
        bar = "#" * max(1, int(34 * c / top[0][1]))
        print("    %-*s %5d  %4.1f%%  %s" % (width, name, c, 100.0 * c / total, bar))
    if len(tools) > 12:
        print("    ...and %d more tools" % (len(tools) - 12))

    print("\n  Steps already taken when the decision was made:")
    for k in sorted(depth)[:7]:
        print("    %d prior step(s)  %5d" % (k, depth[k]))

    head = tools.most_common(1)[0]
    print("\n  READ THIS BEFORE TRAINING ANYTHING")
    print("    - Majority class is %s at %.0f%%. A model that always guesses it"
          % (head[0], 100.0 * head[1] / total))
    print("      scores that much and has learned nothing. That is the baseline to beat.")
    print("    - %d examples sits at the bottom of the 1K-100K band the LoRA" % len(ex))
    print("      literature uses. Expect to augment with a public tool-calling set.")
    print("    - These are one person's workflows. A router trained here fits them,")
    print("      and that is the point — but it will not generalise off them.\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=ROOT)
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--out", help="write JSONL training file")
    a = ap.parse_args()

    if not os.path.isdir(a.dir):
        sys.exit("no history at %s" % a.dir)
    ex = extract(a.dir)
    if not ex:
        sys.exit("no decision points found")
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            for e in ex:
                fh.write(json.dumps(e, ensure_ascii=False) + "\n")
        print("wrote %d examples to %s" % (len(ex), a.out))
    if a.stats or not a.out:
        stats(ex)
    return 0


if __name__ == "__main__":
    sys.exit(main())
