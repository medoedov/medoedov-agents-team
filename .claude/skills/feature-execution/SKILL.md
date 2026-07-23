---
name: feature-execution
description: |
  Orchestrate feature delivery as team lead: spawn agents by wave,
  manage review cycles (max 3 rounds), commit per wave.

  Use when: "выполни фичу", "do feature", "execute feature", "запусти фичу",
  "выполни все задачи", "execute all tasks"
---

# Feature Execution

Team lead orchestrates feature delivery. You are a dispatcher: schedule agents, track progress, commit approved changes, aggregate durable evidence, and escalate issues. Delegate implementation and review work, but verify lifecycle transitions from repository state rather than status messages alone.

Read and follow `.claude/shared/pipeline-contract.md` before taking action. The parent orchestrator owns execution plans, waves, scheduling, shared durable state, aggregation, retry decisions, and resume. Runtime adapters may implement workers with Claude teams or Codex subagents, but this workflow must not depend on a team directory, `team_name`, model/spawn arguments, a shared inbox, or a long-running background watchdog.

## Role Boundary

Feature execution is full-path only and does not implement a lean workflow.
Direct and lean paths execute through `/write-code` with ordinary single-turn
coder/reviewer calls and parent aggregation.

An already-approved full-path ordinary technical repair that preserves the approved
objective, acceptance, scope, and risk stays in the current task. Re-run only affected targeted checks:
no amendment hash, no amendment manifest, and no reapproval. A
product/authority or scope change stops for the user. New high risk promotes
before mutation. The repair retains all full-path security, QA, and terminal gates.

**You CAN:**
- Read task frontmatter (limit=15 lines) to check status and metadata
- Read decisions.md to track progress
- Read `tasks-manifest.yml`, `task-files-map.yml`, current-run pointers with their immutable records, and `feature-status.yml` to enforce lifecycle gates
- Run git commands (status, diff, log, add, commit)
- Spawn and message agents
- Update parent-owned `checkpoint.yml` and `feature-status.yml`

The parent/root is the exclusive git index and commit writer. Workers return a
scoped changed-file inventory, diff, and verification results; after validating
ownership and gates, the parent uses path-scoped staging and creates the
corresponding implementation, review-fix, evidence, or wave commit.

**You CANNOT:**
- Read full task files (teammates do this)
- Read source code or diffs (teammates and reviewers do this)
- Write or edit any code files
- Make implementation decisions — only routing and escalation

## Phase 1: Initialization

Before creating an execution plan or resuming work, require all of the following durable inputs:

- `user-spec.md` and `tech-spec.md` both record `status: approved`.
- `tasks-manifest.yml` records `status: approved` and lists every task to execute.
- `task-files-map.yml` covers every declared write and agrees with the manifest.
- Dependencies are valid and no task count or lifecycle gate from `.claude/shared/pipeline-contract.md` is violated.
- Every `code-writing` task declares `code-reviewer`; `code-simplifier` is
  present only for a broad refactor or after code-reviewer flags complexity or
  readability.
- The feature-audit task set matches the [catalog policy](../tech-planning/references/skills-and-reviewers.md#risk-based-feature-audit-policy), and the Final Wave contains mandatory QA.

Before fresh execution or resume, run exactly
`python .claude/shared/scripts/validate_tasks_manifest.py --project . --manifest work/{feature}/tasks-manifest.yml --report work/{feature}/logs/tasks/manifest-guard-{iteration}.json`
and require exit 0; record its immutable report ref and SHA-256. A legacy approved manifest
that fails atomicity or skill evidence is a pre-development gate regression.
Preserve existing WIP and evidence, partition the affected task into
dependency-linked remediation tasks within the already approved objectives and
acceptance, update task/file ownership, and rerun the manifest guard. This
recovery must not set `awaiting_user`.

If any input is missing, malformed, stale, or contradictory, fail closed before mutation and report the unmet gate.
Empty reviewers on a `code-writing` task fail closed; required `code-reviewer`
must already be materialized in the approved task. Materialize
`code-simplifier` only for a broad-refactor trigger, or add it after a
complexity/readability finding.

### High-risk role instruction gate

Before any high-risk implementation spawn, the parent/root resolves the role through the
active runtime. In Codex, read `.claude/codex/agent-profiles.toml` and validate that the
requested role maps to the matching `.claude/agents/<role>.md`; in Claude Code, retain its
native agent role/model binding. In every runtime, explicitly instruct the isolated child
to read and follow that exact role source before work starts. The task envelope must bound
scope, allowed writes, required evidence, review/test gates, ownership, and deadline. A
`task_name` label, child self-report, or TOML existence is insufficient role-binding
evidence.

In Codex, profile model and effort remain desired preferences. A generic/custom selectable
worker may pass model/reasoning effort only when the active schema supports those selectors
and the context fork is none or bounded. Record the requested selector and acceptance or
failure. A successful spawn proves selector acceptance, not an independent resolved-model
trace; record a resolved trace only if exposed. Runtime-managed/fixed semantic roles remain
locked: invoke the native fixed-role spawn with `agent_type="<exact-role>"`; it omits
model/reasoning overrides. One generic role-bound fallback is permitted only after that
native fixed-role spawn returns an explicit unsupported-model error. Missing or unverified
advisory metadata never qualifies. The fallback must use the same canonical role source and
same bounded envelope. If no selector is available, record model binding as `unsupported` or
`unverified`.

Codex uses a single-turn spawn with no filesystem receipt for ordinary
low-risk coder and read-only reviewer work. Authorization handshakes and
parent-owned spawn receipts remain for privileged/destructive/high-risk
effects and matching lifecycle gates. Follow the runtime contract for the
exact boundary.

For fixed-role model fallback and native permission, follow
`.claude/codex/runtime-contract.md#approval-authority-and-native-permission`; the worker,
not checkpoint state or a copied chat phrase, issues any required native tool request.

Fail closed before code writes when the canonical role source is missing, mismatched, or
unreadable; the child did not receive the exact role instruction and bounded envelope; the
isolated spawn failed; or required implementation/review evidence is absent. Lack of a
runtime model selector by itself is not a role-binding failure and does not reduce the
mandatory implementation, review, security, deployment, QA, or terminal gates.

### Immutable run and pointer gate

Each completed task has an immutable terminal run record at
`work/{feature}/logs/working/task-{task-id}/runs/{run-id}.run.yml`. It requires
`run_id`, matching task ID, `approval_status: approved`, `final_status: done`,
evidence, and optional `supersedes:`. `Final_status: done` is immutable: never
overwrite a terminal record.

`work/{feature}/logs/working/task-{task-id}/{task-id}.run.yml` is the atomically
replaced canonical current-run pointer, not terminal source of truth. It contains
`current_run_id`, `current_run_path`, `projected_status`, and `evidence_digest`.

Every dependency, resume, and projection gate must validate path containment
under the same task's `runs/` directory, require the immutable record's run_id
matches the pointer and task ID, and require its evidence digest matches the
pointer. Enumerate the contained run records and follow the supersedes chain to
the latest approved non-superseded run; reject traversal, symlinks, cycles,
missing ancestors, multiple leaves, or a pointer to another run.

The parent owns the monotonic marker protocol. It writes supporting and
projection artifacts first, writes and verifies the immutable terminal run
record, then atomically replaces the canonical current-run pointer. The pointer
is written last. On a pre-pointer interruption, the new run remains unselected
and readers continue using the old valid pointer; recovery never edits a
terminal record. Incomplete projections are repaired idempotently from the
resolved immutable run.

0. Check `work/{feature}/logs/checkpoint.yml`:
   - Before treating `awaiting_user.active: true` as a real user wait, follow
     its structured `amendment_ref`. Invoke
     `.claude/shared/scripts/validate_technical_amendment.py` against the
     current execution plan, amendment, checkpoint, immutable gate manifest,
     ledger, classification evidence, and terminal gate evidence. Require its
     no-clobber validator evidence and atomic checkpoint transition before
     consuming the bound evidence reference/hash. That transition alone sets
     `cleared_reason: false_technical_approval_gate`, `cleared_at`, and
     `active: false`. When the projection has canonical
     `auto_continue: true`, invoke only its exact digest-bound `continuation`.
     When it is false, preserve that continuation in nonblocking
     `resume_ready` without reapproval. It must not synthesize user approval or
     clear from the question.
   - `last_completed_wave > 0` → this is a resume after context compaction.
     Read checkpoint, then read `work/{feature}/decisions.md` to confirm what was actually completed.
     For tasks in the resumed wave, resolve the canonical current-run pointer
     `work/{feature}/logs/working/task-{task-id}/{task-id}.run.yml`. Skip a task only when its
     validated immutable current record says `final_status: done` and required evidence is present.
     Checkpoint is not terminal proof. decisions.md is not terminal proof. Reconcile the checkpoint
     against resolved immutable current runs, then resume only dependency-ready unfinished tasks.
     Report to user: "Resuming from wave {N}. Waves 1-{N-1} completed."
     Also check stall_state in checkpoint:
     - If `stall_state.active == true AND reset_at <= now` -> resume mode.
       Re-spawn tasks from `stall_state.pending_tasks`, resume from `stall_state.last_active_wave`.
       Clear stall_state after successful re-spawn (set active: false).
     - If `stall_state.active == true AND reset_at > now` -> rate-limit window not elapsed.
       Report to user: "Rate-limit window not yet elapsed. Resume at {reset_at}."
   - `last_completed_wave: 0` is fresh only when no active or canonical execution evidence exists.
     Reconcile all task run records, spawn receipts, and worker
     results first. If wave-1 evidence exists, resume without spawning duplicate workers,
     even though the supporting checkpoint still says zero.

1. Read `work/{feature}/tech-spec.md` and `work/{feature}/user-spec.md`
2. Read frontmatter of all task files in `work/{feature}/tasks/` — extract fields:

   | Field | Purpose |
   |-------|---------|
   | `status` | planned → in_progress → done |
   | `wave` | Parallel execution group number |
   | `depends_on` | Task numbers that must be done first |
   | `skills` | Skills the teammate loads |
   | `reviewers` | Reviewer agents to spawn (source of truth) |
   | `verify` | Verification types: [smoke], [user], [smoke, user], or [] (optional) |

   Build waves by the `wave` field as candidate concurrency groups. Within a wave, only tasks with disjoint writes from `task-files-map.yml` may run in parallel; file overlap forces serialization.

3. Build the execution plan following
   `.claude/shared/work-templates/execution-plan.md.template`. Before approval,
   write an immutable amendment gate manifest whose exact allowed gate IDs map
   to every approved objective/task; record its project-relative reference and
   exact byte SHA-256 in `execution_approval`.
4. Save to `work/{feature}/logs/execution-plan.md`
5. Show plan to user, wait for approval
6. Only after explicit user approval, initialize the parent-owned checkpoint
   and scheduling state. Store only the digest-bound
   `execution_approval_projection`; every canonical approval field must match
   the plan and the projection digest must validate. Do not start workers
   before approval.
7. Determine current runtime capacity. This project has a configured cap of five. Compute
   `confirmed free children = min(configured cap - current active agents (including root),
   live runtime reported free child slots, explicitly named workload-specific cap)`.
   Never schedule more workers than available slots or than that result; the parent and every running worker or reviewer each count as an active agent.
8. Update `work/{feature}/logs/checkpoint.yml`: set `total_waves` from the execution plan. The checkpoint supports resume but is not task or feature completion evidence.

No nested fan-out: only the parent schedules workers and reviewers. A child worker or reviewer must not spawn additional agents. Optional monitoring may run only when the runtime exposes the capability and capacity permits; it is not a required long-running background process and never owns resume.

**Checkpoint:** execution plan explicitly approved, inputs validated, capacity bounded, checkpoint initialized.

### Post-approval amendment handling

After the initial approval checkpoint, apply
`.claude/shared/pipeline-contract.md#post-approval-amendment-classification`
only when an already-approved task or plan artifact changes. Do not duplicate
the exhaustive classifier here.

For a technical result, the parent writes the canonical amendment record,
updates the affected task/plan artifacts and file map, persists the stable
repair-loop ledger record, runs every recorded required gate, then invokes
`.claude/shared/scripts/validate_technical_amendment.py` with its atomic
transition. Only the parent may consume its successful validator evidence
reference/hash, clear `awaiting_user`, set `resume_ready`, or invoke the
approval-owned continuation. A child must not classify, clear, or resume. A
product/authority result returns to the user. Implementation review exhaustion
follows the bounded remediation path below before it may become
`technical-repair-exhausted`.

Runtime worker/reviewer retries, scheduling/capacity adjustments, and
fixed-role fallback that preserve the same execution contract remain under
`.claude/codex/runtime-contract.md`; do not create a technical-amendment record
for them.

## Phase 2: Execute Wave

1. Find dependency-ready tasks for the current wave whose resolved immutable current run
   does not record `final_status: done`.
2. Use `task-files-map.yml` to compare declared writes before scheduling. Any file overlap requires the parent to serialize those tasks even when they share a wave; only disjoint tasks may run concurrently.
3. Mark the selected tasks active in parent-owned state, then schedule workers and required reviewers without exceeding available slots:

   Give each worker a stable descriptive label for reporting only; runtime identity is not durable state.

   **Worker** — use the task's declared executor/skills through the runtime's supported agent mechanism. Do not pass implementation scheduling to the child and do not rely on model-specific or team-specific spawn arguments.

   Prompt template:

   ```
   You are "{name}" executing task {N}.

   Read task: {feature_dir}/tasks/{N}.md
   Load skills listed in task frontmatter. Follow the loaded skill workflow.

   If the task requires user action, return a blocking request to the parent.
   The parent owns user communication and durable approval state.

   {reviewers_block}

   Before yielding, process all review evidence supplied for this round and report any unresolved blocker.

   After implementation or a fix attempt:
   - Write one unique non-terminal worker-result artifact at
     {feature_dir}/logs/working/task-{task-id}/{task-id}.worker-result-{attempt-id}.yml.
      Include changed files, scoped diff, tests and smoke evidence, unresolved blockers,
      and the role-source path. Privileged/high-risk runs also include the
      non-authoritative heading/version acknowledgement plus `receipt_id` and
      `receipt_path` copied from the parent-owned spawn receipt. Ordinary runs
      omit receipt fields. Selector acceptance/failure, agent_type binding, and
      source/envelope validation remain parent-owned.
   - The worker MUST NOT write task frontmatter, immutable `runs/{run-id}.run.yml`, the
     canonical current-run pointer `{task-id}.run.yml`, decisions.md, checkpoint.yml, or
     feature-status.yml. Those are parent-owned shared or terminal state.
   - Return the worker-result path and evidence summary to the parent. The artifact is
     non-terminal and the message itself is not completion proof.

   Feature dir: {feature_dir}
   ```

   **{reviewers_block}** — include only when task has reviewers (not `reviewers: none`):

   ```
   Required reviewer roles: {reviewer_names}.

   Review process — after implementation or fix attempt is ready for review, follow this
   review process (overrides review steps from loaded skills):
   1. Run `git diff -- <your files>` and collect the list of changed files + full diff output.
   2. Return the changed-file list and diff to the parent for reviewer scheduling.
   3. Reviewers write canonical reports to `{feature_dir}/logs/working/task-{task-id}/{reviewer}-round{N}.json`; the parent collects the report paths.
   4. Apply parent-routed findings. After fixes, return an updated diff for the next bounded round.
   5. This unchanged task attempt is capped at three rounds; there is no round
      4. Unresolved findings then enter parent-owned remediation routing.

   Review counting is exact: R1 runs all required reviewers; R2 runs only affected
   Critical/Major reviewers; R3 is reserved for the final integrated all-required-reviewers
   gate (or R1 is final when clean). There is no R4; any finding after R3 routes to remediation.
   The parent deduplicates findings by stable semantic identity.
   The full-path lifecycle is capped at three rounds.

   Round synchronization: the parent waits for all required R(N) reports before scheduling R(N+1).
   Missing evidence is a blocker; the parent decides whether to retry, replace a reviewer, or escalate.

   Git handoff:
   1. Return the scoped changed-file inventory, full diff, and test results to the parent.
   2. The parent validates declared ownership, performs path-scoped staging, and creates
      commits only after the corresponding implementation or review gate passes.
   ```

   If task has `reviewers: none`, first fail closed when `skills` includes `code-writing`.
   For other skills, omission is valid only when that skill explicitly allows omission and
   names its default reviewers, or when the approved task explicitly identifies the worker
   as the review (for example, a selected audit task). Then skip reviewer scheduling. The
   worker completes declared checks and returns its unique non-terminal result; only the
   parent/root may write canonical or shared state.

   **Each reviewer** (when present) — the parent schedules a bounded single review round with the reviewer role declared by the task. Reviewers do not spawn workers or mutate shared lifecycle state.

   Prompt template:

   ```
   You are reviewer "{name}" for task {N}.

   Read specs: {feature_dir}/user-spec.md, {feature_dir}/tech-spec.md
   Read task: {feature_dir}/tasks/{N}.md

   The parent supplies an immutable changed-file list and diff for this round.
   1. Perform the declared review on that evidence.
   2. Write JSON report to: {feature_dir}/logs/working/task-{task-id}/{reviewer}-round{N}.json
   3. Return the report path to the parent; do not append shared state or spawn another agent.
   ```

4. The parent waits for the bounded set of active workers/reviewers, aggregates the unique
   worker-result artifacts and disjoint reviewer reports, and schedules further disjoint
   work only when slots become available. A worker message saying "Task complete" is
   advisory and a worker-result is explicitly non-terminal.
5. Only the parent/root validates the worker-result, tests, acceptance criteria, binding
   evidence, and reviewer reports. It then executes the monotonic marker protocol through
   the immutable run and pointer gate above.
   Reviewer-created reports remain immutable evidence that the parent verifies; the parent
   does not rewrite them. Later revision allocates a new `run_id`, writes a distinct immutable
   record with `supersedes: <prior-run-id>`, and updates the pointer only after validation.

### Feature Audit Wave tasks

The Feature Audit Wave is conditional and risk-based. Derive its exact task set from the catalog policy linked during initialization, using the approved specs and final changed-file inventory. Reject any mismatch between that selection and the planned audit tasks. This is the only feature-level audit pass; there is no additional always-on acceptance-review wave. Final QA is mandatory whether audits run or are skipped.

Scheduled audit tasks have `reviewers: none` because each auditor worker is the review. If
multiple audits trigger, the parent checks the live agent inventory and schedules them in
bounded batches. This project has a configured cap of five; compute
`confirmed free children = min(configured cap - current active agents (including root),
live runtime reported free child slots, explicitly named workload-specific cap)`. Never
schedule beyond confirmed free child slots or live runtime availability. Auditors do not
fan out.

Each scheduled auditor:
- Reads decisions.md to understand what was done in each task
- Reads all source files listed in tech-spec "Files to modify" across all implementation tasks
- Reviews the final integrated state holistically (full files, not diffs)
- Writes a disjoint report to `{feature_dir}/logs/working/audit/{auditor-name}.json`
- Returns the report path and summary; the parent writes any shared decisions.md entry

After all scheduled audit reports:
- All clean and each audit task's resolved immutable current run says `final_status: done` with its report linked → proceed to Final Wave
- Issues found → spawn a fixer with `code-writing` and `code-reviewer`; add
  `code-simplifier` only for flagged complexity/readability or a broad
  refactor, and add the auditor that found the issue when its trigger matches.

### Ad-hoc agents

When lead spawns an agent outside the original execution plan (to fix audit findings, handle escalations, complete missing work):

1. Lead assigns a skill and reviewers matching the type of work:
   - Code changes → skill: `code-writing`, reviewer: code-reviewer;
     code-simplifier and other reviewers join only when their triggers match
   - Prompt changes → skill: `prompt-master`, reviewers: prompt-reviewer
   - Skill changes → skill: `skill-master`, reviewers: skill-checker
   - Deploy/CI changes → skill: `deploy-pipeline`, reviewers: deploy-infra-reviewer
   - Infrastructure changes → skill: `infrastructure-setup`, reviewers: deploy-infra-reviewer, security-auditor
   - Other tasks (research, config, manual steps) → no skill, no reviewers. Agent follows lead's instructions directly.
2. The ad-hoc agent writes a unique non-terminal worker-result and returns it; the parent
   validates the evidence and writes any shared decisions.md entry
3. Standard review protocol: agent returns a diff → parent stages/commits by path → reviewers
   inspect → agent fixes → max 3 rounds
4. The parent verifies the resolved immutable current run says `final_status: done` with required evidence. A decisions.md entry remains supporting context only.

**Checkpoint:** all scheduled work returned, but tasks advance only when resolved immutable runs and evidence pass the completion gate.

### Implementation remediation

After round 3, preserve the source loop and its immutable evidence. For a
legacy non-atomic task, group unresolved themes into newly scoped remediation
tasks, update dependencies and file ownership, revalidate the changed
decomposition with the manifest guard, and resume automatically under the
existing approval. There is at most one remediation generation per `root_blocker_id`.
Every replacement and descendant inherits that root with `generation: 1` and
`bounded_path_used: true`; descendant decomposition is forbidden. Same-root failure after
replacement R3 is `technical-repair-exhausted`; the source loop is not reset.

An environment/deferred-evidence blocker (unmet
engine/image/credential/network/live-access precondition) escalates to the
user on first fail-closed confirmation per the runtime-contract section
Bounded fail-closed escape and blocker classification — it is never
grouped into a remediation task or a coder fix-round.

Set `awaiting_user.active: true` only for a product or acceptance change,
authority change, external or destructive effect, unavailable required input
or service, reviewer conflict, or the same atomic root blocker after the
bounded remediation path is exhausted with no safe alternative. Security, QA,
deploy, permission, immutable evidence, and final integration gates remain;
no user approval can override unresolved security findings.

## Phase 3: Wave Transition

1. For every task in the wave, resolve
   `work/{feature}/logs/working/task-{task-id}/{task-id}.run.yml` through the immutable-run
   gate and require the selected record to say `final_status: done` plus required evidence.
2. Treat task frontmatter, commits, messages, checkpoint data, and decisions as supporting context only. Checkpoint is not terminal proof. decisions.md is not terminal proof.
3. If a run record or required evidence is missing, failed, contradictory, or stale, keep the task incomplete and route it back to its worker or escalate. Do not advance the wave.
4. When every run record passes, the parent may reflect status in task metadata and commit the wave evidence: `chore: complete wave {N} — record terminal task evidence`.
5. Update the parent-owned `work/{feature}/logs/checkpoint.yml` with `last_completed_wave` and `next_wave`; this supports resume but cannot replace canonical task evidence.
6. Before starting the next wave, revalidate dependencies, file ownership, and available slots, then return to Phase 2.

**Checkpoint:** all wave tasks have terminal run records with evidence; supporting state is committed and checkpoint updated.

## Phase 4: User Review

All planned waves are done, including the optional risk-based Feature Audit Wave when triggered and the Final Wave. Final QA is mandatory; deploy and post-deploy verification remain conditional.

1. Show results: what was built, key decisions, QA report summary
2. Describe what to check manually (from execution plan "user checks" section)
3. Issues found → fix → review → parent path-scoped commit (max 3 rounds). If unresolved → escalate (see Escalation).
4. The parent verifies every task pointer resolves to an immutable run with
   `final_status: done`, QA passed, unresolved findings equal zero, and post-deploy
   verification passed or was explicitly waived when applicable.
5. Only after those gates pass, finish every task-level monotonic marker protocol and repair
   any projections, then persist all feature supporting evidence. `feature-status.yml` is written last
   with `status: complete`, QA, unresolved-finding, post-deploy, and evidence
   references. This durable file is the terminal feature proof; checkpoint and decisions
   are not.
6. If any gate fails, preserve the last valid durable state and report the feature as incomplete, failed, or aborted. Never write `status: complete` from a user override alone.

## Escalation

Apply
`.claude/shared/pipeline-contract.md#post-approval-amendment-classification`.
Call the user only for its product/authority result, a structured
`technical-repair-exhausted` result after the bounded remediation path, the
existing reviewer-conflict protocol, or a confirmed
environment/deferred-evidence blocker (below). Route a teammate blocker to
the parent first; the child does not classify or escalate it directly.

An environment/deferred-evidence blocker (unmet
engine/image/credential/network/live-access precondition) escalates to the
user on first fail-closed confirmation per the runtime-contract section
Bounded fail-closed escape and blocker classification — it is never
grouped into a remediation task or a coder fix-round.

When escalation criteria are met, preserve the blocked task/wave, report the
three-round and remediation evidence, record the unresolved stable blocker in
decisions.md, and wait for the specific user-owned decision.

## Self-Verification

- [ ] Execution plan created and approved
- [ ] Approved `tasks-manifest.yml` and complete `task-files-map.yml` validated
- [ ] Every `{task-id}.run.yml` pointer resolves to an immutable approved run with `final_status: done` and required evidence
- [ ] File overlaps serialized; available slots respected; no nested fan-out
- [ ] Every code change completed code-reviewer; code-simplifier ran only when triggered
- [ ] Feature-audit selection matched the catalog policy, and any selected audits completed in batches bounded by live runtime availability
- [ ] All waves committed (including Final Wave)
- [ ] Final QA is mandatory and passed
- [ ] User reviewed and approved
- [ ] `feature-status.yml` durably records `status: complete` only after the terminal gate passes
