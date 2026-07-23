---
description: |
  Execute all tasks of a feature with team of agents — waves, reviews, commits.

  Use when: "do feature", "execute feature", "execute all tasks", "run feature"
---

# Do All Tasks

Execute all approved tasks of a feature through parent-orchestrated waves. Read and follow `.claude/shared/pipeline-contract.md`; runtime messages and checkpoints cannot weaken its durable gates.

## Step 1: Load Skill

Invoke Skill tool: `Skill(skill: "feature-execution")`

## Step 2: Find Feature

1. User provides feature path or name
2. Verify `user-spec.md` and `tech-spec.md` both record `status: approved`.
3. Require `tasks-manifest.yml` with `status: approved`, then run exactly
   `python .claude/shared/scripts/validate_tasks_manifest.py --project . --manifest work/{feature}/tasks-manifest.yml --report work/{feature}/logs/tasks/manifest-guard-{iteration}.json`
   with exit 0 before fresh execution or
   resume. A legacy atomicity/skill failure creates in-scope remediation tasks,
   preserves WIP/evidence, and revalidates without setting `awaiting_user`.
   Record the immutable guard report ref and SHA-256. Then verify every listed task exists and dependencies are valid.
4. Require `task-files-map.yml`, verify it covers every declared write, and inventory file overlap.
5. If any gate or durable evidence is missing, malformed, stale, or contradictory, fail closed before mutation and report what is needed.

## Step 3: Plan and Approval

The parent builds a bounded execution plan from the approved manifest and file map. It must serialize tasks with file overlap, schedule only disjoint work in parallel, respect available slots (the parent and every running worker count as an active agent), and enforce no nested fan-out. Show the plan to the owner and wait for explicit approval before starting workers. Only after explicit user approval may execution begin.

After that durable approval exists, apply
`.claude/shared/pipeline-contract.md#post-approval-amendment-classification`
only when an approved full-path task or plan artifact changes. An ordinary
technical repair that preserves the approved objective and acceptance remains
inside its task and re-runs only affected targeted checks, with no amendment
hash, amendment manifest, or reapproval. Product/authority changes and
privileged/high-risk lifecycle amendments follow the canonical classifier and
its durable safeguards.

## Step 4: Execute and Record Durable State

Follow the loaded feature-execution skill workflow.
The parent owns waves, scheduling, aggregation, checkpoint/resume decisions, and shared
durable state. A task completes only when
`work/{feature}/logs/working/task-{task-id}/{task-id}.run.yml` passes containment, ID,
digest, and supersedes-chain validation and resolves to the latest approved immutable
`runs/{run-id}.run.yml` record with `final_status: done` and required evidence. A pointer,
decision, commit, message, or checkpoint is not terminal proof by itself.

**Completion gate:**
After every task passes and feature verification succeeds, the parent atomically writes `work/{feature}/feature-status.yml`. Report completion only when it records `status: complete` with QA passed, zero unresolved findings, and post-deploy passed or explicitly waived when applicable. Otherwise preserve and report the last valid durable state.
