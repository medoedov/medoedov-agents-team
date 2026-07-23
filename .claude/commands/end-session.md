---
description: Persist a durable session handoff without changing pipeline status.
---

# End Session

Read `.claude/shared/pipeline-contract.md` first. Its durable state rules and
completion gate define which artifacts are authoritative.

## Collect state without mutating it

1. Inspect active feature artifacts: `feature-status.yml`,
   `logs/checkpoint.yml`, and `tasks-manifest.yml`, including each task's
   recorded frontmatter status.
2. Summarize completed work, pending task IDs, blockers, unresolved findings,
   verification evidence, and the next public command permitted by the
   contract.
3. Do not automatically change task, manifest, spec, checkpoint, QA, or feature
   status. Ending a session is a handoff operation, not completion evidence.

## Write the durable session report

1. Create `work/session-reports/` if needed.
2. Write a dated durable report such as
   `work/session-reports/YYYY-MM-DDTHHMMSSZ.yml`. Include:
   - report timestamp and current branch;
   - active feature paths;
   - pointers to each status/checkpoint/manifest artifact;
   - completed actions from this session;
   - pending task IDs, blockers, and unresolved findings;
   - the recommended next public command.
3. Write `work/session-reports/latest.yml` as a small pointer containing only
   the dated report path and timestamp. Update it atomically: write a temporary
   file in `work/session-reports/`, flush/close it, then rename it over
   `latest.yml`. Never partially overwrite the existing pointer.
4. If `work/backlog.md` is used, store backlog pointers and task IDs only. Do
   not copy requirements, task bodies, findings, or statuses into it. The
   approved specs, manifests, and feature status collectively remain
   the single source of truth.

## Report to the user

Return a concise summary with the dated report path, work completed, work still
pending, blockers, and the recommended next public command. State explicitly
that this command did not change task or feature completion status.
