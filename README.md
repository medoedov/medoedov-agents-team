# medoedov-claude-team

Spec-driven agent system for [Claude Code](https://claude.com/claude-code): team-lead orchestrator, specialist agents (architect, coder, reviewers, QA, sysadmin, etc.), project-knowledge skill, and sync tooling. Stack-agnostic — drop into any project, fill in the knowledge files, and start delegating.

## What's inside

```
.claude/
├── team-lead.md              # Team-lead protocol (the orchestrator brain)
├── consultant-base.md        # Shared base for read-only consultant agents
├── agents/                   # 26 specialist agents (one .md per agent)
├── commands/                 # Slash commands (/interview, /tech-plan, etc.)
├── skills/                   # Methodology skills + project-knowledge skeleton
├── shared/                   # Templates (interview, work, sync), shared scripts
└── hooks/                    # Optional Claude Code hooks
```

## Pipelines

- **Quick** (SMALL / MEDIUM tasks): `plan → coder → reviewers (parallel) → fix → commit`
- **Spec-driven** (LARGE features): `/interview → /tech-plan → /split-tasks → /do-all-tasks → /done`

## Quick start

1. Clone this repo as a sibling to your project, or copy `.claude/` into your repo's root.
2. Fill in `.claude/skills/project-knowledge/references/*.md` with your stack, architecture, patterns, deployment, UX guidelines.
3. Edit your `CLAUDE.md` to load the team-lead protocol on dev-related messages.
4. Send a feature request to Claude Code — the team-lead picks the pipeline.

See [MIGRATION.md](MIGRATION.md) for adapting the agents to a specific stack.

## Sync tooling

The `.claude/shared/scripts/sync_to_os.py` orchestrator keeps a private project's `.claude/` in sync with this public repo. Run from the private source with `.sync-config.local.yml` configured. See `.claude/commands/sync-os.md`.

## License

MIT — see [LICENSE](LICENSE).
