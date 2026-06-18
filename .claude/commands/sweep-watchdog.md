---
description: |
  Single sweep cycle for the watchdog agent. Invoked via /loop 10m. Reads
  filesystem state, classifies stalls (S1-S4), pings or escalates, writes to
  watchdog.log.
---

# Sweep-watchdog — single sweep cycle

This command implements one full sweep cycle of the watchdog agent
(`.claude/agents/watchdog.md`). The watchdog invokes it via `/loop 10m
/sweep-watchdog` immediately after TeamCreate and continues until the
`/do-all-tasks` run ends. Each invocation is independent: it reads state, acts,
logs, and returns.

The agent spec is the authoritative reference for stall classifier rules
(S1–S4), the 3-ping escalation thresholds, Surface 1/2/3 message templates,
the M4 rate-limit path, and the exact permitted Bash patterns. This command
implements one iteration of that algorithm; it does not redefine it. Where a
rule could drift between the two files, the agent spec wins — point to it
rather than duplicate.

The sweep does not spawn agents, modify code, or write to `decisions.md`. It
reads filesystem state, sends pings or escalations, optionally writes
`stall_state` to `checkpoint.yml` on a rate-limit detection, and appends one
JSON line to `work/{feature}/logs/watchdog.log`.

## Inputs read

- `work/{feature}/logs/checkpoint.yml` — `team_name`, `tasks:` block (active
  teammates derived from `in_progress` rows), `stall_state.active` (skip-if-true
  guard), `last_completed_wave`.
- For each active teammate: TaskList unread-message count and `next:` marker.
- For each active teammate: that teammate's last raw output / log text — used
  by S4 detection when feeding the M4 classifier.

## Sweep steps (in order)

### Step 1 — Read state

If `awaiting_user.active == true` in `checkpoint.yml`, the run is parked behind
a user decision (plan approval, reviewer-conflict choice, escalation reply,
deploy go-ahead). The teammates are correctly waiting, not stalled — pinging
them is noise. Short-circuit: write one log entry with `active_teammates: []`,
`stall_types: ["awaiting-user"]`, `pings_sent: 0`, `redacted: true`, and return.
This is the awaiting-user guard from the agent spec ("Awaiting-user
suppression"). Team-lead clears the flag when the user replies.

If `stall_state.active == true` in `checkpoint.yml`, the run is already
paused waiting for an M4 wake. Skip the rest of this sweep, write a single
log entry with `active_teammates: []`, `stall_types: []`, `redacted: true`,
and return. This is the idempotency guard from the agent spec M4 section.

Otherwise enumerate active teammates from the checkpoint `tasks:` block — any
row with `status: in_progress`. Skip the teammate literally named `watchdog`
(self-skip per agent spec edge cases). Also skip any teammate whose latest
marker is `next: awaiting-user` (or `blocked: user`): it is individually parked
on the user, so run no oracle, no classification, and no `consecutive_stale`
increment for it — record it under `awaiting_user_teammates` in the log entry
and move on. Per agent spec "Awaiting-user suppression".

If `checkpoint.yml` is missing or unreadable, append one log entry with a
warning marker (`stall_types: ["checkpoint-missing"]`, `redacted: true`) and
return. Do not crash the sweep loop.

For each active teammate compute `last_activity` as the union (max) of the
four filesystem signals:

- Most-recent commit touching the feature directory:
  `git log --format=%ct -1 -- work/{feature}/`
- `decisions.md` mtime:
  `python -c "import os,sys; print(int(os.path.getmtime(sys.argv[1])))" work/{feature}/decisions.md`
- Newest per-task review report mtime:
  `python -c "import os,sys; print(int(os.path.getmtime(sys.argv[1])))" work/{feature}/logs/working/{task}/<newest>.json`
- Newest audit wave report mtime (covers audit-wave teammates that write
  to `work/{feature}/logs/tasks/*.json` — e.g. security-auditor, bug-hunter,
  test-reviewer — and would otherwise not trip the per-task glob):
  `python -c "import os,sys; print(int(os.path.getmtime(sys.argv[1])))" work/{feature}/logs/tasks/<newest>.json`

A missing signal contributes 0 (epoch), never a crash.

### Step 2 — Genuine-work oracle

If `now - last_activity < 300` seconds — a fixed 5-minute recent-work window,
deliberately decoupled from the 10-minute sweep cadence — the teammate is
making genuine progress. Reset that teammate's `consecutive_stale` counter to
0 and skip classification for this teammate. (With a 10-minute sweep the 5–15
min grace window between this oracle and the 15-min S3 threshold absorbs any
gap, so no false ping is emitted for work done between sweeps.) This is the only line of
defence against false positives on long edits, large reads, or multi-minute
Bash. The union over four signals is deliberate — any one is sufficient
proof of work (see agent spec, "Filesystem genuine-work oracle").

### Step 3 — Stall classification

If the oracle did not fire (all four signals are >5 min stale), classify
the teammate into at most one of S1–S4 per the agent spec rules:

- **S1 — Multi-reviewer round desync.** `len(reviewers) >= 2` AND the
  teammate's last `SendMessage` to any reviewer is >30 min old AND the
  teammate is not in `next: idle` AND at least one expected reviewer report
  for R(N) is missing. Action: log + escalate to team-lead with the marker
  `reviewer {name} stuck on R(N)`. Do not run the 3-ping protocol — S1 goes
  straight to team-lead.
- **S2 — Idle with pending inbox.** Teammate emitted `next: idle` while
  TaskList shows `has_unread == true`. Action: 3-ping protocol (Step 4).
- **S3 — No filesystem progress.** All four activity signals >15 min stale
  AND `has_unread == false`. Action: 3-ping protocol (Step 4).
- **S4 — Subscription rate-limit.** Teammate's last output contains a
  subscription rate-limit error. Detection: feed the error body through the M4
  classifier Bash snippet below (Step 6); branch on `result == "rate_limit"`.
  Action: M4 path (Step 5). Skip the 3-ping protocol — rate-limit is not a
  ping-recoverable class.

Each teammate gets at most one class per sweep. If S4 matches, it wins over
S2/S3 (rate-limit dominates other signals).

Increment `consecutive_stale` for the teammate on each classification hit
that is not S4. Reset to 0 on any inbound message between sweeps or any
oracle hit.

### Step 4 — Action: 3-ping escalation (S2 / S3)

Per the agent spec "3-ping escalation protocol":

- `consecutive_stale == 1`: `SendMessage(teammate, <Surface 1 ping text>)` —
  the Surface 1 template from the agent spec. Log entry with `pings_sent: 1`.
- `consecutive_stale == 2`: `SendMessage(teammate, <Surface 1 ping text>)`
  again — same template, repeated. Log entry with `pings_sent: 2`.
- `consecutive_stale >= 3`: stop pinging. Send the **Surface 2 escalation**
  to the user via messaging platform alert + chat message — the Surface 2 template
  from the agent spec, with `{N}`, `{teammate}`, `{X}`, `{Y}`, `{timestamps}`
  filled from sweep state. Log entry with `escalations: 1`. The counter does
  not auto-reset above 3; the watchdog waits for the user's decision.

Surface 1 and Surface 2 wording is owned by `.claude/agents/watchdog.md`
("Surface message templates"). Do not redefine the strings here.

### Step 5 — Action: M4 rate-limit path (S4)

Per the agent spec "M4 rate-limit path", executed exactly once per detection
(the Step 1 `stall_state.active` guard makes it idempotent):

1. Run Pattern 4 (Retry-After extraction) on the error body immediately after
   Pattern 3 confirms the bucket is `rate_limit`. If Pattern 4 returns a
   non-empty integer string `N`, set `reset_at = now + N + buffer_seconds`.
   If Pattern 4 returns an empty string, default `reset_at = now + 18000s (5 h)`
   — the subscription usage-limit rolling window. Conservative fallback over
   fragile parsing.
2. Write the 8-field `stall_state` block to
   `work/{feature}/logs/checkpoint.yml`:
   `active: true`, `reason: "rate_limit"` (canonical — exact string matched
   by `SessionStart.sh`, NOT `rate_limit_exceeded`), `detected_at` (ISO-8601
   UTC, current), `reset_at` (ISO-8601 UTC, computed above), `buffer_seconds:
   60`, `pending_teammates` (active teammate names from this sweep),
   `last_active_wave` (`checkpoint.last_completed_wave + 1`),
   `resume_attempts: 0` (see agent spec known v1.0 limitation — counter is
   never incremented in this iteration).
3. Attempt `ScheduleWakeup(delaySeconds = (reset_at - now) + buffer_seconds)`.
   On success, the resume fires at the wake. On failure (tool unavailable in
   the teammate context), `SessionStart.sh` is the cross-session backstop.
4. Send the **Surface 3 auto-resume wake** to the user via messaging platform alert +
   chat message — the Surface 3 template from the agent spec, with
   `{duration}`, `{start}`, `{end}`, `{N}`, `{M}`, `{task_name}` filled from
   the checkpoint and computed timestamps.

### Step 6 — Log write (every sweep, no exceptions)

Append exactly one JSON-line entry to `work/{feature}/logs/watchdog.log`.
Entry schema (one line per sweep, newline-delimited):

```json
{
  "sweep_id": "uuid4",
  "ts": "2026-05-24T02:15:00Z",
  "active_teammates": ["t3-impl"],
  "stale_count": 1,
  "pings_sent": 1,
  "escalations": 0,
  "stall_types": ["S2"],
  "awaiting_user_teammates": [],
  "redacted": true
}
```

`awaiting_user_teammates` holds teammates skipped this sweep for a
`next: awaiting-user` marker (Step 1). When the global `awaiting_user.active`
guard fires, the whole entry is the short-circuit form from Step 1:
`active_teammates: []`, `stall_types: ["awaiting-user"]`, `pings_sent: 0`.

Before assembling the entry, every string field passes through
`_redact_sensitive()` from the project error classifier module (see
project-knowledge patterns.md for the module path).
This strips LLM provider API key patterns (e.g. `sk-ant-...`, `sk-...`),
Google `AIza...`, and HTTP `Bearer ...` / `Basic ...` patterns, replacing
each match with `[REDACTED]`. The redaction is reused — never re-implemented
inline — because the production classifier is the audited truth source and
any drift between watchdog and bot-runtime redaction would be a security gap.

The `"redacted": true` sentinel is required on every log entry, set
unconditionally after the redaction pass. Its absence in any written log line
indicates a log-path bypass that did not run through `_redact_sensitive()`.
Tests in `tests/agent_orchestration/test_redaction.py` (Task 7) assert both:
(a) absence of bearer tokens / API keys in log content, and (b) presence of
`"redacted": true` on every parsed line. The sentinel-presence check is the
canary — it fails loudly if a future refactor adds a code path that writes
to `watchdog.log` without going through the redaction wrapper.

A sweep with no active teammates still writes one log entry: `stale_count: 0`,
`active_teammates: []`, `stall_types: []`, `redacted: true`.

## Permitted Bash patterns

Exactly three Bash invocations are permitted from this command. No other
Bash commands are allowed; any deviation is a finding for the reviewer.
These mirror the agent spec "Permitted Bash patterns" section verbatim — the
two files share one enumeration so drift is impossible.

**1. Git mtime for a path** (epoch seconds of the most recent commit
touching the path):

```bash
git log --format=%ct -1 -- <path>
```

The `--` separator is mandatory. It separates revision arguments from path
arguments and prevents `<path>` being misread as a ref when the path string
happens to match an existing branch or tag name.

**2. File mtime in epoch seconds** (for files not in git or for uncommitted
review reports):

```bash
python -c "import os,sys; print(int(os.path.getmtime(sys.argv[1])))" <path>
```

The path is passed as `sys.argv[1]`, never interpolated into the script
string.

**3. M4 rate-limit classifier invocation:**

```bash
ERROR_MSG="$raw_error" python -c "
    import os, sys
    sys.path.insert(0, '.')
    from <project_module>.error_classifier import classify_claude_error, _redact_sensitive
    class _E(Exception):
        def __init__(self, m): self.message = m
    result = classify_claude_error(_E(os.environ['ERROR_MSG']))
    print(result)"
```

The error string is passed via the `ERROR_MSG` environment variable. It is
**never** interpolated into the `python -c` command string. An error body
may contain arbitrary characters — shell metacharacters, quotes, backticks,
`$(...)` patterns — that would execute or break shell parsing if
interpolated. Env-var passing is injection-safe; string interpolation is
not. This is the only injection-safe path for moving an attacker-controllable
string from Bash into Python.

**4. Pattern 4 — Retry-After header extraction.** Returns integer seconds
string if `Retry-After` is present in the error body, empty string otherwise.
The M4 path uses this immediately after pattern 3 returns `rate_limit`; if
non-empty, `reset_at = now + retry_after + buffer_seconds`; if empty, fall
back to `now + 5h + buffer`. `ERROR_MSG` env-var passing keeps the
injection-safety property.

```bash
ERROR_MSG="$raw_error" python -c "
import os, re
m = re.search(r'Retry-After:\s*(\d+)', os.environ['ERROR_MSG'])
print(m.group(1) if m else '')"
```

## Edge cases

- **No active teammates** (all idle/done): write one log entry with
  `active_teammates: []`, `stale_count: 0`, `stall_types: []`, `redacted:
  true`. Skip all ping/escalation logic.
- **`checkpoint.yml` not found:** log one warning entry
  (`stall_types: ["checkpoint-missing"]`, `redacted: true`) and return. Do
  not crash the sweep loop.
- **Self-skip:** the teammate literally named `watchdog` must not appear in
  `active_teammates` and never triggers a ping — even if it appears in
  TaskList alongside other teammates.
- **Windows mtime resolution:** NTFS stores timestamps at 100 ns granularity, but filesystem/OS layers may round — treat sub-second equality conservatively; the 10-minute sweep window is unaffected.
- **Already-paused run:** if `stall_state.active == true` from a prior M4
  detection, Step 1 short-circuits with an empty log entry. Resume is owned
  by `SessionStart.sh` / `ScheduleWakeup`, not by the sweep itself.
