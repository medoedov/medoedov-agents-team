# Project: [PROJECT NAME]

> [ONE SENTENCE — what this project is about]

## Language
- User communication: [user-facing language]
- Tech docs, agent prompts, files inside `.claude/`: [tech docs language]
- AI prompts (system prompts shipped to LLMs): [LLM prompt language]

## Classifier
Load rules — apply per turn, lazy-load only what matches.
- Slash command (e.g. `/interview`, `/tech-plan`, `/do-task`) → load `.claude/commands/{name}.md`; the command spec decides what skill to spawn.
- Dev-related message (feature request, bug report, code question, refactor) → load `.claude/team-lead.md` (root); team-lead applies its own classifier to pick the pipeline.
- Project-knowledge question (stack, deploy, patterns, UX, architecture) → lazy-load the matching `.claude/skills/project-knowledge/references/{file}.md` only. Do not load others.
- First-run / empty project-knowledge: if `.claude/skills/project-knowledge/references/project.md` is missing, a placeholder, or has <200 chars of non-placeholder content, AND the user sends a dev-related message → proactively offer `/init-project` as a one-line suggestion. Never auto-run.
- Fresh project + 30s idle after harness start (no user message yet) → team-lead emits a proactive opener via its own heuristic (declarative; do not schedule a wakeup or background timer).
- User confirms exit from Plan Mode → start delegation per `team-lead.md`.

## Critical Rules
- [Add project-specific deploy/safety rules here — e.g., deploy windows, who can push, mandatory review gates.]
- [Add a delegation rule here if this project requires the team-lead to route code edits through a coder agent — otherwise delete this line.]
- [Add a planning rule here if this project requires explicit user approval before implementation — otherwise delete this line.]

## What's where
- Team Lead protocol → `.claude/team-lead.md`
- Project facts (stack, architecture, patterns, deployment, UX) → `.claude/skills/project-knowledge/references/{project,architecture,patterns,deployment,ux-guidelines}.md`
- Engineering principles (code style, anti-patterns) → `.claude/skills/project-knowledge/references/engineering-principles.md`
- Agent specs → `.claude/agents/{name}.md`
- Skills (methodology, code-writing, reviews, etc.) → `.claude/skills/{name}/SKILL.md`
- Feature work (specs, decisions, tasks, logs) → `work/{feature}/`

## Available Commands
- /interview, /tech-plan, /split-tasks — spec-driven planning
- /do-task, /do-all-tasks, /done — implementation and finalization
- /init-project, /setup-deploy — project bootstrap
- /start-session, /end-session, /write-code, /init-project-knowledge — session and authoring helpers
