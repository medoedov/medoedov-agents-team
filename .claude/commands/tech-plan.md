---
description: Produce technical plan (tech-spec.md) from approved user-spec.
allowed-tools:
  - Skill
---

# Instructions

Read and follow `.claude/shared/pipeline-contract.md` before taking action. Use the `tech-planning` skill without weakening its gates.

Fail closed unless the existing `work/{feature}/user-spec.md` durably records `user-spec.status: approved`. Missing, malformed, stale, or draft input must stop before mutation; do not create the feature folder or tech-spec while the input gate is unmet.

## Durable Output/State

The durable output is `work/{feature}/tech-spec.md`, the disjoint validator reports at `work/{feature}/logs/tech-plan/validator-reports/{validator}-round{N}.json`, and the parent-owned aggregate. Record explicit approval by changing the tech-spec frontmatter to `status: approved` only after validation and user approval.

## Completion Gate

Completion requires bounded validation to pass, parent aggregation of the disjoint reports, explicit user approval to be durably recorded, and `tech-spec.status: approved`. A draft, a chat response, or file existence is not completion.

## Next Allowed Transition

After the completion gate passes, offer `/split-tasks`, `/advisor`, or an explicit `/tech-plan` revision. Otherwise stop at the last valid durable state and report the unmet gate.
