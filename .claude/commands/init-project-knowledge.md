---
description: Populate or explicitly revise durable Project Knowledge documentation.
---

# Init Project Knowledge

Read `.claude/shared/pipeline-contract.md` first. Follow its durable state,
explicit approval, and completion gate rules.

## Existing-content gate

Inspect `.claude/skills/project-knowledge/references/` before invoking any
planning skill. Project Knowledge is populated when its core files contain
substantive project-specific content rather than placeholders.

- If populated Project Knowledge already exists, stop and ask whether the user
  explicitly intends a revision/update. Do not overwrite, reinitialize, or
  downgrade approved documentation based on an ambiguous invocation.
- Continue with update mode only after explicit revision intent is confirmed.
  Preserve unaffected approved content and identify the files in scope.
- If Project Knowledge is absent or placeholder-only, confirm the initialization
  scope with the user before creating it.

## Execute and close the gate

After confirmation, load and execute the `project-planning` skill. Persist its
progress in the canonical durable artifact defined by
`.claude/shared/pipeline-contract.md`; interrupted work remains resumable.

Do not report success until all required Project Knowledge files pass the
project-planning validation and the durable status is `approved` or `complete`
as required by the contract completion gate. If validation or approval is
missing, report the exact pending gate without marking the operation complete.

When initialization or the explicitly requested update is complete, summarize
the affected documentation and offer the next public command: `/interview`.
Do not expose an internal skill name as the user's next step.
