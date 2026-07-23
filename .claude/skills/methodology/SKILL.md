---
name: methodology
description: |
  AI-First development methodology: spec-driven pipeline, project structure,
  skills/agents ecosystem, quality gates.

  Use when: "изучи методологию", "изучи глобальную папку", "как работает методология",
  "how does the methodology work", "explain the workflow"

  For infrastructure tasks, use infrastructure-setup or deploy-pipeline skills.
---

# AI-First Development Methodology

## What Is This

A structured development approach for AI agents. Full-path work goes through:
idea → spec → architecture → tasks → implementation → documentation update.
Direct and lean work use the bounded routes below. QA and deploy are regular
full-path tech-spec tasks rather than separate pipeline steps.

Core problems it solves:
- **Context loss between sessions** — distributed knowledge base persists across sessions
- **Quality without human review** — automated validators at every stage
- **Scope creep** — specs approved before coding starts
- **Outdated agent knowledge** — Context7 MCP fetches current library docs

---

## Development Pipeline

Delivery uses three risk-proportional paths:

- **Direct path:** low-risk local S work uses compact plan + approval, one
  ordinary single-turn coder, targeted tests, and one code-reviewer.
- **Lean spec path:** Standard S and low-risk M reuse prior evidence, use one
  clarification batch, compact specs, two default technical validators, and
  one corrective pass.
- **Full path:** L, high-risk, or explicitly requested work uses the complete
  lifecycle below.

Ordinary single-turn coder and read-only reviewer calls need no receipt or
authorization handshake. Privileged/high-risk operations retain those
safeguards. The **lean budget stop-loss** routes oversized auxiliary
orchestration helpers or focused suites to simplification/design review instead
of automatically adding tests or review cycles.

The detailed lifecycle below is full-path only. Direct and lean paths execute
through `/write-code`; lean planning shares one parent-owned clarification budget
across interview and tech planning and stops after its compact approvals.

### Step 1: User Spec — `/interview` (full-path lifecycle)

**What:** Structured interview to capture requirements in human-readable form (Russian).

**Process:**
- Agent reads Project Knowledge files to understand the project
- Scans codebase for relevant code, patterns, integration points
- Runs 3 interview cycles with the user (general → code-informed → edge cases)
- `userspec-validator` agent verifies coverage
- Creates `user-spec.md` from interview data → git commit draft
- 1 unified validator runs (up to 3 iterations):
  - `userspec-validator` — document quality, acceptance criteria testability, solution feasibility, over/underengineering (3 dimensions in one pass)
- Git commit after each validation round
- User approves → git commit approval (status: approved)

**Output:** `work/{feature}/user-spec.md` (status: approved)

**Skill:** `interview-planning`

### Step 2: Tech Spec — `/tech-plan` (full-path lifecycle)

**What:** Technical architecture, decisions, testing strategy, implementation plan.

**Process:**
- Reads approved user-spec
- Researches codebase, checks dependencies, uses Context7 for external libraries
- Asks technical clarification questions
- Copies tech-spec template, edits sections in place → `tech-spec.md` with architecture (including Shared Resources for heavy objects like ML models, DB pools), decisions, testing strategy, brief Implementation Tasks (scope only — AC and TDD are added during task-decomposition) → git commit draft
- Implementation Tasks include Verify-smoke (executable checks: curl, python -c, docker) and Verify-user (manual UI/UX checks) fields where applicable
- Every code change keeps `code-reviewer`; `code-simplifier` runs only for a
  broad refactor or flagged complexity/readability
- A conditional, risk-based Feature Audit Wave may precede the Final Wave according to the [catalog policy](../tech-planning/references/skills-and-reviewers.md#risk-based-feature-audit-policy); Final QA is mandatory even when the audit wave is skipped
- 4 validators run in bounded batches that fit the available slots (up to 3
  iterations). With the configured cap of five including the root, all four may
  run concurrently only when live runtime availability reports four confirmed free child slots;
  otherwise use smaller batches:
  - `reality-checker` — detects non-existent files, functions, APIs (mirages)
  - `techspec-validator` — bidirectional requirements traceability, over/underengineering, solution depth, template compliance, task quality, wave conflict detection
  - `security-auditor` — OWASP Top 10 review
  - `test-reviewer` — test plan adequacy
- Git commit after each validation round
- User approves → git commit approval (status: approved)

**Output:** `work/{feature}/tech-spec.md` (status: approved)

**Skill:** `tech-planning`

### Step 3: Task Decomposition — `/split-tasks` (full-path only)

**What:** Break tech-spec into atomic task files.

**Process:**
- For each Implementation Task in tech-spec, a `task-creator` agent copies the task template and fills it; creators run in bounded batches that fit available child slots
- Each task file expands brief tech-spec scope into: acceptance criteria, TDD anchor (from Testing Strategy), context files, skills, reviewers, wave, dependencies → git commit draft
- 2 validator types run in bounded batches (up to 3 iterations):
  - `task-validator` — template compliance, content quality
  - `reality-checker` — validates against actual codebase (file existence, feasibility)
- Cross-task integration check: run exactly one cross-task pass with both validator perspectives over the complete manifest. Fix reported tasks and individually re-validate only those changed tasks; do not run another cross-task validator pass
- Git commit after each validation round
- User approves → git commit approval

**Output:** `work/{feature}/tasks/*.md` (validated)

**Skill:** `task-decomposition`

### Step 4: Implementation

**Choose `/do-task` when:** single task, manual control, debugging, iterating on one piece.
**Choose `/do-all-tasks` when:** multiple approved tasks are ready and independent work can be scheduled safely.

Two modes:

In both modes, the parent/root is the exclusive git index and commit writer.
Workers return scoped diffs, verification results, and immutable non-terminal
worker results. Only the parent validates ownership and gates, uses path-scoped staging
for every implementation, fix, and evidence commit, and terminalizes
the immutable run. Supporting projections and the immutable record are written first; the
canonical current-run pointer is atomically replaced after validation. The pointer is
written last.

#### Mode A: Single Task — `/do-task`

One task per session. Suited for manual, controlled execution.

**Process:**
- Reads task file and all its Context Files
- Loads skills specified in task (e.g. `code-writing`, `pre-deploy-qa`, `infrastructure-setup`)
- Follows loaded skill workflow (TDD for code tasks, verification for QA tasks, etc.)
- Worker returns the implementation diff and passing test evidence; the parent commits it
- Runs reviewers specified in task (if any), up to 3 review iterations
- Parent commits each accepted review-fix round after path-scoped validation
- Writes entry to `decisions.md`, updates task status → done
- Git commit status + decisions

**Skill:** Loaded from task file (typically `code-writing` for code tasks)

#### Mode B: Full Feature — `/do-all-tasks`

All tasks are executed through parent-orchestrated waves of isolated workers.

**Process:**
- Parent reads the approved specs, task manifest, file map, and task files; builds a bounded execution plan and obtains explicit approval
- Checks durable task result artifacts when resuming; `checkpoint.yml` supports routing but is not terminal proof
- Executes tasks wave by wave:
  - Parent spawns bounded isolated workers with explicit role instructions and only the minimal task context, using the current runtime primitive
  - Workers run in parallel only for independent tasks with disjoint declared files; overlap is serialized and total active workers never exceed available slots
  - Each worker follows its loaded skill, runs required verification, and returns its scoped diff plus immutable non-terminal worker-result evidence
  - Parent coordinates reviewers, aggregates result artifacts, owns shared durable state, commits wave status, and updates `checkpoint.yml`; children do not use shared team state or nested fan-out
- **Feature Audit Wave** (conditional and risk-based): use only the audit tasks selected by the catalog policy above. When multiple audits are selected, the parent uses bounded batches under the shared configured-cap/live-slot formula. Auditors write disjoint reports; the parent aggregates findings and coordinates bounded fix rounds. This is the only feature-level audit pass
- **Ad-hoc workers**: when work outside planned tasks is required, parent assigns an explicit role, matching skill, minimal context, disjoint output, and reviewers based on work type
- **Final Wave**: Final QA is mandatory; deploy + post-deploy remain conditional
- **Escalation**: after 3 failed fix rounds — stop, report to user, write decisions.md entry, wait for decision
- User reviews results; parent records terminal durable state and releases runtime workers. A checkpoint is retained or archived according to the pipeline contract, not treated as completion evidence

Runtime adapters may map workers to Claude teammates, Codex subagents, or another supported primitive. The methodology does not require shared team state, and it makes no model override claim unless the active runtime exposes and confirms that capability.

Tasks can be code, user-action, deploy, config, or verification. Task nature is determined by its skill + description, not a separate type field.

**Skill:** `feature-execution`

### Step 5: Done — `/done`

**What:** Finalize feature, update project knowledge, archive.

**Process:**
- Reads user-spec, tech-spec, decisions.md
- Updates affected Project Knowledge files (architecture.md, patterns.md, deployment.md, etc.)
- Moves `work/{feature}/` → `work/completed/{feature}/`
- Commits changes

**Skill:** Loads `documentation-writing` skill for PK update rules

---

## Project Structure

### Project Knowledge — the Knowledge Base

All project documentation lives in `.claude/skills/project-knowledge/references/`. This is the single source of truth for everything about the project.

**4 core + optional files:**

| File | Content |
|------|---------|
| `project.md` | Purpose, audience, core features, scope |
| `architecture.md` | Tech stack, structure, dependencies, data model |
| `patterns.md` | Code conventions, git workflow, testing, business rules |
| `deployment.md` | Platform, env vars, CI/CD, monitoring |
| `ux-guidelines.md` | UI language, tone, domain glossary (optional) |

Features and roadmap live in the project backlog (external to PK).

**CLAUDE.md is minimal.** It contains only the project name, a reference to project-knowledge skill, methodology overview, and default branch. All real information lives in Project Knowledge files.

**`project-planning` skill** creates PK from scratch in new projects via interview (`/init-project-knowledge`).

**`documentation-writing` skill** manages existing PK: audits, updates, checks consistency. `/done` command uses it to update PK after feature completion.

### Work Items

```
work/{feature}/
├── user-spec.md          # Requirements (Russian, for human)
├── tech-spec.md          # Architecture (English, for agent)
├── decisions.md          # Decisions made during implementation
├── tasks/
│   ├── 1.md              # Atomic task files
│   ├── 2.md
│   └── 3.md
└── logs/                 # Working logs (interview, research, reviews)
```

Completed features are archived to `work/completed/{feature}/`.

### Project-Local Structure `.claude/`

```
.claude/
├── skills/               # Skills (methodology, workflow, quality)
├── agents/               # Agents (validators, reviewers, creators)
├── commands/             # Slash commands
├── shared/               # Templates, scripts, interview plans
├── hooks/                # Automation hooks
└── CLAUDE.md             # Project instructions (checked into repo)
```

All methodology assets are project-local — checked into the repository under `.claude/`. There is no global home-directory install.

---

## Key Principles

### Commit Strategy
Commit after each step where the repository state is stable and meaningful. Not after every action — after each result.

- **Planning stages** (user-spec, tech-spec, tasks): draft commit → validation round commits → approval commit
- **Single task execution** (do-task): implementation commit (tests pass) → review fix commits (tests pass) → status/decisions commit
- **Feature execution** (do-all-tasks): workers return scoped changes and evidence; the parent commits accepted code, review fixes, and statuses per wave
- **Finalization** (done): single commit with PK updates + archive

### Spec-Driven Development (full-path only)
Write specifications before code. The hierarchy: User Spec → Tech Spec → Tasks → Code. Code starts only after specs are approved.

### Validation at Every Stage (full-path only)
- User spec: 1 unified validator (userspec-validator — quality + adequacy + completeness in one pass)
- Tech spec: 4 validators (reality-checker + techspec-validator + security + test), scheduled in bounded batches within available child slots
- Tasks: 2 validator types (template + reality), with bounded task-creator and validator batches plus exactly one cross-task pass
- Code: every code change has `code-reviewer`; `code-simplifier` and other
  specialists run only on matching triggers
- Feature Audit Wave: conditional and risk-based; its selected audit tasks come from the catalog policy above and run in bounded batches within confirmed free child slots
- Final QA is mandatory. Post-deploy QA verifies the live environment only when applicable

No planning, validation, or feature-audit batch may exceed runtime capacity. This project
uses a configured cap of five. For every bounded batch, calculate
`confirmed free children = min(configured cap - current active agents (including root),
live runtime reported free child slots, explicitly named workload-specific cap)`. Schedule
only within confirmed free child slots and live runtime availability.

Max 3 fix iterations at each stage.

### Project Knowledge as Single Source of Truth
Project documentation = `.claude/skills/project-knowledge/references/`. CLAUDE.md stays minimal — just a pointer. The `/done` command updates PK after every feature. The `documentation-writing` skill audits PK for bloat and quality.

### Just-In-Time Context
Agent reads only what's needed for current task, not everything. Task files list their Context Files explicitly.

### Context7 for Library Docs
Agent uses Context7 MCP to fetch current library documentation instead of relying on training data. Used during tech-spec research and code implementation.

### Checkpoint Recovery
Feature execution persists recovery metadata after each wave. `checkpoint.yml` and
`decisions.md` provide routing and context only. After compaction, the parent resolves each
canonical current-run pointer to its contained immutable approved run before selecting
dependency-ready unfinished work. Immutable `runs/{run-id}.run.yml` records are terminal
task evidence; `{task-id}.run.yml` is only the current pointer, and `feature-status.yml` is
terminal evidence for the feature. Neither checkpoint nor decisions can prove completion.

---

## Skills Ecosystem

<!-- Exclude from methodology catalogs: items for private repo management (public-repo skill, public-repo-scanner agent, sync-public command). They are tooling for maintaining this repository, not part of the development methodology. -->

### Planning Skills
| Skill | Purpose |
|-------|---------|
| `project-planning` | New project: interview → project knowledge docs (project.md, architecture.md, etc.) |
| `interview-planning` | Feature requirements: interview → user-spec.md |
| `tech-planning` | Architecture: research → tech-spec.md |
| `task-decomposition` | Decompose tech-spec into atomic task files |

### Execution Skills
| Skill | Purpose |
|-------|---------|
| `code-writing` | TDD cycle: plan → tests → code → review |
| `prompt-master` | LLM prompt engineering: write, improve, verify prompts |
| `feature-execution` | Parent dispatches isolated workers by wave; workers return evidence, parent aggregates and commits statuses |
| `pre-deploy-qa` | Pre-deploy acceptance testing: tests + acceptance criteria |
| `post-deploy-qa` | Post-deploy verification on live environment via MCP tools |

### Quality & Review Skills
| Skill | Purpose |
|-------|---------|
| `code-reviewing` | 11-dimension code review methodology (incl. Resource Management) |
| `security-auditor` | OWASP Top 10 security analysis |
| `test-master` | Testing strategy: when to use which tests |

### Meta Skills
| Skill | Purpose |
|-------|---------|
| `methodology` | This skill — how the process works |
| `documentation-writing` | Manage Project Knowledge files |
| `skill-master` | Create and maintain quality skills |
| `infrastructure-setup` | Framework init, Docker, pre-commit hooks, testing setup |
| `deploy-pipeline` | CI/CD pipelines, deployment config, automated deploy |
| `prompt-master` | Effective prompts for LLMs (also an execution skill) |
| `skill-test-designer` | Design test scenarios for skills |
| `skill-tester` | Execute skill test scenarios |

---

## Agents

Agents are isolated workers with fresh context. The parent spawns a bounded set through the current runtime primitive, gives each explicit role instructions and minimal context, and requires a structured result artifact. Parallel work is limited to independent, disjoint tasks; the parent aggregates outputs and owns all shared state. Workers do not spawn more workers. Runtime-specific model selection is optional and must not be claimed unless supported.

### Validators (run during spec/task creation)
- `userspec-validator` — unified validator: document quality, solution feasibility, interview completeness (3 dimensions in one pass; merged from 3 predecessors in Wave 3)
- `techspec-validator` — unified validator: template compliance, task quality, wave conflict detection, bidirectional traceability, over/underengineering, solution depth (merged from 2 predecessors in Wave 3)
- `reality-checker` — detects mirages (non-existent files/functions/APIs); validates tasks against codebase
- `task-validator` — task template compliance
- `task-creator` — generates task files from tech-spec

### Reviewers (run during/after code writing)
- `code-reviewer` — code quality across 10 dimensions
- `code-simplifier` — behavior-preserving simplification, triggered by broad
  refactors or code-reviewer complexity/readability findings
- `test-reviewer` — test quality analysis with concrete fixes
- `security-auditor` — OWASP Top 10, auth, input validation
- `prompt-reviewer` — prompt quality against prompt-master principles
- `documentation-reviewer` — project-knowledge quality against documentation-writing principles
- `deploy-infra-reviewer` — CI/CD, deploy config, Docker, pre-commit, .gitignore mechanics, infrastructure setup quality

### Research
- `code-researcher` — codebase research for features (files, patterns, tests, integrations, risks)

### QA
- `pre-deploy-qa` — pre-deploy acceptance testing (tests + acceptance criteria)
- `post-deploy-qa` — post-deploy verification on live environment (MCP tools, AVP)

### Meta
- `skill-checker` — validates skills against skill-master standards

---

## Commands Reference

| Command | Purpose |
|---------|---------|
| `/interview` | Interview → user-spec.md |
| `/tech-plan` | Research → tech-spec.md |
| `/split-tasks` | Tech-spec → task files |
| `/do-task` | Execute single task with quality gates |
| `/do-all-tasks` | Execute approved tasks through parent-orchestrated isolated workers |
| `/done` | Update PK, archive feature |
| `/write-code` | Ad-hoc coding with TDD and reviews |
| `/init-project` | Initialize new project with template, git, GitHub |
| `/init-project-knowledge` | Fill all project documentation via project-planning skill |

---

## Workflow Quick Start

**New project:**
`/init-project` → `/init-project-knowledge` (interview + fill all docs) → start features

**New feature (full path):**
`/interview` → `/tech-plan` → `/split-tasks` → `/do-all-tasks` or `/do-task` → `/done`

**Direct or lean implementation:**
`/write-code`

To understand how a specific skill works internally, read its SKILL.md directly.
