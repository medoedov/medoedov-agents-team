# medoedov-claude-team

Spec-driven agent system for [Claude Code](https://claude.com/claude-code) and
[OpenAI Codex](https://developers.openai.com/codex): team-lead orchestrator,
specialist agents (architect, coder, reviewers, QA, sysadmin, etc.),
project-knowledge skill, and safe sync tooling. One methodology, two runtimes.

## Two runtimes, one source

- **Editable source:** `CLAUDE.md` and `.claude/**`.
- **Generated Codex runtime:** `AGENTS.md`, `.agents/skills/**`, and managed
  `.codex/**` files.
- Do not edit generated files directly. Change the Claude-side source and run
  `python .claude/shared/scripts/sync_to_codex.py --project . --apply --prune`.

Codex uses native subagents, skills, project instructions, and hooks. The root
agent owns work waves, checkpoints, aggregation, and conflict resolution; do
not assume Claude Agent Team shared state is available in Codex.

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

.agents/skills/               # Generated methodology + command adapters

.codex/                       # Generated runtime config — do not edit
├── agents/                   # Native Codex subagents (*.toml)
├── hooks/                    # Adapted lifecycle hooks
└── .sync/                    # Ownership hashes and drift protection

AGENTS.md                     # Generated Codex project instructions
```

## Pipelines

- **Quick** (SMALL / MEDIUM tasks): `plan → coder → reviewers (parallel) → fix → commit`
- **Spec-driven** (LARGE features): `/interview → /tech-plan → /split-tasks → /do-all-tasks → /done`

## Quick start

1. Clone this repo as a sibling to your project, or copy `CLAUDE.md`, `.claude/`, `AGENTS.md`, `.agents/`, and `.codex/` into your repo's root.
2. Fill in `.claude/skills/project-knowledge/references/*.md` with your stack, architecture, patterns, deployment, UX guidelines.
3. Edit your `CLAUDE.md` to load the team-lead protocol on dev-related messages.
4. Regenerate the Codex runtime after filling Project Knowledge.
5. Send a feature request to Claude Code or Codex — the team-lead picks the pipeline.

See [MIGRATION.md](MIGRATION.md) for adapting the agents to a specific stack.

## Sync tooling

The maintainer-side `sync_to_os.py` orchestrator keeps a private project's
Claude source in sync with this public repo. It runs from the private source
with `.sync-config.local.yml` configured; see `.claude/commands/sync-os.md`.
The public Codex runtime is generated from the already-sanitized target, never
copied from the private project's generated files.

`sync_to_codex.py` is the deterministic Claude → Codex transformation. It:

- converts Claude agents to native Codex TOML agents;
- adapts methodology skills and slash commands into `.agents/skills/**`;
- generates the `team-lead` skill, hooks, config, and `AGENTS.md`;
- rejects secret-looking or symlinked sources;
- records ownership hashes and refuses to overwrite independent edits;
- supports preview, drift checking, safe pruning, and idempotent regeneration.

```bash
# Preview
python .claude/shared/scripts/sync_to_codex.py --project .

# Generate
python .claude/shared/scripts/sync_to_codex.py --project . --apply --prune

# CI / pre-commit drift check
python .claude/shared/scripts/sync_to_codex.py --project . --check
```

## License

MIT — see [LICENSE](LICENSE).
