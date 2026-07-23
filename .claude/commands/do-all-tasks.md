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
3. Require `tasks-manifest.yml` with `status: approved`. Then verify every listed task exists and dependencies are valid.
4. Require `task-files-map.yml`, verify it covers every declared write, and inventory file overlap.
5. If any gate or durable evidence is missing, malformed, stale, or contradictory, fail closed before mutation and report what is needed.

## Step 3: Plan and Approval

The parent builds a bounded execution plan from the approved manifest and file map. It must serialize tasks with file overlap, schedule only disjoint work in parallel, respect available slots (the parent and every running worker count as an active agent), and enforce no nested fan-out. Show the plan to the owner and wait for explicit approval before starting workers. Only after explicit user approval may execution begin.

After that durable approval exists, apply
`.claude/shared/pipeline-contract.md#post-approval-changes`
only when an approved full-path task or plan artifact changes. An ordinary
technical repair that preserves the approved objective and acceptance remains
inside its task under the existing approval and re-runs only affected targeted
checks — no reapproval needed. Product/authority changes stop for
the owner before mutation.

## Step 4: Execute and Record Durable State

Follow the loaded feature-execution skill workflow.
The parent owns waves, scheduling, aggregation, checkpoint/resume decisions, and shared
durable state. A task completes only when its required tests and reviews pass and the
parent records `done` in the task's frontmatter and in `checkpoint.yml`. A commit,
message, or chat progress is not terminal proof by itself.

**Completion gate:**
After every task passes and feature verification succeeds, the parent atomically writes `work/{feature}/feature-status.yml`. Report completion only when it records `status: complete` with QA passed, zero unresolved findings, and post-deploy passed or explicitly waived when applicable. Otherwise preserve and report the last valid durable state.
