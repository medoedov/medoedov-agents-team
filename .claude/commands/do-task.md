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

Run exactly `python .claude/shared/scripts/validate_tasks_manifest.py --project . --manifest work/{feature}/tasks-manifest.yml --report work/{feature}/logs/tasks/manifest-guard-{iteration}.json`
and require exit 0 before fresh execution
or resume. Route a legacy atomicity/skill failure to the parent-owned in-scope
remediation decomposition and revalidate without setting `awaiting_user`. Record the immutable
guard report ref and SHA-256.

An ordinary technical repair that preserves the approved objective and
acceptance stays inside the selected task. Re-run affected targeted checks with
no amendment hash, no amendment manifest, and no reapproval. Product/authority
changes return to the user.

For a privileged/high-risk post-approval edit to the selected task or plan artifact, apply
`.claude/shared/pipeline-contract.md#post-approval-amendment-classification`.
The adapter passes the structured amendment reference to `task-execution`; it
does not independently classify, approve, or create a conversational gate.
The parent invokes
`.claude/shared/scripts/validate_technical_amendment.py`; only parent-owned
validator evidence reference/hash after its atomic checkpoint transition may
authorize mutation, clearing, `resume_ready`, or the exact approval-owned
continuation.

Delegate the complete workflow to the `task-execution` skill. This command is only an
adapter: it MUST NOT duplicate execution steps, update lifecycle artifacts directly, or
infer completion from chat or file existence.
