---
description: Initialize project with template, git, and GitHub
allowed-tools:
  - Bash(*)
  - Read
  - Edit
  - TodoWrite
---

# Init Project

Read and follow `.claude/shared/pipeline-contract.md` before taking action. Its durable-state rules and completion gate are mandatory.

## 1. Plan and Approval

1. Inspect the target without modifying it. If the target directory is non-empty, fail closed and stop before copying, moving, deleting, committing, or pushing anything.
2. Present a concrete plan, including the target path, existing Git state, intended template source, collision and secrets checks, Git/GitHub actions, rollback, and durable-state location.
3. Get explicit user approval for that plan before implementation. Prefer creating the project in a new, empty directory.

## 2. Safe Initialization

For an empty target, apply the template with portable, platform-appropriate file operations. Do not use a POSIX-only inline script and do not issue a direct destructive command.

An in-place merge into a non-empty target is exceptional and requires separate, explicit user approval. Before any merge:

- Create staging and backup locations outside the tree whose contents could be moved or replaced.
- Inventory every source/target collision and sensitive path (`.env*`, `*.key`, `*.pem`, `credentials.json`, `secrets/`) and show the inventory to the user.
- Define and verify a rollback procedure that restores the original tree from the external backup.
- Copy only the approved files. Never move the project root or bulk-move its contents into a child directory.
- Stop on an unapproved collision, missing backup, failed verification, or rollback uncertainty.

After applying the template, verify `.claude/skills/project-knowledge/` exists. If `.claude/shared/scripts/sync_to_codex.py` exists, run `python .claude/shared/scripts/sync_to_codex.py --project . --apply --prune` and verify that `AGENTS.md`, `.agents/skills/`, and `.codex/agents/` exist.

## 3. Git and GitHub Safety

Initialize or publish Git only if those actions were included in the approved plan. Never automatically commit or push the old project, unreviewed pre-existing files, credentials, or secrets. Before any commit or push, show the exact staged inventory and verify that ignore rules exclude sensitive paths. Repository creation and branch publication require their own explicit approval when they were not already approved.

## 4. Durable State and Completion Gate

Persist the plan, approval, target inventory, collision/secrets findings, backup and rollback details, files applied, verification results, Git actions, and any GitHub URL in the durable state required by `.claude/shared/pipeline-contract.md`.

Do not report completion until the pipeline contract's completion gate passes: the approved target is initialized, required generated runtime files are verified, no unapproved collision or secret was published, rollback evidence exists for an in-place merge, and the durable report is written. Otherwise report the blocked or partial state and the exact recovery step.
