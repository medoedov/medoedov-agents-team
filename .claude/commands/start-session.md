---
description: Restore durable session state and route to the next public pipeline command.
---

# Start Session

Read `.claude/shared/pipeline-contract.md` first. Its transition matrix, durable
state rules, approval gates, and completion gate are authoritative for this
command.

## Restore durable state

1. Read `work/session-reports/latest.yml`. It is an atomic pointer to the most
   recent dated durable session report; read the referenced report rather than
   treating the pointer as a report itself. If the pointer or referenced report
   is missing or invalid, say so and continue by reconstructing state from the
   canonical feature artifacts.
2. Inspect every active `work/{feature}/` directory, excluding
   `work/completed/`. Read the durable status artifacts that exist:
   - `feature-status.yml`
   - `logs/checkpoint.yml`
   - `tasks-manifest.yml`
3. Treat only `feature-status.yml` and each task's own frontmatter/checkpoint status as
   terminal evidence. A checkpoint alone, session report, `decisions.md`, or backlog text
   is recovery context only and must not be promoted to completion proof.
4. If `awaiting_user.active: true` in a feature's checkpoint, confirm the recorded
   question was actually answered before clearing it (`active: false`) and resuming.
   It must not synthesize user approval from a free-form guess.
5. Summarize the restored feature, current gate, pending task IDs, blockers,
   and the last recommended public command. Ask the user what to continue when
   more than one active feature exists.

## Resume precedence

When there is exactly one resume target and its `awaiting_user` wait has been
confirmed cleared, resume the paused wave or task directly. Multiple resume targets
or a genuine product/authority decision require the user.

Ordinary session starts still only offer the next allowed public command; they
do not auto-run it.

## Route without bypassing gates

Session start does not bypass a specification, plan, explicit approval, or
completion gate. Never route a "simple" request directly to `coder`, and never
route a "complex" request directly to `architect`; both shortcuts bypass the
durable pipeline.

Offer the next public command allowed by `.claude/shared/pipeline-contract.md`:

- Project Knowledge absent or intentionally being revised: `/init-project-knowledge`.
- New work without an approved user spec: `/interview`.
- Approved user spec without an approved tech spec: `/tech-plan`.
- Approved tech spec without an approved task manifest: `/split-tasks`.
- One approved, dependency-ready task selected: `/do-task {task-id}`.
- Approved manifest with multiple pending tasks: `/do-all-tasks`.
- All execution and QA evidence satisfies the completion gate: `/done`.

Do not spawn an implementation or planning agent merely because this command
was invoked. Do not assume Claude Agent Teams, a team configuration file, or an
environment flag exists; use only the runtime capabilities actually available
in the current session.
