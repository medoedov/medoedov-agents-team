---
description: |
  Execute task from tasks/*.md with quality gates.

  Use when: "выполни задачу", "сделай таску", "do task", "execute task", "запусти задачу"
---

# Do Task

This is the full-task adapter for approved decomposed work. It retains
privileged/high-risk and full lifecycle safeguards.

Read `.claude/shared/pipeline-contract.md` and apply the `/do-task` row. Its preconditions,
durable output/state, completion gate, and next allowed transitions are normative and fail
closed.

An ordinary technical repair that preserves the approved objective and
acceptance stays inside the selected task under the existing approval. Re-run
affected targeted checks and continue — no reapproval needed. Product/authority
changes return to the user before mutation. See
`.claude/shared/pipeline-contract.md#post-approval-changes`.

Delegate the complete workflow to the `task-execution` skill. This command is only an
adapter: it MUST NOT duplicate execution steps, update lifecycle artifacts directly, or
infer completion from chat or file existence.
