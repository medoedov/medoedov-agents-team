---
name: task-execution
description: |
  Execute a single task from work/{feature}/tasks/{task-id}.md end-to-end:
  load skills, implement, run reviewers (max 3 rounds), commit per round,
  write a state log, return control. Single-task scope only.

  Use when: "/do-task", "do task", "execute task", "run one task",
  "run task T-007", "execute single task", "do one task"
---

# Task Execution

Run one task file, with reviewers if declared, with at most 3 fix rounds, and leave a complete on-disk audit trail. The teammate executing the task is the driver; reviewers are spawned by the teammate, not by team lead. Implementing agents follow `engineering-principles.md` for code style, testing, error handling, and review etiquette.

## When to use

- A user (or team lead) invokes `/do-task` against a single `work/{feature}/tasks/{task-id}.md` file.
- A `feature-execution` wave delegates one task slot to a teammate; that teammate then runs this skill for its own task.
- Direct request like "execute task 13" or "run task T-007" — pointing at one task file.

Not for feature-level wave orchestration — multi-task spawning, wave transitions, audit waves, feature acceptance review, and resume-from-checkpoint live in [feature-execution/SKILL.md](../feature-execution/SKILL.md). If the request covers more than one task, hand back to feature-execution.

## Inputs

Required:
- Path to the task file: `work/{feature}/tasks/{task-id}.md`.

Derived implicitly:
- `feature_path` = parent of `tasks/` (e.g. `work/agent-system-v2-migration/`).
- `task_id` = filename stem (e.g. `13` from `13.md`, or `T-007` from `T-007.md`).

Read from task frontmatter (driven by `task-decomposition` schema):

| Field | Purpose |
|-------|---------|
| `status` | `planned` → `in_progress` → `done`. Set `in_progress` on start, `done` on finish. |
| `skills` | Skills to load before implementing (e.g. `code-writing`, `skill-master`). |
| `reviewers` | Reviewer agents to spawn each round. `none` skips review. |
| `verify` | Verification types: `[smoke]`, `[user]`, `[smoke, user]`, or `[]`. |
| `teammate_name` | Agent name used for SendMessage routing (optional). |
| `depends_on` | Task IDs that must be `done` first. Refuse to start if unmet. |

For implementation guidance inside one round, follow [code-writing/SKILL.md](../code-writing/SKILL.md). For what reviewers do, see [code-reviewing/SKILL.md](../code-reviewing/SKILL.md).

## Process

### 1. Wave composition table per pipeline triggers

The frontmatter shape determines which agents run, and in what order, for this single task:

| Trigger (frontmatter shape) | Spawned agents | Order |
|---|---|---|
| `reviewers: none`, `skills: [<auditor-skill>]` | teammate only (auditor-style task) | teammate → done |
| `reviewers: [code-reviewer, ...]`, code skills | teammate, then listed reviewers in parallel | teammate → review round 1 → fix → review round 2 (if needed) → fix → ... |
| `reviewers: [prompt-reviewer]`, `skills: [prompt-master]` | teammate, then `prompt-reviewer` | teammate → review → fix loop |
| `reviewers: [skill-checker]`, `skills: [skill-master]` | teammate, then `skill-checker` | teammate → review → fix loop |
| `verify: [smoke]` present | teammate runs smoke commands before sending diff to reviewers | smoke → review round 1 |
| `verify: [user]` present | teammate pauses after implementation; team lead asks user; resume on confirmation | implement → user check → review |

Reviewer set is the source of truth in `reviewers:` — never invent additional reviewers, never silently drop a listed one. The two `verify:` rows are additive modifiers: they apply on top of whichever reviewers row matches the frontmatter shape, not as independent pipeline alternatives.

### 2. Coder context carryover protocol

The implementing teammate stays alive across rounds when possible: round N+1 inherits round N's working memory (task body already read, prior diffs already produced, reviewer JSON already parsed).

If the teammate dies between rounds (compaction, crash, explicit shutdown), a fresh spawn must be primed before any fix is attempted. The priming bundle is:

- Original task file body (`work/{feature}/tasks/{task-id}.md`).
- All prior reviewer JSON reports under `work/{feature}/logs/working/task-{task-id}/`.
- All prior diffs (cumulative `git diff` against the pre-task base, or per-round commit diffs).
- The current round number and the unresolved findings list.

Load the priming bundle before any fix. A fresh agent that skips this step repeats earlier mistakes — the bundle is the round's starting context.

### 3. Iteration limit 3

Maximum 3 review-and-fix rounds per reviewer per task. Rationale: diminishing returns — if 3 rounds cannot resolve findings, the issue requires human judgment. After round 3 with unresolved findings:

- Stop the loop. Do not auto-spawn round 4.
- Write an `escalations` entry in the state log naming the unresolved finding and the reviewer.
- Send team lead a message: "Task {task-id} unresolved after 3 review rounds. Escalating."
- Wait for user decision before any further commits.

This mirrors the escalation wording in [feature-execution/SKILL.md](../feature-execution/SKILL.md) Escalation section so behavior is consistent across the two skills.

### 4. Reviewer conflict escalation

Two reviewers can disagree (e.g. `code-reviewer` wants pattern X, `prompt-reviewer` wants pattern Y; or `test-reviewer` demands a test that `code-simplifier` calls over-engineering). The teammate does not pick a side.

Instead:

- Quote both findings verbatim (file, line, recommendation) into a `conflict` entry in the state log.
- Send team lead a message: "Reviewer conflict on task {task-id}: <reviewer A> says X, <reviewer B> says Y. Awaiting decision."
- Halt fixes for the conflicting area until the user decides.
- Resume only with the user's chosen direction recorded in the state log.

A teammate who silently sides with one reviewer and ignores the other has bypassed the conflict — that is a protocol violation.

## Outputs

After the skill finishes, the following artifacts exist on disk:

- State log: `work/{feature}/logs/{task-id}.run.yml` — single source of truth for this run (see next section).
- Reviewer JSON reports: `work/{feature}/logs/working/task-{task-id}/{reviewer-name}-round{N}.json`, one per reviewer per round.
- `decisions.md` entry appended in `work/{feature}/decisions.md` — 1-3 sentence summary plus links to the JSON reports for this task.
- Git commits: one per fix round (`fix: address review round {N} for task {task-id}`), plus the initial implementation commit (`feat|fix: task {task-id} — {brief}`), plus a final review-reports commit (`chore: review reports for task {task-id}`) following the [feature-execution/SKILL.md](../feature-execution/SKILL.md) commit convention.

Task frontmatter `status` is updated `planned` → `in_progress` at start, `done` at finish (or left `in_progress` on escalation, with the state log explaining why).

## State log path

Path: `work/{feature}/logs/{task-id}.run.yml`.

Required keys (prose schema — pick reasonable YAML shapes, but every key below must appear):

- `task_id` — the task identifier matching the filename stem.
- `teammate` — agent name that executed the task.
- `started_at`, `finished_at` — ISO timestamps bracketing the run.
- `rounds` — list of review rounds; per round capture: round number, reviewers spawned, paths to the JSON reports, summary of findings, summary of fixes, commit hash for the fix.
- `reviewers` — flat list of reviewer agent names that participated (deduped across rounds).
- `commits` — ordered list of commit hashes produced by this task run, with subject lines.
- `escalations` — list of escalation entries (each: round number, reason, reviewer(s), unresolved finding, resolution note from user).
- `conflicts` — list of reviewer conflict entries (each: round number, reviewer A finding quoted, reviewer B finding quoted, user resolution).
- `final_status` — one of `done`, `escalated`, `blocked`.

The state log is the artifact a future operator reads to reconstruct what happened on this task without rereading every diff. Keep it factual and link-heavy; do not duplicate prose that already lives in `decisions.md`.

## Self-Verification

- [ ] Task frontmatter updated: `planned` → `in_progress` at start, `done` at finish (or `in_progress` on escalation).
- [ ] State log written at `work/{feature}/logs/{task-id}.run.yml` with all required keys.
- [ ] Each reviewer round produced a JSON report under `work/{feature}/logs/working/task-{task-id}/`.
- [ ] `decisions.md` entry appended for this task.
- [ ] Implementation, fix, and review-reports commits exist on the current branch.
- [ ] Iteration limit honored (max 3 rounds per reviewer); escalation logged if exhausted.
- [ ] Reviewer conflicts (if any) escalated, not silently resolved by the teammate.
