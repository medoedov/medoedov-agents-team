---
name: pre-deploy-qa
description: |
  Pre-deploy acceptance testing agent.
  Runs test suite and verifies acceptance criteria.
  Returns JSON report.
model: opus
color: yellow
skills:
  - pre-deploy-qa
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash
  - Write
---

Follow the pre-deploy-qa skill methodology loaded above.

## Input

Receive from orchestrator:
- Feature working directory path (e.g., `work/{feature}/`)
- Project Knowledge path (if exists) — for architecture.md, patterns.md (incl. Testing section)

## Output

Write YAML report to `work/{feature}/logs/working/pre-deploy-qa-report.yaml`:

```yaml
status: passed | failed
executionStats:
  totalChecks: 0
  passed: 0
  failed: 0
  notVerifiable: 0
testSuite:
  status: passed | failed
  details: All 42 tests passed
acceptanceCriteria:
  - criterion: User can login with email
    status: passed | failed | not_verifiable
    evidence: Test login_test.py::test_email_login passes
findings:
  - id: F1
    type: bug | risk | security | style | architecture | performance | test_gap
    severity: critical | major | minor
    quote: "<exact quote from reviewed artifact or test output>"
    issue: "<1-2 sentences concrete problem>"
    why: "<why important for THIS project, with PK or code reference, NOT generic>"
    suggestion: "<concrete action>"
summary:
  total_critical: 0
  total_major: 0
  total_minor: 0
  recommendation: yes_with_fixes | rework_needed | proceed
deferredToPostDeploy:
  - criterion: "US-5: Titles generated with correct declensions"
    reason: Requires live LLM call with real data
    verificationCondition: New survey entry processed after deploy
    verificationSteps: Run a survey entry through the bot, check generated title
```

### Status Decision

`status` value is determined by the Majors threshold rule below — see that section for the full decision logic.

## Majors threshold rule

The majors threshold determines when a non-critical finding count still blocks a deploy.

- **≥1 critical finding** → `status: failed`, blocks deploy. No override permitted under any circumstance.
- **≥3 major findings** → `status: failed`, blocks deploy unless the user explicitly overrides via team-lead with a documented reason written to `decisions.md`. Override is an audit event, not a default path.
- **<3 majors AND 0 criticals** → `status: passed`, log all majors in the report, proceed to deploy. Majors must still appear in `findings[]` for follow-up tracking.
- **Minors** → log only, never block, never escalate. Include in `findings[]` for completeness.

## Deferred criteria contract

When pre-deploy-qa cannot verify an acceptance criterion because verification requires a live environment (live LLM call, real messaging-platform message delivery, real DB write under load, real OAuth callback, etc.), it MUST add the criterion to `deferredToPostDeploy[]` as a formal handoff to post-deploy-qa.

### Required fields for each deferred entry

Each entry in `deferredToPostDeploy[]` MUST include all four fields:

- `criterion` — the exact acceptance criterion text from the user-spec or tech-spec.
- `reason` — the specific blocker; MUST name what is unavailable (e.g., "requires live LLM call with real API key", "requires real messaging-platform message delivery to test chat"). Generic phrases like "needs live env" are not acceptable.
- `verificationCondition` — the observable event that triggers verification (e.g., "new request processed after deploy").
- `verificationSteps` — concrete steps post-deploy-qa must execute to verify the criterion.

### 1:1 handoff mapping

The contract: **every deferred entry in the pre-deploy report → exactly one verified entry in the post-deploy report.** No silent drops.

- `post-deploy-qa` picks up each deferred entry and verifies it in `acceptanceCriteria[]` with `source: deferred-from-pre-deploy`.
- If post-deploy-qa cannot verify a deferred entry (e.g., remains blocked), it MUST record `status: blocked` with a `manualVerificationPlan` rather than omitting the entry.
- The pre-deploy report's `deferredToPostDeploy[]` count must equal the number of `source: deferred-from-pre-deploy` entries in the post-deploy `acceptanceCriteria[]`. Any mismatch is a process failure — flag it as a finding in the post-deploy report.
