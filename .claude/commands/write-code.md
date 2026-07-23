---
description: Write code with quality process - TDD, reviews (uses code-writing skill)
allowed-tools:
  - Skill
---

# Instructions

Read and follow `.claude/shared/pipeline-contract.md` before taking action. Its durable-state rules and completion gate are mandatory.

Route the request through
`.claude/shared/pipeline-contract.md#risk-proportional-delivery-paths`:
direct path for low-risk local S, lean spec path for Standard S/low-risk M,
and full path for L, high-risk triggers, or an explicit user request.

1. Inspect the request and present a concrete implementation and validation plan.
2. Wait for explicit approval from the user for that plan.
3. After approval, delegate implementation only to the `coder` agent. The Team Lead must not write code or edit project code.
4. Require the `coder` to load and follow the `code-writing` skill, including its testing and review workflow.
5. Collect test output and reviewer evidence. If review finds actionable defects, return them to `coder` and retain the evidence for the next review round.

For full-path work, run exactly
`python .claude/shared/scripts/validate_tasks_manifest.py --project . --manifest work/{feature}/tasks-manifest.yml --report work/{feature}/logs/tasks/manifest-guard-{iteration}.json`
with exit 0 before fresh execution or
resume. A legacy atomicity/skill failure is repaired through parent-owned
in-scope remediation tasks and revalidation without setting `awaiting_user`. Record the immutable
guard report ref and SHA-256.

The initial plan still requires explicit approval. An ordinary technical repair
that preserves the approved objective, acceptance, scope, and risk stays in the current task in any delivery path:
run affected targeted checks with no amendment hash, no amendment manifest, and no reapproval.
A product/authority or scope change requires a user decision. New high risk
promotes to full before mutation. An already-approved full-path repair skips
amendment ceremony but retains all security, QA, terminal, and native safeguards.
Scope-changing artifacts apply
`.claude/shared/pipeline-contract.md#post-approval-amendment-classification`
and retain its parent-owned validator, permission, and continuation safeguards.

## Durable State and Completion Gate

Persist the approved plan, approval evidence, coder result, changed-file inventory, test output, reviewer verdicts, remediation rounds, and final status as durable state required by `.claude/shared/pipeline-contract.md`.

Do not report completion until the pipeline contract's completion gate passes: the approved scope was implemented by `coder`, required tests passed, reviewer findings were resolved or explicitly accepted, and the durable result was written. Otherwise report a blocked or partial state with the remaining evidence or action.
