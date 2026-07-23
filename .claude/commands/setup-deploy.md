---
description: Bootstrap project infrastructure via infrastructure-setup skill; follow up with deploy-pipeline for CI/CD
allowed-tools:
  - Skill
---

# Instructions

Read and follow `.claude/shared/pipeline-contract.md` before taking action. Its durable-state rules and completion gate are mandatory.

1. Inspect the deployment request and present a concrete plan covering scope, environment, verification, secrets handling, maintenance-window constraints, rollback, and reporting.
2. Wait for explicit approval from the user for that plan.
3. After approval, delegate execution only to the `sysadmin` agent. Only the `sysadmin` agent may run SSH, Docker, infrastructure, CI/CD, or deployment commands; the Team Lead must not run them directly.
4. `infrastructure-setup` and `deploy-pipeline` are methodology skills that `sysadmin` loads and follows as applicable. They do not authorize the Team Lead to perform deployment work.
5. Require `sysadmin` to capture verification and rollback evidence, including the deployed revision/configuration, health checks, rollback target and procedure, and the outcome of any rollback test or readiness check.

## Durable State and Completion Gate

Persist the approved plan, approval evidence, sysadmin result, commands/actions summary with secrets redacted, verification output, deployment status, and rollback evidence as durable state required by `.claude/shared/pipeline-contract.md`.

Do not report completion until the pipeline contract's completion gate passes: approved work was performed by `sysadmin`, deployment and health verification succeeded, rollback evidence is present, and the durable report was written. Otherwise report the blocked, failed, or partial state and the safest next action.
