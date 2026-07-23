# Canonical Delivery Pipeline Contract

This document is the source-of-truth lifecycle contract for the project commands
under `.claude/commands/`. Command files and skills may add operational detail,
but they must not weaken the preconditions, durable evidence, completion gates,
or transition limits defined here.

The words **MUST**, **MUST NOT**, **REQUIRED**, and **MAY** are normative.

## Approval and execution boundaries

Lifecycle/product approval governs durable state transitions. Owner authority governs a
risky or destructive effect. Native Codex sandbox/elevation permission governs tool access.
They are separate decisions: approval or owner authority never substitutes for the native
permission request required by the active runtime. Operational rules, including native
requests and permission-wait behavior, are canonical in
`.claude/codex/runtime-contract.md#approval-authority-and-native-permission`.

The initial execution plan is always an approval boundary: implementation
commands must stop for explicit user approval before the first implementation
mutation. The rules below apply only after that durable approval exists.

## Risk-proportional delivery paths

Classify delivery before creating lifecycle artifacts. Plan and explicit
approval remain required for every implementation, but assurance work scales
with scope and risk.

- **Direct path:** a low-risk local S change, normally no more than three implementation files,
  with no auth, payment, secrets or credentials, migration, deploy, SSH, Docker,
  destructive effect, or public-breaking change. Use a compact plan, explicit approval,
  one ordinary `coder` spawn, targeted tests, and one `code-reviewer`.
  This path does not run `/interview`, create a tech-spec, run
  split-tasks, or create a checkpoint, spawn receipt, immutable run chain, or
  technical-amendment manifest.
- **Lean spec path:** Standard S and low-risk M work. Reuse prior chat and code
  research. Interview and tech planning share one parent-owned clarification budget:
  at most one clarification batch with no more than five questions total,
  run one post-write user-spec validation, write a compact
  tech-spec, and use `reality-checker` plus `techspec-validator` in round 1.
  Security, test, UX, and product specialists run only when their matching
  risk or value trigger fires. Allow at most one corrective re-run.
- **Full path:** L or any high-risk trigger (auth, payment, secrets or credentials,
  migration, deploy, SSH, Docker, destructive or irreversible effects, or a public-breaking change),
  and any explicit user request for the full lifecycle. It retains the durable
  specification, decomposition, execution, permission, and terminal-evidence
  gates defined below.

If scope or risk grows, promote to the next path before continuing. A path may
not be downgraded merely to avoid a triggered gate.

The lean orchestration budget permits at most one new auxiliary helper and a
focused orchestration suite targeted to finish within two minutes. Exceeding
either limit triggers simplification/design review; it does not automatically
authorize more helper layers, tests, validators, or review cycles.

## Post-approval amendment classification

This section is the only exhaustive normative classifier. Team Lead, execution
skills, and command adapters MUST reference this exact heading and add only
their local operational actions. The classifier applies only to edits of
already-approved task or plan artifacts used by `/do-task`, `/do-all-tasks`,
and full-path `/write-code`.

An ordinary technical repair that preserves the approved objective and acceptance,
and whose risk does not grow,
stays inside the current task in any delivery path. Re-run only
affected targeted checks: no amendment hash, no amendment manifest, and no reapproval.
Stop for the user when the repair itself changes product/authority/scope.
If a new auth, payment, secrets/credentials, migration, deploy, SSH, Docker,
destructive, or public-breaking effect appears, promote to full before mutation.
An already-approved full-path repair within the same objective, acceptance, and
scope skips amendment ceremony but retains all full-path security, QA, and terminal gates,
including exact native permission and receipt safeguards.

A runtime worker or reviewer retry, fixed-role model fallback, or scheduling or
capacity adjustment that preserves the same role source, task envelope, gates,
and evidence remains governed by `.claude/codex/runtime-contract.md`. It does
not trigger amendment classification or reapproval and does not create a
technical-amendment record.

### Implementation recovery and review rounds

Before fresh execution or resume, the parent runs exactly
`python .claude/shared/scripts/validate_tasks_manifest.py --project . --manifest work/{feature}/tasks-manifest.yml --report work/{feature}/logs/tasks/manifest-guard-{iteration}.json`
and requires exit 0, then records the immutable report ref and SHA-256 against the approved
manifest. A legacy approved manifest that fails atomicity or skill evidence is
a pre-development gate regression, not a product question. Preserve existing
WIP and evidence, partition the affected task into dependency-linked
remediation tasks within the already approved objectives and acceptance,
update task/file ownership, and rerun the manifest guard. This recovery must
not set `awaiting_user`.

Review counting is exact: R1 runs all required reviewers. R2 exists only when an affected
reviewer reported a Critical/Major finding and reruns only those affected reviewers. R3 is
reserved for the final integrated gate with all required reviewers (or R1 is final when it has
no findings). There is no R4. Deduplicate counts by stable semantic identity. Any finding after
R3 routes to remediation; security, QA, deploy, permission, immutable evidence, and final
integration gates remain unchanged. No user approval can override unresolved security findings.

One unchanged atomic attempt loop stops after round 3; there is no round 4.
Round-3 findings on a legacy non-atomic task create newly scoped remediation
tasks grouped by unresolved theme, then update dependencies and file ownership,
revalidate with the manifest guard, and resume automatically under the existing
approval. For each `root_blocker_id`, the parent may create at most one remediation
generation. Every replacement and descendant inherits that root, `generation: 1`, and
`bounded_path_used: true`; descendant decomposition is forbidden. A same-root failure after
replacement tasks' R3 is `technical-repair-exhausted`. The source loop is never reset or relabeled.

Set `awaiting_user.active: true` only for a product or acceptance change, an
authority change, an external or destructive effect, unavailable required
input or service, reviewer conflict, or the same atomic root blocker still
failing after its bounded remediation path is exhausted with no safe
alternative. Only the last case becomes `technical-repair-exhausted` for an
implementation review loop. Internal technical findings remain
developer-owned.

A truly unavailable external service or tool is an owner-owned wait trigger; an internal
technical uncertainty is not. This is the canonical unavailable external service or tool rule.

Canonical regression: a T-001-shaped legacy oversized task with unresolved
round 3 findings records `implementation_remediation.active: true`, keeps
`awaiting_user.active: false`, creates dependency-linked replacement tasks,
passes the manifest guard, and resumes automatically through the existing
approval-owned continuation.

Executable parent remediation procedure:

1. Atomically transition the checkpoint to remediation and inherit the source
   `root_blocker_id`; reject a source already at generation 1/bounded path used.
2. First write a fresh strict immutable `changes_required` diagnostic for a legacy source;
   never cite a legacy mutable/non-schema report. Its `{path, sha256}` becomes split evidence.
   Allocate unique replacement IDs, mark the source `superseded` without erasing immutable
   evidence, and set every replacement to generation 1 with the inherited root/bounded flag.
3. Rewire every downstream dependency from the source to the appropriate replacements.
4. Atomically update replacement task files, the complete manifest, and task-files map.
5. Produce fresh immutable task-validator and cross-task reality-checker reports explicitly
   bound to every current task, current task-set/map digests, and exact `supersedes` pairs.
6. Route every task-envelope/file-map delta through the existing technical-amendment validator
   and evidence path. A validated technical/in-scope result auto-continues without conversational
   reapproval; product/authority results use only the listed owner-owned triggers.
7. Render FINAL approved manifest bytes to `work/{feature}/.tasks-manifest.final.tmp`, including
   approval, amendment, and immutable validation refs but no guard-output self-reference. Run
   `python .claude/shared/scripts/validate_tasks_manifest.py --project . --manifest work/{feature}/.tasks-manifest.final.tmp --logical-manifest work/{feature}/tasks-manifest.yml --report work/{feature}/logs/tasks/manifest-guard-{iteration}.json`.
   On exit 0 atomically replace canonical with the IDENTICAL staged bytes. There is no rerun and
   no post-guard mutation.
8. Store the immutable guard-report SHA-256 in checkpoint/entrypoint evidence and invoke the
   exact approval-owned continuation.

### Durable approval and amendment evidence

The approved execution-plan frontmatter is the only canonical
`execution_approval`. It carries `status`, `approved_at`, `owner_ref`,
`approved_plan_sha256`, `auto_continue`, `directive_evidence_ref`,
`amendment_gate_manifest_ref`, `amendment_gate_manifest_sha256`, and one
normalized `continuation` containing `command`, `argv`, and their canonical
JSON digest. Only `/do-task`, `/do-all-tasks`, and `/write-code` are valid
continuation commands, with their command-specific safe argument shape. The
manifest reference and exact byte digest bind approval to the immutable
execution-plan payload, normalized objective and acceptance-section digests,
exact task/plan artifact bytes, exact task/file-map bytes and approved entries,
existing-write bytes, absent/addable inventory, gate evidence schemas and
evaluator identities, classification policy, and continuation. Write the
manifest before approval; it is an immutable approval baseline, not a
post-failure scope declaration. The parent checkpoint stores only a
digest-bound projection named `execution_approval_projection`: every canonical
field, `plan_ref`, and a `projection_sha256` over their canonical JSON. Any
missing field, projection mismatch, continuation mismatch, or digest mismatch
fails closed.
`approved_plan_sha256` covers the canonical plan payload while excluding the
mutable approval block. `auto_continue: true` derives only from semantically
explicit owner intent waiving further conversational confirmation. Quoted
Russian or English wording is example evidence, never exact phrase matching.
It is not a magic phrase and does not authorize risky authority or bypass a
native permission request.

Every proposed artifact amendment has one durable record at
`work/{feature}/logs/technical-amendments/{amendment-id}.yml`, created from
`.claude/shared/work-templates/technical-amendment.yml.template`. The
filesystem-safe amendment ID, base approval reference and digest, stable repair
identity, approved-objective trace, allowed delta, before/after acceptance
criteria digests, classifier inputs and evidence digest, immutable failure
evidence, exact required gate IDs, terminal validation results, append-only
technical-validation ledger head, separate task review/fix counters, rationale,
status, and timestamps are required. Amendment-local continuation fields are
forbidden: the canonical execution approval is the only continuation
authority. Evidence-free prose is not an amendment record.

`.claude/shared/scripts/validate_technical_amendment.py` is the executable
classifier and fail-closed bundle validator. Its table-driven
`classify_scenario` policy is the sole executable copy of this section's
classifier; entrypoints reference it and MUST NOT implement a second local
classifier. Before a parent clears a wait or resumes, the validator verifies
UTF-8 without BOM, canonical newline hashing, the exact plan-body digest,
approval projection, gate-manifest byte digest, objective/task mapping,
acceptance snapshots, before bytes from the immutable manifest, exact
after-bytes, task/file-map entries, contained non-symlink paths and current
hashes, bounded repair identity/ledger, exact terminal gate results, evaluator
identities, and evidence digests. Classification is derived from the validated
baseline/delta plus a digest-bound semantic evidence document. Missing or
unprovable classifier signals fail closed; record prose never proves a safe
classification.

### Technical execution amendment

A parent may classify an edit as a technical execution amendment only when all
of the following are true:

- approved user-visible behavior and acceptance criteria are unchanged;
- there is no destructive, irreversible, or external effect and no expansion
  of authority;
- there is no deploy, SSH, Docker, or incident operation;
- there is no product tradeoff or specification/code conflict;
- there is no dependency, version, download, or cost expansion;
- the change affects only testable implementation tooling, runner, fixture,
  file mapping, task envelope, or verification mechanism for an already
  approved gate; and
- every changed plan/task artifact and every added or changed write path is in
  the allowed delta and objective trace for an existing approved objective.

A new objective or unrelated write path is a product/authority revision, not a
technical amendment. A qualifying technical amendment does not require new
user approval and must not set `awaiting_user`.

Exact manifests and file maps remain fail closed for mutation. The parent
updates the affected task/plan artifacts and task/file map, writes the
technical-amendment record, then runs the same required validators, reality
checks, security checks, and exact required gate IDs. It records rationale and
evidence and continues only after the canonical validator writes successful
validator evidence. An added path must be in the manifest's approved
absent/addable inventory; an existing write must match its manifest-bound
before bytes. No implementation mutation is allowed before successful
revalidation; fail closed does not mean ask the user.

A gate passes only through terminal semantic evidence with `schema_version`,
`gate_id`, the manifest-approved `evaluator_id`, `status: passed`,
`terminal_gate_passed: true`, digest-bound source evidence, and `completed_at`.
The manifest fixes its evidence content type/schema and allowed source evidence
types. A runner or process summary is source evidence only and can never
satisfy the terminal gate by itself.

A preflight or tool-wrapper failure before task code mutation or review does
not consume the task's three review/fix attempts. The task review/fix counter
remains separate. Derive the normalized failure signature from immutable
failure evidence content, type, and code; the amendment cannot assert its own
signature. All repair variants for the same `root_blocker_id` and approved
objective share the same bounded `repair_loop_id`; rewording or implementation
variants cannot reset it. Use one directory per blocker fingerprint with
immutable `attempt-NNN.yml` records in a digest-chained, gap-free sequence and
exactly one head file, `head.yml`. The amendment references that head and its exact digest.
Truncation, tampering, multiple heads, gaps, or attempt four is refused. After
the third failed attempt in this already bounded technical-validation path,
set status `technical-repair-exhausted` and request a recovery choice. The
parent must not relabel exhaustion as product/authority unless the scope truly
changed.

The blocker fingerprint is SHA-256 of canonical JSON containing
`approved_plan_sha256`, sorted `objective_ids`, `failing_gate_id`, and
`normalized_failure_signature`. The signature is derived from the immutable
failure evidence. Normalization trims and collapses whitespace,
normalizes newlines, replaces only volatile absolute paths and timestamps, and
case-folds only the stable error-class/code prefix. `amendment_id`,
`root_blocker_id`, and `repair_loop_id` are derived from that fingerprint, so
path/timestamp wording variants cannot reset the append-only ledger.

### Product/authority amendment

Stop for a user decision when any proposed edit introduces a new objective or
unrelated write path; dependency, version, or download expansion; Docker, SSH,
deploy, or incident activity; an external or destructive effect or authority
expansion; cost expansion; a product tradeoff or specification/code conflict;
a truly unavailable required input or service; or
`technical-repair-exhausted` after the bounded recovery path above. An
ambiguous product requirement is user-owned.
Internal technical ambiguity and teammate blockers route to the parent for
this structured classification first.

### Canonical Gitleaks repair example

Replacing an invalid inline PowerShell wrapper with
`.claude/shared/scripts/run_gitleaks_gate.ps1`, covered by
`tests/agent_orchestration/test_gitleaks_gate_runner.py`, is a materially
different bounded repair of an already-approved security gate. The amendment
may add those paths to the task/file map only when its allowed delta and
objective trace bind them to the existing approved objective and all required
validations pass. Under those conditions it does not require new user approval
and must not set `awaiting_user`.

The runner preserves the approved C01 process arguments, including
`--exit-code 0`, so findings do not change the scanner process exit. It uses
exact history log options `:(top,exclude,literal)chats.csv`. Its sanitized
summary is process evidence only: zero findings produce
`scan_completed_clean`; either scan finding secrets produces
`scan_completed_with_findings`, `classification_required: true`, and always
`terminal_gate_passed: false`. Invalid or missing reports and a nonzero scanner
exit fail closed as `scan_failed`. A separate approved exposure evaluator must
classify current versus historical findings and write evidence before
continuation. The process wrapper is not the C01 gate and can never call C01
passed.

### Recovery of a false approval wait

Recovery MUST invoke
`.claude/shared/scripts/validate_technical_amendment.py` with project-relative
artifact arguments and require durable successful validator evidence. Only
after successful revalidation may the parent proceed. The validator writes
evidence no-clobber with the pre-transition checkpoint digest,
plan/amendment/manifest/ledger digests, decision, approval-owned continuation,
timestamp, validator identity, and a self-digest. The transition rechecks those
immutable artifacts and the current checkpoint before an atomic same-directory
temporary-file, fsync, and replace. Only that transition may clear the wait
with `cleared_reason: false_technical_approval_gate` and `cleared_at`, clear
stale wait metadata, bind the validator evidence reference and hash, and set the
resume decision/target. With `auto_continue: true`, the decision is
`direct_resume` for the exact approved continuation. With
`auto_continue: false`, it writes nonblocking `resume_ready` with the same
continuation without requesting reapproval. It must not synthesize user
approval. Children never clear `awaiting_user`, set `resume_ready`, or resume.
SessionStart hooks are context-only: they may surface feature, checkpoint, and
`pending_tasks`, while the parent must validate durable evidence and decide.

If there is no structured amendment record, migrate or reclassify first. Never
clear from the free-form question or infer approval from conversation,
checkpoint progress, or a copied directive.

## Durable evidence

A transition is valid only when its evidence is written to the repository. Chat
messages, an agent's final response, an in-memory checkpoint, and the existence
of a file are not durable proof of approval or completion.

- File existence does not equal approval. An approval-gated artifact MUST carry
  `status: approved` and durable approval metadata in that artifact or its
  canonical manifest. Product/authority revisions return to draft until an
  explicit revision is approved and recorded. A bounded technical execution
  amendment follows the post-approval revalidation rule above instead.
- Approval is durable state. A later session MAY consume a recorded approval;
  it MUST NOT infer approval from prior conversation, a filename, or progress.
- A task is complete only when its canonical current-run pointer
  `work/{feature}/logs/working/task-{task-id}/{task-id}.run.yml` passes path,
  ID, digest, and supersedes-chain validation and resolves to the latest
  approved non-superseded immutable record under `runs/{run-id}.run.yml` with
  `final_status: done`. The pointer, checkpoint, decision log, commit, or
  reviewer report is not terminal task proof by itself.
- A feature is terminally complete only when `work/{feature}/feature-status.yml`
  records `status: complete` and every gate required by `/done` is satisfied.
  `status: aborted` is terminal but is never equivalent to completed.
- Writes that change lifecycle state MUST be atomic. A command that fails before
  its completion gate leaves the last valid durable state in force.

## Project state machine

Project lifecycle uses four states. Deployment readiness is an orthogonal
capability flag because configuring deployment does not approve a feature.

1. **P0 — absent:** project bootstrap artifacts do not exist.
2. **P1 — initialized:** `/init-project` has created and verified the project
   scaffold and source-of-truth Claude runtime.
3. **P2 — knowledge-ready:** Project Knowledge contains substantive, validated
   project facts. P1 projects MAY still start a session, but feature planning
   MUST surface missing knowledge instead of inventing it.
4. **P3 — session-active:** a session started from P1 or P2 is active. The
   previous ready state is retained so `/end-session` returns to P1 or P2.

Valid project transitions are P0 to P1 via `/init-project`, P1 to P2 via
`/init-project-knowledge`, P1 or P2 to P3 via `/start-session`, and P3 back to
its retained P1 or P2 state via `/end-session`. `/setup-deploy` may set the
`deploy-ready` capability after its own gate. `/advisor`, `/sync-codex`,
`/sync-os`, and `/sweep-watchdog` do not advance project lifecycle state.

## Feature state machine

Each `work/{feature}/` directory has an independent feature lifecycle:

1. **F0 — absent:** no confirmed feature workspace.
2. **F1 — user-spec draft:** intent is confirmed and requirements are being
   captured; the draft is not approved.
3. **F2 — user-spec approved:** `user-spec.md` durably records
   `status: approved`.
4. **F3 — tech-spec draft:** technical design is being produced or revised.
5. **F4 — tech-spec approved:** both user and technical specifications durably
   record `status: approved`.
6. **F5 — tasks approved:** `tasks-manifest.yml` records `status: approved`, all
   task files are listed, dependencies are valid, and `task-files-map.yml`
   covers their declared writes. Referenced validator evidence contains no
   unresolved Critical/Major atomicity or skill-task mismatch findings, no
   unresolved cross-task findings, and no atomicity waiver/disposition.
7. **F6 — executing:** at least one approved task is active or resumable. Each
   task has its own immutable-run directory and canonical current-run pointer.
8. **F7 — verifying:** all required pointers resolve to approved immutable runs
   with `final_status: done`, and feature-level acceptance or deployment gates
   are being checked.
9. **F8 — complete:** `feature-status.yml` records `status: complete` together
   with the required QA and unresolved-finding fields.
10. **F9 — archived:** `/done` has passed its strict gate and moved the feature
    without a destination collision.
11. **FA — aborted:** terminal non-completion. An override or waiver MAY explain
    the stop, but MUST NOT relabel it complete or archived-as-completed.

The normal path is F0 to F1 to F2 via `/interview`, F2 to F3 to F4 via
`/tech-plan`, F4 to F5 via `/split-tasks`, F5 through F6 and F7 to F8 via
approved execution and verification, then F8 to F9 via `/done`. Revisions move
the affected artifact and all dependent states back to their last valid draft
gate unless they qualify for the bounded post-approval technical execution
amendment path above. `/write-code` inside a feature participates only through
the same task run records; outside a feature it does not advance this state
machine.

## Command transition matrix

Every row has exactly five columns: command, preconditions, durable output or
state, completion gate, and next allowed transition.

<!-- COMMAND_MATRIX_START -->
| Command | Preconditions | Durable output/state | Completion gate | Next allowed transition |
| --- | --- | --- | --- | --- |
| `/init-project` | P0, or an explicitly approved idempotent repair of P1 | Project scaffold, source `.claude/**`, generated runtime, and initialized repository state | Required scaffold validates, source and generated runtime agree, and no existing user files were silently replaced | `/init-project-knowledge`, `/setup-deploy`, or `/start-session` |
| `/init-project-knowledge` | P1 and confirmed project intent; existing substantive knowledge is revised rather than overwritten implicitly | Substantive Project Knowledge source files and regenerated Codex runtime | Knowledge validation passes, changes are reviewed, and any required explicit approval is durably recorded | `/start-session`, `/interview`, `/setup-deploy`, `/sync-codex`, or `/sync-os` |
| `/start-session` | P1 or P2 and no already-active session; `work/session-reports/latest.yml` is optional resumable input, not approval | P3 plus any resumed feature checkpoint reference; the latest durable session report is consumed read-only | Resume target is validated, stale work is reported, and restored context does not bypass any approval gate | `/interview`, `/tech-plan`, `/split-tasks`, `/do-task`, `/do-all-tasks`, `/write-code`, `/advisor`, `/setup-deploy`, or `/end-session` as their own preconditions allow |
| `/interview` | P1, P2, or P3; intent confirmation occurs before creating a feature workspace | `work/{feature}/user-spec.md` progressing F0 to F1 and, only after explicit approval is recorded, F2 | Substantive seeded answers are reused, residual gaps are resolved, validation passes, and `user-spec` records `status: approved` | `/tech-plan`, `/advisor`, or an explicit `/interview` revision |
| `/tech-plan` | F2 proven by `user-spec.status: approved`; existing approved specs are preserved unless explicit revision is requested | `work/{feature}/tech-spec.md`, disjoint validator reports, and F3 progressing to F4 after approval | Validators pass, the parent aggregates reports, user approval is recorded, and `tech-spec` records `status: approved` | `/split-tasks`, `/advisor`, or an explicit `/tech-plan` revision |
| `/split-tasks` | F4 proven by approved user and tech specs | Atomic task files, `tasks-manifest.yml`, `task-files-map.yml`, disjoint creator reports, and F5 after approval | Dependencies, file ownership, validator evidence, and the deterministic manifest guard validate; one cross-task pass succeeds; the manifest records `status: approved` | `/do-task`, `/do-all-tasks`, `/advisor`, or an explicit `/split-tasks` revision |
| `/do-task` | F5 or F6; approved specs and manifest exist, dependencies resolve through validated current pointers to immutable runs with `final_status: done`, and the selected task owns its declared files | Immutable task run, atomically replaced current pointer, code or documentation changes by the assigned writer, and canonical per-reviewer round reports | Tests and required review gates pass and the selected task pointer resolves to an approved immutable run with `final_status: done` | Another dependency-ready `/do-task`, parent-controlled `/do-all-tasks` resume, feature verification, `/advisor`, or `/end-session` |
| `/do-all-tasks` | F5 or resumable F6; approved manifest and complete file map validate; parent has bounded the wave to available slots | Parent-owned checkpoint and feature status, immutable run plus current pointer per task, disjoint review reports, and F6 progressing through F7 to F8 only after verification | Every task pointer resolves to an approved immutable run with `final_status: done`, feature acceptance and QA gates pass, unresolved findings are zero, and `feature-status.yml` records `status: complete` | `/done`, `/advisor`, `/setup-deploy` when required, or `/end-session` |
| `/write-code` | A concrete plan has explicit approval; direct and lean paths satisfy the risk classification above, while full feature execution also requires the relevant F5 or F6 gates | Changes written only by delegated `coder`, targeted tests, and required review evidence; immutable run/current pointer evidence applies only to full-path task execution | Approved scope is implemented and its risk-proportional tests and reviews pass; full-path task pointers additionally resolve to an immutable run with `final_status: done` | Parent-controlled feature verification, another approved `/write-code`, `/advisor`, or `/end-session` |
| `/setup-deploy` | P1, P2, or P3; a deployment plan has explicit approval and timing policy permits the action | Deployment configuration and documentation plus a durable sysadmin verification or deployment report; `deploy-ready` capability after success | Only the `sysadmin` ran SSH, Docker, and deploy operations; methodology checks, smoke checks, rollback readiness, and approval requirements pass | `/do-all-tasks`, parent-controlled post-deploy verification, `/done` after F8, or `/end-session` |
| `/done` | F8 and strict terminal evidence in `feature-status.yml`: `status: complete`, QA passed, zero unresolved findings, and post-deploy passed or explicitly waived when applicable | Idempotent archive at `work/completed/{feature}/` plus any required Project Knowledge source updates and regenerated runtime | Source updates validate, destination has no collision, archive is atomic, and aborted or overridden work is not represented as completed | `/end-session`, `/start-session`, `/interview`, `/sync-codex`, or `/sync-os` |
| `/end-session` | P3; active work is first reduced to its last valid durable state | A dated durable session report and atomically replaced `work/session-reports/latest.yml` pointer with backlog pointers | Report is complete, pointer update is atomic, the report remains the single source of truth for session handoff, and no approval is inferred | `/start-session`, `/sync-codex`, or `/sync-os` |
| `/advisor` | A concrete proposal or decision context and verified role metadata; missing role metadata fails closed | Read-only verdict; if the owner accepts it, the parent may record the decision in the canonical feature decision artifact | Output schema and role gate pass; the advisor does not claim approval, mutate lifecycle state, or choose a transition | Return to the caller's previously allowed command or request explicit owner approval |
| `/sync-codex` | Source-of-truth changes exist under `CLAUDE.md` or `.claude/**`; generated files are not treated as editable input | Regenerated `AGENTS.md`, `.agents/**`, and managed `.codex/**` derived from the Claude source | Sync completes with pruning and validation, and a second check reports no source/generated drift | Return to the unchanged project or feature state, `/sync-os`, or `/end-session` |
| `/sync-os` | Sanitized Claude-side source is ready and the public mirror target is explicitly in scope | Sanitized public OS mirror state and durable synchronization result | Sanitization, secret scanning, source selection, and mirror synchronization succeed without treating generated files as source | Return to the unchanged project or feature state, `/sync-codex`, or `/end-session` |
| `/sweep-watchdog` | Parent-owned `/do-all-tasks` execution is active or paused and runtime capabilities are known | Exactly one redacted sweep entry plus permitted checkpoint stall metadata; no task or feature terminal state | The sweep uses only its four permitted command patterns, respects available capabilities, and reports findings without attempting resume | Parent owns resume, re-prompt, interruption, escalation, or the next event-driven sweep |
<!-- COMMAND_MATRIX_END -->

## Concurrency, ownership, and budgets

- Parallel writers MUST have disjoint declared file sets. File overlap requires
  the parent to serialize the tasks. Reports are also disjoint: each validator
  or reviewer writes only its canonical per-agent, per-round report.
- Shared and aggregate state has one writer: the parent orchestrator. It owns
  manifests, file maps, checkpoints, feature status, aggregation, scheduling,
  retry decisions, and resume. Children return evidence; they do not race to
  update shared state.
- Atomicity determines decomposition task count. Fifteen is a soft organization
  threshold and maximum scheduling/validation batch size, never a lifecycle cap
  or reason to merge concerns. Creation and review re-run only changed tasks
  when possible and perform at most one cross-task consistency pass per round.
- Scheduling never exceeds available agent slots. Every running worker counts
  as an active agent, including the parent and watchdog.
- There is no nested fan-out. A child executor or reviewer MUST NOT spawn more
  workers; only the parent schedules parallel work.

## Role boundaries

- The Team Lead owns the plan, obtains explicit approval, delegates, aggregates,
  and advances durable state. The Team Lead MUST NOT write project code.
- Only the `coder` role writes project code. It writes within its assigned,
  disjoint scope and returns tests and evidence to the parent.
- Only the `sysadmin` role may run SSH, Docker, or deployment commands. Deploys
  require an approved plan and the repository's timing policy; explicit owner
  authorization may permit an out-of-window deploy where the policy says so.
- Reviewers and validators do not approve on the user's behalf and do not mutate
  implementation or shared lifecycle state. They write isolated reports for
  parent aggregation.
- Parent aggregation and user approval cannot waive a Critical/Major atomicity
  or skill-task mismatch finding. The task is split or corrected, revalidated,
  and any split is recorded as `resolved_by_split` with exact report reference,
  finding ID, and replacement task IDs present in the manifest.

## Fail-closed rule

If preconditions or durable evidence are missing, contradictory, malformed, or
stale, the command MUST stop before mutation and report the unmet gate. Recovery
resumes from the last valid durable state; it never reconstructs approval or
completion from conversational context. For a qualifying technical execution
amendment, "stop before mutation" means stop implementation mutation until the
amended task/plan artifacts pass their required revalidation; it does not mean
ask the user for approval that is already durably recorded.
