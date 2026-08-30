# quiet

**The anti-dashboard.**

Every other tool you own is paid to show you more. This one is built to say
nothing. It reads your streams, ranks what it finds, and prints **one thing** —
or, most days, nothing at all.

```
$ quiet
  smart-kitchen-scale — Gate 1 — Does the European database gap actually exist?  — tomorrow
```

```
$ quiet
$
```

The second one is the product working.

There is deliberately no `--all`. If you want everything, you already have ten
apps for that. The discipline is the point: a tool that can show you everything
becomes another thing to check.

## Use

```
quiet              one line, or silence
quiet --why        ...and why that one, and what it suppressed
quiet --notify     desktop notification, or nothing at all
quiet --score      how often it managed to stay quiet
quiet --streams    what it can currently see
quiet --selftest   check the ranking and date logic
```

Put it somewhere on your PATH, or alias it. It is one file with no
dependencies. Running it costs about a second.

## The number that matters

```
$ quiet --score

  Silent on 41 of the last 50 runs  (82%)
  Lifetime: 214 runs, spoke 38 times.

  The number to want high is the first one.
```

Most tools measure engagement. This one measures how often it left you alone.
If that percentage falls, either your life got genuinely busier or the
threshold is wrong — both are worth knowing, and neither is visible in any
other tool you own.

## Letting it interrupt you

A tool you have to remember to check is not solving a noise problem. `--notify`
fires a desktop notification when there is something to say, and does nothing
whatsoever when there is not.

```
quiet --notify        # notification, or absolute silence
```

It will not repeat itself. Once it has notified you about something it stays
quiet about that thing for 20 hours (`--repeat-after`). Saying it twice is how
a quiet tool becomes a nagging one, which is the whole failure mode.

To run it on a schedule:

```bash
cp com.gleb.quiet.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.gleb.quiet.plist
```

Three times a day — 09:00, 13:00, 17:00. Not hourly: something that checks in
constantly is the problem, not the fix. To stop it:

```bash
launchctl unload ~/Library/LaunchAgents/com.gleb.quiet.plist
```

## Streams

Three are built in:

- **vault** — deadlines and gates in a markdown vault's active projects, and
  unfinished commitments in today's note
- **git** — uncommitted work and unpushed commits across your repos. Urgency
  rises for three weeks then *decays*: something untouched for months is
  abandoned, not urgent, and saying so daily is exactly the noise this removes
- **plugins** — anything executable in `~/.quiet/streams/`

Add a stream by dropping an executable in `~/.quiet/streams/`. It prints JSON
lines:

```json
{"text": "Payment failed for INV-1042", "source": "stripe", "urgency": 85}
{"text": "Design review", "source": "calendar", "due": "2026-09-03"}
```

`due` or `urgency` — either is enough. Anything that can print JSON can be a
stream: a calendar export, a Slack digest, a cron job, an MCP client, a text
file. A working example ships at `~/.quiet/streams/manual`, which reads
`~/.quiet/manual.txt`:

```
Send the three adoption-report emails | 2026-09-01
```

## Config

`~/.quiet/config.json`, all optional:

```json
{
  "vaults": ["~/Claude_Cowork/GlebOS"],
  "repos": ["~/Claude_Cowork"],
  "threshold": 60,
  "stale_days": 3
}
```

`threshold` is the whole tuning surface. At 60 it speaks about things overdue,
due today, or due tomorrow. Raise it and it speaks less. Lower it and it
becomes every other tool you already have.

## What it is not

Not a dashboard, not a task manager, not a notification service. It has no
inbox, no badge, no unread count, and nothing to check. You run it, and usually
nothing happens.
