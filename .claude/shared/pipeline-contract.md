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
  split-tasks, or create a checkpoint.
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
  specification, decomposition, execution, permission, and completion-evidence
  gates defined below.

If scope or risk grows, promote to the next path before continuing. A path may
not be downgraded merely to avoid a triggered gate.

The lean orchestration budget permits at most one new auxiliary helper and a
focused orchestration suite targeted to finish within two minutes. Exceeding
either limit triggers simplification/design review; it does not automatically
authorize more helper layers, tests, validators, or review cycles.

## Post-approval changes

This section applies to edits of an already-approved task or plan artifact used by
`/do-task`, `/do-all-tasks`, and full-path `/write-code`.

An ordinary technical repair that preserves the approved objective and acceptance,
and whose risk does not grow,
stays inside the current task in any delivery path. Re-run only
affected targeted checks and continue — no reapproval needed.
Stop for the user when the repair itself changes product/authority/scope.
If a new auth, payment, secrets/credentials, migration, deploy, SSH, Docker,
destructive, or public-breaking effect appears, promote to full before mutation.
An already-approved full-path repair within the same objective, acceptance, and
scope continues under the existing approval and retains all full-path security, QA, and terminal gates,
including exact native permission and receipt safeguards.

A runtime worker or reviewer retry, fixed-role model fallback, or scheduling or
capacity adjustment that preserves the same role source, task envelope, gates,
and evidence remains governed by `.claude/codex/runtime-contract.md`. It does
not require any of the machinery above.

## Review rounds

Review counting is exact: R1 runs all required reviewers. R2 exists only when an affected
reviewer reported a Critical/Major finding and reruns only those affected reviewers. R3 is
reserved for the final integrated gate with all required reviewers (or R1 is final when it has
no findings). There is no R4. Deduplicate counts by stable semantic identity. No user approval
can override unresolved security findings.

If a Critical or Major finding is still open after round 3, stop that review loop and
escalate to the owner: report what was tried across all three rounds, a root-cause
hypothesis, and offer the owner a choice — skip the item and continue, halt the feature
for manual debugging, or supply the missing context needed to retry. Do not silently
skip a finding and do not route it into an automatic remediation cycle without the
owner's decision.

An environment/deferred-evidence blocker (unmet engine/image/credential/network/live-access
precondition) follows `.claude/codex/runtime-contract.md#bounded-fail-closed-escape-and-blocker-classification`
instead: it escalates to the owner on first fail-closed confirmation, not after three rounds.

## Durable evidence

A transition is valid only when its evidence is written to the repository. Chat
messages, an agent's final response, and an in-memory checkpoint alone are not durable
proof of approval or completion.

- File existence does not equal approval. An approval-gated artifact MUST carry
  `status: approved` and durable approval metadata (who approved it and when) in that
  artifact or its canonical manifest. A product/authority revision returns to draft
  until an explicit revision is approved and recorded again.
- Approval is durable state. A later session MAY consume a recorded approval;
  it MUST NOT infer approval from prior conversation, a filename, or progress.
- A task is complete when its required tests and reviews pass and the parent records
  `done` in the task's frontmatter and `work/{feature}/logs/checkpoint.yml`. Add a
  `decisions.md` entry when the feature's decisions.md trigger applies. A commit or a
  worker's "task complete" message is supporting context, not completion proof by itself.
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
   unresolved Critical/Major atomicity or skill-task mismatch findings, and no
   unresolved cross-task findings.
7. **F6 — executing:** at least one approved task is active or resumable, tracked in
   `work/{feature}/logs/checkpoint.yml`.
8. **F7 — verifying:** every required task is recorded `done`, and feature-level
   acceptance or deployment gates are being checked.
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
gate unless they qualify for the post-approval technical repair above.
`/write-code` inside a feature participates only through the same task
records; outside a feature it does not advance this state machine.

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
| `/split-tasks` | F4 proven by approved user and tech specs | Atomic task files, `tasks-manifest.yml`, `task-files-map.yml`, disjoint creator reports, and F5 after approval | Dependencies, file ownership, and validator evidence validate; `validate_tasks_manifest.py` exits 0; one cross-task pass succeeds; the manifest records `status: approved` | `/do-task`, `/do-all-tasks`, `/advisor`, or an explicit `/split-tasks` revision |
| `/do-task` | F5 or F6; approved specs and manifest exist, every `depends_on` task is recorded `done`, and the selected task owns its declared files | Code or documentation changes by the assigned writer, plus canonical per-reviewer round reports | Tests and required review gates pass and the parent records the task `done` in its frontmatter and in `checkpoint.yml` | Another dependency-ready `/do-task`, parent-controlled `/do-all-tasks` resume, feature verification, `/advisor`, or `/end-session` |
| `/do-all-tasks` | F5 or resumable F6; approved manifest and complete file map validate; parent has bounded the wave to available slots | Parent-owned checkpoint and feature status, code changes per task, disjoint review reports, and F6 progressing through F7 to F8 only after verification | Every task is recorded `done`, feature acceptance and QA gates pass, unresolved findings are zero, and `feature-status.yml` records `status: complete` | `/done`, `/advisor`, `/setup-deploy` when required, or `/end-session` |
| `/write-code` | A concrete plan has explicit approval; direct and lean paths satisfy the risk classification above, while full feature execution also requires the relevant F5 or F6 gates | Changes written only by delegated `coder`, targeted tests, and required review evidence | Approved scope is implemented and its risk-proportional tests and reviews pass; full-path task work additionally follows the `/do-task` completion gate | Parent-controlled feature verification, another approved `/write-code`, `/advisor`, or `/end-session` |
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
- A Critical/Major atomicity or skill-task-mismatch finding cannot be waived by
  parent aggregation or user approval. Split or correct the task and revalidate
  before continuing; `/split-tasks` records which finding a split resolved.
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

## Fail-closed rule

If preconditions or durable evidence are missing, contradictory, malformed, or
stale, the command MUST stop before mutation and report the unmet gate. Recovery
resumes from the last valid durable state; it never reconstructs approval or
completion from conversational context. For a qualifying ordinary technical
repair, "stop before mutation" applies only to the change that actually
requires it — fail closed does not mean ask the user for approval that is
already durably recorded.
