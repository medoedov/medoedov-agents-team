---
name: interview-planning
description: |
  Creates user-spec.md through an adaptive interview with prior-chat seeding, classification
  gate, mandatory specialist checkpoints, smart routing, and unified validation.

  Primary trigger: /interview

  Use when: "сделай юзер спек", "проведи интервью для юзер спека",
  "создай юзерспек", "user spec", "detailed planning", "хочу продумать фичу",
  "опиши требования к фиче", "сделай описание фичи", "/interview"

  For tech planning use tech-planning. For task decomposition use task-decomposition.
---

# Interview Planning

Thorough adaptive interview → codebase scan → user-spec.md → unified validation → user approval.
Output: `work/{feature}/user-spec.md` with `status: approved`.
Log: `work/{feature}/logs/interview.yml` (flat path).

## Interview Style

Conduct the interview in the user's language. Be thorough and opinionated — an engaged
co-thinker who actively proposes solutions and challenges weak answers.

**How to interview:**
- Ask 3-4 questions per batch. Run as many batches as needed until the cycle's items are
  fully covered.
- Propose solutions based on Project Knowledge: "The architecture.md describes pattern X —
  I think Y is the right approach here. Agree?"
- Challenge with substance — concrete counterexamples, code references, unexplored scenarios:
  "What if the user does Z? Module Q does not handle that case."
- Accept the answer after one substantive challenge and move on to the next gap.
- When user says "I don't know": help think through it (examples, common patterns).
  Optional item → mark TBD. Required item → break into simpler questions.

**Interview depth** depends on feature size (S/M/L in interview metadata):
- S (1-3 files, local fix): focused interview, core behavior
- M (several components): moderate depth, integration questions
- L (new architecture): deep interview, thorough edge cases and risk analysis

## Process

### Specialist Output Contract

These rules apply to every specialist invocation across phases — product-manager (Phase 2),
ux-designer (Phase 4), Phase 5 routing, and userspec-validator (Phase 6 + Phase 8).

#### Output Gate

Apply this gate whenever a specialist (product-manager, ux-designer, marketer, architect,
security-auditor) returns findings. Reject the output if ANY of the following is true:

- No `quote` field present in a finding (finding lacks grounding in the artifact).
- `why` field is generic, missing, or sycophantic (e.g., "good idea but...", "interesting
  approach", "this is fine overall").
- Finding is a rephrase of the task description, not a critique.
- Total findings count is fewer than 3 for Standard-class work.

**Rejection example (valid finding vs. rejected finding):**
```
Valid:   {id: f1, severity: major, quote: "users can export", issue: "export format
          unspecified", why: "CSV and JSON have incompatible tooling expectations — a
          spreadsheet user vs. a developer will assume a different default"}
Rejected: {id: f2, severity: minor, issue: "consider adding more formats",
           why: "good idea but worth thinking about"}
          → rejected: no `quote`, `why` is generic/sycophantic
```

**On rejection:** re-prompt the same specialist (same prompt + addendum:
"Previous output rejected: {reasons}. Provide specific, grounded findings.") up to 2
retries maximum.

**After 2 failed retries:** escalate to the user with the raw specialist output and the
rejection reasons. Do not silently drop the specialist's work.

#### Output Handling

After specialist findings pass the Output Gate, transform 5-15 validated findings into
3-5 conversational questions per round:
- Each question ties to a specific finding's `issue` and `suggestion`.
- Questions are short, contextual, and natural — not yaml dumps.
- Goal: continue the interview without overwhelming the user.

<example>
Finding (yaml): {id: f3, severity: major, quote: "users can export", issue: "export format
  unspecified", suggestion: "specify CSV vs JSON vs both"}
Question to user: "You mentioned export — should we support CSV, JSON, or both? Different
  audiences (spreadsheet users vs developers) have different defaults."
</example>

---

### Phase 0: Init

#### Prior-chat seed (Scenario B)

Before loading the interview template, scan the current session chat history. For each item
in the feature template (see `.claude/shared/interview-templates/feature.yml`), if the user
has already provided substantive content during free chat — pre-fill that item's `value` and
`score` (range 60-80% depending on detail level), and mark the gap as
"verified in chat, may need deepening". Write seeded items to `logs/interview.yml` at init
time. Skip interview questions for items that are already seeded to threshold.

Prior-chat seeding: existing chat history is scanned to pre-populate interview state before
Phase 1 begins, using scores in the 60-80% range.

#### Init flow

1. Check for existing interview: look in `work/*/logs/interview.yml` for
   `metadata.status: in_progress`. If found — load, show discussed topics summary, resume.
   If multiple found — show list, let user choose.
2. Get task description: "Describe what you want to build."
3. Determine work_type (feature / bug / refactoring) from description.
4. Propose feature name (kebab-case).
5. **Confirmation Gate:** After the user describes the feature, reply with:
   > "Understood as: **{name}**. Should I create folder `work/{name}/`? (yes / no / edit-name)"

   Wait for explicit `yes` before invoking `init-feature-folder.sh`.
   On `no` — abort cleanly, no folder created (Scenario D protection).
   On `edit-name` — ask for the corrected name, then re-confirm.
6. After `yes`: run `.claude/shared/scripts/init-feature-folder.sh {name}` — creates folder
   structure with `logs/interview.yml`.
7. Update `logs/interview.yml`: set `metadata.started`, `metadata.status: in_progress`,
   `phase1_feature_overview.feature_name`, `phase1_feature_overview.work_type`. Write seeded
   items from prior-chat scan.

### Classification Gate

After the user confirms intent and the feature folder is created, classify the work along two
independent axes before doing anything else.

**Class** (drives whether specialists run at all):

| Class | Criteria | Pipeline |
|-------|----------|----------|
| **Trivial** | 1 file scope, no UX changes, no payment, no security-sensitive data | Solo interview; mandatory checkpoints SKIPPED; no specialist routing |
| **Standard** | Anything else | Full mandatory checkpoints scheme + conditional smart routing |

Trivial implies size S by definition. If work grows beyond one file mid-interview,
reclassify as Standard.

**Size** (drives interview depth): S / M / L per `interview_depth_policy` in
`feature.yml`.

Announce the classification and allow the user to override:
> "Classified as **Standard / M** — full interview with product-manager and ux-designer
> review. OK?"

If the user explicitly says "trivial" or "standard" — honor the override.

The trivial vs standard classification gate determines which specialist agents run and
whether mandatory checkpoints fire at all.

### Phase 1: Study Project Knowledge

Read ALL files from `.claude/skills/project-knowledge/references/`. If the directory is
missing or empty — warn the user and suggest running `/init-project-knowledge` first.

These files are your context for the entire interview. Reference them when asking questions
and proposing solutions.

### Phase 2: Cycle 1 — General Understanding

**Scope:** `phase1_feature_overview` items in `logs/interview.yml`.

1. Score the user's initial description against all items (detailed 80-95%, brief 50-70%,
   vague 20-40%, not mentioned 0%). Items already seeded from prior-chat start at their
   seeded score.
2. Run the interview loop (see below) on `phase1_feature_overview` items.
3. During this cycle — determine feature size S/M/L and agree on testing strategy:
   - S: integration/E2E usually not needed — state why.
   - M: propose whether integration tests make sense, explain reasoning.
   - L: propose specific integration and E2E scope with justification.

#### Mandatory checkpoint — product-manager (Standard, size M or L)

After Cycle 1 completes (for Standard-class work of size M or L), spawn `product-manager`
as a mandatory checkpoint. S features run a short interview without checkpoints because the
surface is too small for product/UX critique to surface anything new.

- Input: draft sections 1-2 of the emerging user-spec (problem statement, value prop).
- Task: critique the framing, surface blind spots, name competitor approaches, validate PMF.
- Run as a single-turn `Agent` call.
- Apply the Output Gate (Specialist Output Contract above) before consuming findings.
- Transform validated findings → 3-5 conversational questions for the next interview round
  (see Output Handling in Specialist Output Contract above).

### Phase 3: Code Scanning

Launch `code-researcher` subagent (Task tool, opus) with feature path and feature description
from Cycle 1.

After the subagent completes — read `{feature_path}/code-research.md`. Use findings in
Cycle 2 questions.

If during later phases a gap is discovered — launch `code-researcher` again with the specific
question to investigate.

### Phase 4: Cycle 2 — Code-Informed Refinement

**Scope:** `phase2_user_experience` + `phase3_integration` items.

1. Summarize understanding: "I understand the task as: [X]. My implementation approach: [Y,
   based on code findings]."
2. Questions based on code findings: "Found module X which does Y — should we reuse it?"
3. Cover deploy and user actions (items `deploy_approach`, `manual_user_actions`):
   - "Are there manual steps required to launch? (create a bot, get API keys, configure
     a service, register somewhere)"
   - "How should this be deployed? What needs to be configured? (existing CI/CD, new setup,
     manual deploy)"
   - "How do we verify it works after deploy? (tools, curl, manual check)"
   - "What can be verified during development without a deploy? (call external API locally,
     run locally, check config, test the prompt)"
4. Run interview loop on phase2 + phase3 items.

#### Mandatory checkpoint — ux-designer (Standard, size M or L, UI/UX only)

After Cycle 2 completes, if the feature has any user-visible interface changes (for
Standard-class work of size M or L):
- Spawn `ux-designer` as a mandatory checkpoint.
- Input: description of UI flows, interaction patterns discovered in Cycle 2.
- Task: review flows, surface friction points, suggest alternative patterns.
- Run as a single-turn `Agent` call.
- Apply the Output Gate (Specialist Output Contract above) before consuming findings.
- Transform validated findings → 3-5 conversational questions for the next round.

### Phase 5: Cycle 3 — Review and Finalize

**Scope:** ALL items across all phases still below threshold.

Cleanup pass: revisit anything not fully covered in Cycles 1-2. Deepen edge cases and error
scenarios — probe for scenarios the user has not considered, even if items formally passed
threshold.

Run interview loop on remaining gaps.

#### Smart routing (Phase 5 specialists)

After Cycle 3, spawn additional specialists when the following conditions are met. Multiple
triggers → multiple specialists in parallel. Always announce before spawning:
"Asking {specialist} for input — about 30 seconds."

Triggers: marketer on paid feature, architect on L feature, security-auditor on sensitive
data.

| Trigger | Specialist | Condition |
|---------|-----------|-----------|
| Paid feature | `marketer` | Feature involves subscriptions, payments, limits, or pricing changes |
| L feature | `architect` | Feature is size L, introduces new architecture, or spans a new microservice |
| Sensitive data | `security-auditor` | Feature handles PII, auth tokens, secrets, or payment data |

Smart routing applies to Standard-class work only; for Trivial class, skip all smart
routing.

Apply the Output Gate (Specialist Output Contract above) to each specialist's findings
before consuming them. Transform validated findings → 3-5 conversational questions per
specialist per round.

### Phase 6: Completeness Check

Launch `userspec-validator` subagent (Task tool) with feature path. It reviews
`logs/interview.yml` against PK files and `code-research.md`.

Input: `logs/interview.yml` (interview is the artifact under review at this stage;
user-spec.md does not exist yet). Goal: gate ready-to-write.

- `needs_more` → ask the suggested questions, re-run
- `complete` → proceed to Phase 7

### Phase 7: Create User Spec

1. Copy template to working file:
   - Copy `.claude/shared/work-templates/user-spec.md.template` → `work/{feature}/user-spec.md`
   - Edit sections one by one using Edit tool, replacing placeholders with interview data.
   Reason: the agent sees the template structure and comments while editing each section,
   preventing drift from template format.
2. Content rules:
   - "What we are doing" — self-contained, understandable without reading the interview.
   - "Why" — concrete user value, not vague improvement claims.
   - Acceptance criteria — testable, no "works correctly".
   - Every discussed topic from the interview must appear in the spec.
3. If the feature seems large (>10 criteria, >3 user flows, >5 integrations) — suggest
   splitting.

Git commit: `draft(userspec): create user-spec for {feature}`

### Phase 8: Validation

Run `userspec-validator` (single agent, three dimensions: quality / adequacy / completeness).
It returns a unified findings list in one combined JSON report.

Input: `user-spec.md` (post-write artifact). Goal: gate ready-to-approve. Same agent,
different artifact — Phase 6 catches missing interview coverage, Phase 8 catches drift
introduced during spec authoring.

**`userspec-validator`** is the single merged validator (Wave 3 Task 9). `userspec-validator`
is the only validator for user-spec quality, adequacy, and completeness — it merged three
previous single-dimension validators in Wave 3 Task 9.

**Handling findings:**
- Obvious issue → fix silently.
- Borderline → discuss with user.
- Disagree with finding → reject with reasoning.
- Conflict across dimensions → adequacy findings take priority over quality findings on
  substance vs form disputes.

After each validation round (validator ran + fixes applied), git commit:
`chore(userspec): validation round {N} — {summary of fixes}`. Re-run `userspec-validator`.
Max 3 iterations, then show remaining issues to the user.

### Phase 9: User Approval

Show `user-spec.md` link + validation summary. If changes requested — edit and show again.

When approved:
1. Set `user-spec.md` frontmatter `status: approved`.
2. Set `logs/interview.yml` `metadata.status: completed`.
3. Git commit: `chore(userspec): approve user-spec for {feature}`
4. Suggest `/tech-plan {feature-name}` as the next step.

## Interview Loop

Runs inside each cycle. Repeats until the cycle's scope is fully covered.

```
1. Find gaps: required items in current scope with score < 85%. Lowest score first.
2. Ask 3-4 questions about different gaps. Reference PK and code findings.
3. User responds.
4. Update logs/interview.yml:
   - conversation_history: add full Q&A entry
   - Item: score, value, gaps, status
   - metadata: last_updated, current_question_num
   - Save immediately after every response.
5. Check stop criteria (BOTH must be true):
   a) All required items in scope score >= 85%
   b) Structural: every required item has non-empty value,
      no TBD in value, gaps empty or only conscious limitations
6. Not done → step 1. Done → exit cycle.
```

Scoring: detailed answer 80-95%, brief 50-70%, vague 20-40%, not mentioned 0%.
Prior-chat seeded items start at their seeded score (60-80%).

Optional items: cover when the user mentions relevant context or when naturally connected
to required items.

## Work Type Adaptations

All three cycles apply to any work_type, but focus shifts:

**Bug:** Cycle 1 → reproduction steps, expected vs actual, severity, when it broke.
Code scanning → find bug location and root cause. Cycle 2 → fix approach, regression risks.

**Refactoring:** Cycle 1 → current problems, target architecture, stability guarantees.
Code scanning → current structure, dependencies, test coverage.
Cycle 2 → migration path, backward compatibility.

## Scope Changes

If understanding changes significantly during the interview:
- Update affected scores downward, add new gaps.
- Reassess feature size (S/M/L).
- If work_type changes (was feature, actually bug) — pivot items accordingly.
- Note the change in `logs/interview.yml` notes section.
- If reclassifying from Trivial to Standard — activate mandatory checkpoints going forward.

## Self-Verification

- [ ] Prior-chat seed applied: items from existing chat history pre-filled at 60-80% score
- [ ] Confirmation Gate passed: user explicitly said yes before `init-feature-folder.sh` ran
- [ ] Classification set: Trivial or Standard (announced + user acknowledged)
- [ ] All three cycles completed: Cycle 1 (phase1 items >=85%), Cycle 2 (phase2+phase3 items
      >=85%), Cycle 3 (cleanup pass on residual gaps)
- [ ] Mandatory checkpoints invoked: product-manager after Phase 2 (Standard + M/L),
      ux-designer after Phase 4 (Standard + M/L + UI/UX)
- [ ] Output Gate applied to all specialist findings
- [ ] Smart routing specialists consulted where triggered (Phase 5) — Standard only
- [ ] `userspec-validator` passed (or issues resolved with user) — three dimensions
- [ ] `user-spec.md` filled with real content (no placeholders)
- [ ] User approved, frontmatter `status: approved`
- [ ] `logs/interview.yml` `metadata.status: completed`
- [ ] All log files at flat path `work/{feature}/logs/interview.yml` (flat, no subdirectory nesting)
- [ ] Suggested `/tech-plan` as next step
