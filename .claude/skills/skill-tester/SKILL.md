---
name: skill-tester
description: |
  Execute test scenarios prepared by skill-test-designer. Spawns parallel
  runners with and without the skill, interacts as user persona, grades
  acceptance criteria, produces detailed test report.

  Use when: "запусти тесты для скилла", "run skill tests", "execute skill
  scenarios", "проверь скилл тестами"
---

# Skill Tester

Execute test scenarios prepared by skill-test-designer.
You are team lead, user actor, and grader — all in one.

## Input

Scenario files at: `~/.claude/skill-tests/{skill-name}/scenarios/`
If no scenarios found → tell user to run skill-test-designer first.

## Phase 1: Prepare

1. Read ALL scenario files from the scenarios directory
2. Read the target skill's SKILL.md + key references
   You need to deeply understand what the skill instructs agents to do:
   - Which phases must agents follow and in what order?
   - Which references must agents read?
   - What outputs must agents produce?
   - What checkpoints must agents hit?
3. Read the persona from scenarios (your acting role)
4. If anything is unclear — ask the user before proceeding

**Checkpoint:** You can list all scenarios, the skill's phases, required
references, expected outputs, and your persona. If any are unclear, resolve
before proceeding.

## Phase 2: Setup

1. The parent builds a bounded plan: per scenario = 2 runners with the tested skill + 1 baseline without it.
2. For A/B fairness, the three runners receive the same base prompt, persona answers, initial workspace snapshot, tools/capabilities, time budget, and runtime/model conditions. The only intended difference is access to the tested skill.
3. A scenario's runners use isolated workspaces and disjoint result-artifact paths. They may run in parallel only when isolation is guaranteed and available slots permit it; otherwise the parent runs them in a balanced sequential order with the same reset state. Scenarios run sequentially.
4. The scenario's requested model is a preference only when the current runtime supports explicit model selection. Otherwise use the same actual runtime/model for all variants and record the deviation; never claim an unsupported override.
5. Show the plan to the user: "I'll run {N} scenarios, {M} runners total under the same recorded runtime conditions. Proceed?"

**Checkpoint:** User confirmed the execution plan; isolation, slot budget, and A/B controls are recorded.

## Phase 3: Execute

For each scenario:

### 3a. Spawn runners
The parent spawns three bounded isolated workers using the current runtime primitive and explicit runner-role instructions:

- Skill runner A and skill runner B receive the natural scenario prompt and access to `{tested-skill-name}`.
- The baseline receives the same prompt and context but no access to the tested skill.
- Each runner writes a transcript/result artifact to its own path under the scenario's run directory and returns that path to the parent.
- Runners do not share state, communicate with one another, or spawn additional workers.

The parent records the runtime handle and result-artifact path for each runner so grading never depends on an in-memory message alone.

### 3b. Interact as user
When the current runtime supports interaction, answer runner questions in character per the scenario's persona. Otherwise inject the same deterministic persona answers into each isolated run. Rules:
- Stay in character: answer as the user would
- Be consistent: same question from different runners → same answer
- Answer naturally, as a real user would — without guidance toward any
  specific behavior
- Keep conversation purely about the task itself (the feature, the question,
  the request)
- Baseline runner may ask different questions (no skill to guide it) — this
  is expected, answer them too

### 3c. Grade via grader agents

When all three runners finish, the parent schedules one isolated grader worker per runner using the current runtime primitive. Graders receive explicit grader-role instructions, minimal read-only evidence, and disjoint evaluation-artifact paths. They do not share state or spawn additional workers.

Each grader receives:

1. The runner's durable transcript/result-artifact path or runtime-supported read-only transcript handle, including tool calls and created outputs
2. The scenario's acceptance criteria (copy the criteria list into the prompt)
3. The skill's SKILL.md path (grader reads it for compliance check)
4. Whether this is a skill-runner or baseline
5. Its own evaluation-artifact path, returned to the parent after grading

Grader returns a structured evaluation:

```
## Acceptance Criteria
| # | Criterion | Verdict | Evidence |
|---|-----------|---------|----------|
| 1 | WebFetch  | PASS    | "Tool call #3: WebFetch(url='https://...')" |
| 2 | Read INDEX| PASS    | "Tool call #7: Read('vault/knowledge/INDEX.md')" |

## Skill Compliance
| Phase | Executed | Evidence |
|-------|----------|----------|
| 1. WebFetch | YES | call #3 |
| 2. Topic routing | YES | call #7: Read INDEX.md |

## References Read
- TAGS.md: YES (call #9)
- notes.md: NO (never read)

## Files Created
- vault/knowledge/example.md — frontmatter: {type, tags, source, created}
```

Grader rules (include in grader prompt):
- **PASS** requires clear evidence: a specific tool call, file content, or
  message. Quote it directly.
- **FAIL** when no evidence found, evidence contradicts criterion, or only
  surface compliance (correct format, wrong substance).
- **When uncertain: FAIL.** Burden of proof is on the criterion.
- For process criteria: cite specific tool calls with arguments
- For outcome criteria: cite file content (read the created files)
- For compliance criteria: cite Bash calls for scripts

The parent runs graders in parallel only when their inputs and outputs are independent and available slots permit it; otherwise it uses bounded batches. Wait for all evaluation artifacts, then aggregate them centrally.

### 3d. Compile results

You now have 3 structured evaluations (one per runner). Do NOT re-read
transcripts. Using only the grader outputs:

1. Build the results table (criteria × runners)
2. Cross-runner consistency: where did skill-runners diverge?
3. Baseline comparison:
   - Passed by skill-runners ONLY → skill adds value
   - Passed by ALL → criterion too easy or skill doesn't help
   - Failed by ALL → criterion may be unrealistic
   - Passed by baseline ONLY → skill might be harmful
4. Identify skill issues and ambiguities

### 3e. Cleanup
Release all runtime workers and isolated workspaces for this scenario after their durable artifacts are verified. Do not depend on shared team state for cleanup.

## Phase 4: Report

Compile results from all scenarios following
[report-template.md](references/report-template.md).

Save to: `~/.claude/skill-tests/{skill-name}/reports/{timestamp}-report.md`
Show report to user.

## Self-Verification

- [ ] All scenarios executed (2 skill-runners + 1 baseline each)
- [ ] Grader agents used for transcript analysis (not read by lead directly)
- [ ] Every criterion graded with cited evidence from tool call transcripts
- [ ] Skill compliance checked for each runner
- [ ] Baseline comparison completed per criterion
- [ ] Report saved to expected path and shown to user
- [ ] Runtime workers released after durable runner and grader artifacts were verified
