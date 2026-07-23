---
description: Decompose approved tech-spec into atomic tasks with validation.
allowed-tools:
  - Skill
---

# Instructions

Read `.claude/shared/pipeline-contract.md` first. `/split-tasks` is the F4 -> F5
transition and must follow its durable state and completion gate rules.

Before mutation, require both `work/{feature}/user-spec.md` and
`work/{feature}/tech-spec.md` to record `status: approved`. In particular, an
existing tech spec without durable approved status is not executable: stop and
offer `/tech-plan`. Do not infer approval from chat, a commit, or file existence.

Use the `task-decomposition` skill. It owns the bounded creation/validation
workflow; child task creators return evidence while the parent alone atomically
aggregates `task-files-map.yml` and `tasks-manifest.yml`.

The command is complete only when the durable completion gate passes:
dependencies and file ownership validate, the single cross-task pass has no
unresolved findings, and `work/{feature}/tasks-manifest.yml` records
`status: approved`. Then offer `/do-task {task-id}` or `/do-all-tasks` according
to the approved manifest.
