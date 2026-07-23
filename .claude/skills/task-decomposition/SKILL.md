---
name: task-decomposition
description: |
  Decompose approved tech-spec into atomic task files with parallel creation and validation.

  Use when: "разбей на задачи", "декомпозиция", "decompose tech-spec",
  "создай задачи из техспека", "/split-tasks"
---

# Task Decomposition

Decompose tech-spec Implementation Tasks into individual task files with parallel creation and validation.

Read `.claude/shared/pipeline-contract.md` before starting. Its F4 -> F5
transition, durable state rules, concurrency budget, and completion gate are
authoritative.

This is a full-path or explicitly requested decomposition workflow. Direct
path skips it. Lean spec path executes from its compact approved plan unless
the user explicitly requests task files or disjoint multi-writer ownership
requires decomposition.

The parent schedules every creator and validator as a bounded worker through the current
runtime. Each receives named role instructions from its `.claude/agents/` source plus the
minimum task context and a disjoint output path. Do not request or claim a model override
unless the runtime returns enforceable binding evidence. Workers never schedule children.

**Input:** `work/{feature}/user-spec.md` and `work/{feature}/tech-spec.md` (both `status: approved`)
**Output:** validated `work/{feature}/tasks/*.md`, `task-files-map.yml`, and an approved `tasks-manifest.yml`
**Language:** Task files in English, communication in Russian

## Phase 1: Create Tasks

1. Ask user for feature name if not provided.

2. Read `work/{feature}/tech-spec.md`. Check frontmatter `status: approved`.
   If not approved — tell user: "tech-spec не утверждён. Сначала запусти `/tech-plan` и доведи до approved." Stop before mutation.

3. Read `work/{feature}/user-spec.md` and require frontmatter `status: approved`.
   Missing, malformed, or non-approved durable evidence fails closed.

4. Check every high-level Implementation Task for atomicity before scheduling workers.
   `/split-tasks` may partition one approved high-level item into multiple
   dependency-linked task files while preserving its objective and acceptance
   criteria. This detailing does not repeat interview or tech-plan approval.
   Atomicity determines the resulting count; use batches of at most 15 for
   scheduling and validation when the decomposition is larger.

5. Note the task template path: `.claude/shared/work-templates/tasks/task.md.template`

6. Read skills/reviewers catalog from [skills-and-reviewers.md](.claude/skills/tech-planning/references/skills-and-reviewers.md) — for passing correct skills/reviewers to task-creators.
   For every `code-writing` task, require and materialize `code-reviewer`.
   Materialize `code-simplifier` only for a broad refactor; otherwise it is
   added later only when code-reviewer flags complexity or readability. Empty
   reviewers or a missing code-reviewer make task creation fail closed.

7. The parent schedules [`task-creator`](.claude/agents/task-creator.md) workers through the
   current runtime in **bounded batches**. Batch size is `min(3, available child-agent slots)` and
   must never exceed the runtime's available slots. The parent is the scheduler;
   creators do not spawn children.
   Pass each task-creator:
   - feature_path, task_number, task_name
   - template_path: `.claude/shared/work-templates/tasks/task.md.template`
   - files_to_modify, files_to_read (from tech-spec)
   - depends_on, wave, skills, reviewers, verify (from tech-spec)
   - teammate_name (optional human-readable worker label for logs/reports only; never use it for routing or as evidence of a bound runtime role/model)
   Each task-creator copies the template to `tasks/{N}.md` first, then edits each section in place. This ensures no sections are skipped.
   Each creator writes only its own task file and returns a structured result:
   `task_id`, `task_path`, `depends_on`, `wave`, and
   `task_files_map_entry` (`task_id` plus `files_to_modify`). A creator **MUST
   NOT** write `task-files-map.yml` or `tasks-manifest.yml`.

8. Confirm every creator returned a unique task path and map entry. The parent aggregates the validated complete set into:
   - `work/{feature}/task-files-map.yml`; and
   - `work/{feature}/tasks-manifest.yml`, initially `status: draft`, using
     `.claude/shared/work-templates/tasks/tasks-manifest.yml.template`.
   Shared files have exactly one writer. Write each to a same-directory
   temporary file and atomically rename it into place only after the full YAML
   parses and contains every task.
9. Git commit: `draft(tasks): create {N} tasks from tech-spec for {feature}`

**Checkpoint:**
- [ ] All `tasks/*.md` files created
- [ ] Each task-creator returned a file path and `task_files_map_entry`
- [ ] Parent atomically wrote the complete draft manifest and file map
- [ ] Draft committed

## Phase 2: Validation (up to 3 iterations)

Tech-spec was already validated by 4 validators. This phase checks only: (1) task-creator correctly expanded tasks by template, (2) no mismatches with real code appeared during detailing.

### Validators

To launch both in bounded batches within available agent slots, the parent schedules both
named validator roles through the current runtime. Validators write disjoint reports; only
the parent aggregates results.

[`task-validator`](.claude/agents/task-validator.md) — Template Compliance + AC/TDD carry-forward:
- Batch: 5 tasks per call
- Pass: feature_path, task_numbers array, batch_number, iteration
- Immutable report: `logs/tasks/task-validator-batch{N}-iteration-{iteration}.json`
- Reject any `code-writing` task whose empty reviewers or explicit list omits
  `code-reviewer`; fail closed rather than supplying a runtime fallback

[`reality-checker`](.claude/agents/reality-checker.md) — Reality & Adequacy:
- Batch: 3 tasks per call
- Pass: feature_path, task_numbers array, batch_number, iteration
- Immutable report: `logs/tasks/reality-checker-batch{N}-iteration-{iteration}.json`

### Process

1. Initial round: validate all tasks (task-validator batches of at most 5,
   reality-checker batches of at most 3), scheduling only as many calls at once
   as available slots permit.
2. Read JSON reports, collect findings.
   Critical/Major atomicity or skill-task mismatch findings are blocking until
   corrected. Parent aggregation, total task count, overall decomposition
   approval, and summary dispositions cannot clear them.
3. If issues are found, the parent schedules [`task-creator`](.claude/agents/task-creator.md) in fix mode for each affected task:
   - Pass: same inputs as creation + `mode: fix` + `findings` from validators
   - task-creator reads existing task, applies fixes, overwrites file
   - collect the updated structured entry; the parent atomically refreshes the
     shared manifest/map if declared metadata changed
4. After each validation round, git commit: `chore(tasks): validation round {N} — {summary}`
5. Re-validate **only changed tasks**. Do not rerun validators for unchanged,
   already-approved tasks. Repeat steps 2-5 for a maximum of 3 individual
   validation iterations.
6. If problems remain after 3rd iteration — show user: "Вот что осталось — давай решим вместе."

### Cross-Task Integration Check

After individual validation passes, run exactly **one cross-task pass**:

1. The parent schedules both validators over the complete manifest, in bounded calls if the
   context does not fit one call:
   - `task-validator` — focus: shared resource ownership (one owner, consumers depend_on owner), no competing instances in same wave
   - `reality-checker` — focus: duplicate heavy resource init, hidden dependencies, inconsistent approaches across tasks

2. If issues are found, fix affected tasks and individually re-validate only
   those changed tasks. The parent verifies that the reported cross-task
   constraints are resolved from the updated entries. Record a split as
   `resolution: resolved_by_split` with the exact validator report reference,
   original finding ID, source task ID, and at least two distinct replacement task IDs present
   in the manifest and file map. The approved revalidation explicitly `supersedes` the exact
   source report/finding and covers every replacement with current task-set/map digests and
   `validated_task_sha256`. Historical split evidence includes `source_task_sha256`, matches that
   source ID/hash in the strict diagnostic report, and cites a blocking Critical/Major
   `atomicity` or `skill_task_mismatch` finding;
   waiver or accepted-as-is dispositions do not resolve atomicity.

3. Do not launch a second cross-task validator pass. Unresolved cross-task
   findings fail the completion gate and are surfaced to the user.

**Checkpoint:**
- [ ] Both validators: status=approved with no unresolved Critical/Major atomicity or skill-task mismatch findings
- [ ] One cross-task pass completed with no unresolved cross-task conflicts

## Phase 3: Present to User

1. Summary: task count, waves, dependencies, validation results (iterations, issues found/fixed).
2. Obtain initial user approval before rendering approval fields.
3. Render the complete immutable final approved manifest bytes to a same-directory temporary
   file, including status, approval/amendment references, current task count, canonical task
   paths/dependencies, file-map pointer, and immutable validation reports. Guard output is
   external evidence and never appears in these bytes.
4. Validate the staged physical bytes while binding the report to the logical canonical path:
   `python .claude/shared/scripts/validate_tasks_manifest.py --project . --manifest work/{feature}/.tasks-manifest.final.tmp --logical-manifest work/{feature}/tasks-manifest.yml --report work/{feature}/logs/tasks/manifest-guard-{iteration}.json`.
   Require exit 0, then atomically replace canonical with the IDENTICAL staged bytes. A nonzero
   result leaves canonical bytes unchanged. There is no rerun, self-reference, or post-guard mutation.
5. Store the immutable guard report ref and SHA-256 only in external checkpoint/approval-entrypoint
   evidence, then invoke only the approval-owned continuation.
5. Git commit: `chore(tasks): task decomposition approved for {feature}`
6. Suggest `/do-task {task-id}` for one dependency-ready task or
   `/do-all-tasks` for parent-controlled feature execution.

**Checkpoint:**
- [ ] Summary presented to user
- [ ] User approved task decomposition
- [ ] Durable `tasks-manifest.yml` records `status: approved`
- [ ] Approval committed

## Final Check

- [ ] All phases completed (tasks created, validation passed)
- [ ] All tasks match template (frontmatter: status, depends_on, wave, skills, reviewers, teammate_name); any `teammate_name` is label-only with no routing or role/model-binding semantics
- [ ] Every `code-writing` task declares `code-reviewer`; broad refactors also declare `code-simplifier`
- [ ] Validation: both validators passed; blocking atomicity and skill-task mismatch findings have clean revalidation evidence
- [ ] Atomicity determined task count; scheduling/validation batches contain at most 15 tasks
- [ ] Creation and validation used bounded batches and re-ran only changed tasks
- [ ] Parent atomically aggregated a complete `task-files-map.yml`
- [ ] Exactly one cross-task pass completed
- [ ] Exact final approved manifest bytes passed the guard and atomically replaced canonical bytes
