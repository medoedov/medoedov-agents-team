---
description: |
  Finalize a completed feature: read specs and decisions, update project knowledge files,
  archive feature directory to work/completed/.

  Use when: "фича готова", "заверши фичу", "done", "финализация", "закрой фичу", "перенеси в completed"
---

# Done — Finalize Feature

Read and follow `.claude/shared/pipeline-contract.md` before taking action. `/done` archives only a durably complete feature; conversation, commits, decisions, and checkpoints are supporting evidence, not terminal proof.

## Step 1: Load Documentation Skill

Use Skill tool: `documentation-writing`

## Step 2: Identify Feature

User typically provides feature directory with the command (e.g., `/done work/my-feature`).
- If provided → use it
- If not → ask: "Which feature to finalize? Provide path to work/{feature}/ directory."

## Step 3: Read Feature Artifacts

Read these files from the feature directory:
1. `user-spec.md` — what was planned
2. `tech-spec.md` — how it was implemented
3. `decisions.md` — what decisions were made during implementation
4. `tasks-manifest.yml`, task current-run pointers with their immutable run records, and
   `feature-status.yml` — durable lifecycle evidence

If `decisions.md` is missing or sparse, use `git log --oneline` for feature-related commits to understand what changed.

**Strict completion gate:** fail closed unless `feature-status.yml` records all applicable terminal evidence:

- `status: complete`
- `qa: passed`
- `unresolved_findings: 0`
- `post_deploy: passed`, or `post_deploy: waived` with an explicit durable waiver when post-deploy is applicable but intentionally waived
- every task in the approved manifest has a validated `{task-id}.run.yml` pointer that
  resolves to the latest approved non-superseded immutable run with `final_status: done`

Missing, malformed, stale, or contradictory evidence stops `/done` before Project Knowledge edits or archival. An owner request to stop or finalize incomplete work may be recorded as `status: aborted` with explicit `waived` gate metadata where appropriate, but it must not be represented as completed and must not be archived under `work/completed/`.

## Step 4: Update Project Knowledge

If `.claude/skills/project-knowledge/references/` does not exist or is empty — skip this step, inform the user that project knowledge has not been initialized.

Otherwise, read current PK files and update only those affected by the feature:
- `architecture.md` — new components, changed structure, data model / schema changes
- `patterns.md` — new project-specific patterns, testing approaches, business rules
- `deployment.md` — deployment or monitoring changes
- If the project has a backlog file, note any status updates for the user

Apply quality principles from documentation-writing skill: no code examples, no obvious content, only project-specific information.

## Step 5: Archive

Archive atomically from `work/{feature}/` to `work/completed/{feature}/` only after the strict completion gate passes.

Before moving, check for a destination collision:

- If the destination does not exist, create its parent if needed and perform the atomic archive move.
- If the source is already absent and the destination contains the same validated complete feature and evidence, treat the operation as idempotent success and make no duplicate changes.
- Otherwise, a destination collision fails closed. Never overwrite, merge into, rename around, or delete an existing destination automatically.

## Step 6: Commit & Report

1. Commit PK file changes and feature archive move.
   ```
   docs: update project knowledge after {feature-name}
   ```

2. Report to user:
   - What was done (brief summary from specs)
   - What PK files were updated and what changed
   - Feature archived to `work/completed/{feature}/`

## Self-Verification

- [ ] Documentation-writing skill loaded
- [ ] Feature artifacts read and understood
- [ ] `feature-status.yml` and every resolved immutable task run passed the strict completion gate
- [ ] Incomplete override, if any, recorded as aborted/waived and never represented as completed
- [ ] PK files updated (only affected ones)
- [ ] Destination collision check passed and archive was atomic/idempotent
- [ ] Feature archived to work/completed/ only when complete
- [ ] Changes committed
- [ ] Report delivered to user
