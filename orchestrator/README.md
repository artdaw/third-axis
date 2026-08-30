# orchestrator

**A research spike, not a shipped component.** Read this before assuming it
does something.

It answers one question with a number instead of an opinion: *if you wanted a
small local model to run your agent loop, what would it have to learn, and do
you have enough data to teach it?*

## Why the question is live again

The 2024 answer was "routers don't work." That is now wrong, for a specific
reason — the failures were people *prompting* small general models. Training
them is different:

| | |
|---|---|
| 350M fine-tuned, ToolBench | **77.55%** |
| 175B general baseline | 26% |
| xLAM-2-1b-fc-r (purpose-built 1B) | 30.44 |
| Llama-3.2-1B-Instruct (same size, general) | 10.82 |

A model 500× smaller beat the large one by 51 points. Size is close to
irrelevant for a narrow structured job; **training objective is everything.**
NVIDIA's position paper puts it plainly — *Small Language Models are the
Future of Agentic AI* — and reports 80–90% of on-device agent steps staying
local on a 3–9B model.

The pattern that won is **local-by-default, cloud-on-escalation**: a small
router runs the loop and hands a single turn upstairs when confidence drops or
a tool call fails to parse.

This matters for Third Axis beyond cost. **The orchestrator sees all the
context — it has to, in order to route.** That makes it the highest-leverage
privacy component in any agent stack, and a local router that logs its
decisions is also the traceability artifact an auditor asks for.

## Use

```bash
python3 extract-trajectories.py --stats           # what your own history holds
python3 extract-trajectories.py --out train.jsonl # write the training file
```

Read-only, standard library, nothing leaves the machine. It reads
`~/.claude/projects/**/*.jsonl` and emits one example per routing decision:
the goal, the steps already taken, and the tool that came next.

## Read the output honestly

On the first vault it was run against: **679 decision points, 15 tools, and
Bash at 67%.**

That last number is the whole story. A model that always guesses `Bash` scores
67% and has learned nothing — that is the baseline to beat, and it is a hard
one. The tail (3–8 examples for some tools) is unlearnable from this alone,
and 679 sits at the bottom of the 1K–100K band the LoRA literature uses.

**The honest plan, if you continue:** augment with a public tool-calling set —
ToolBench, xLAM, ToolMind, the International Tool Calling Dataset — and use
local traces only for the final personalisation pass. LoRA/QLoRA with PEFT or
Unsloth on a single GPU is a fortnight, not a research programme.

## Two smaller problems worth doing first

Both are in this repo already, both are currently hand-tuned heuristics, and
both are better-posed than a general router:

- **`quiet`'s ranking** is a hardcoded table — 92 for today, 74 for tomorrow.
  It should be learned from which items you actually act on. A ranker, not a
  generator.
- **`scriptorium`'s retrieval** is a linear scan. A small reranker over a few
  hundred pages is a clean task with obvious relevance labels.

Neither needs a new model architecture. Both improve a tool you use daily.
