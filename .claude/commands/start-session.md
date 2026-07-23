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
   - task current-run pointers under `logs/working/task-{task-id}/{task-id}.run.yml`
     and immutable records under the sibling `runs/` directory
3. Validate each pointer's containment, ID, digest, and supersedes chain. Treat only the
   selected latest approved immutable task run and `feature-status.yml` as terminal
   evidence. A pointer alone, checkpoint, session report, `decisions.md`, or backlog text
   is recovery context only and must not be promoted to completion proof.
4. Apply
   `.claude/shared/pipeline-contract.md#post-approval-amendment-classification`
   to any referenced post-approval artifact amendment. Invoke
   `.claude/shared/scripts/validate_technical_amendment.py` and require durable
   no-clobber validator evidence plus its atomic checkpoint transition. Only
   that transition may set `cleared_reason: false_technical_approval_gate`,
   `cleared_at`, and `awaiting_user.active: false`, clear stale wait metadata,
   and bind the validator evidence reference/hash. It must not synthesize user
   approval.
5. Summarize the restored feature, current gate, pending task IDs, blockers,
   and the last recommended public command. Ask the user what to continue when
   more than one active feature exists.

## Resume precedence

When there is exactly one resume target, a valid
`execution_approval_projection`, a
qualifying structured technical-amendment record, successful revalidation, and
successful validator evidence with `auto_continue: true`, invoke the previously
approved digest-bound continuation directly. With `auto_continue: false`, clear
the false wait only through the atomic transition and write nonblocking
`resume_ready` with that exact continuation, without reapproval.
This is the only direct-resume case. Multiple resume targets or a genuine
product/authority decision require the user.

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
