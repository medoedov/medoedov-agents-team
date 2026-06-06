# Migrating to your stack

The agents and skills in `.claude/` are stack-agnostic by design. All project-specific facts — frameworks, libraries, deploy paths, environment variables, conventions — live in two places:

1. `.claude/skills/project-knowledge/references/*.md` — six skeleton files (project, architecture, patterns, deployment, ux-guidelines, engineering-principles).
2. `.claude/agent-memory/{agent}/MEMORY.md` — per-agent learning that accumulates over time.

Both ship as empty skeletons. Agents read them to derive concrete failure modes, paths, and constraints; if you leave them empty, agent output stays generic.

## First-pass setup (15-30 minutes)

1. **Fill `project-knowledge/references/project.md`** — one paragraph on what the product is, current state, value proposition.
2. **Fill `references/architecture.md`** — tech stack with versions, top-level directory layout, external services.
3. **Fill `references/patterns.md`** — code conventions, anti-patterns, integration points. Include API client locations (e.g., where you call LLM providers, your DB driver, your cache).
4. **Fill `references/deployment.md`** — how production runs: hosting, deploy command, deploy window if any, rollback path.
5. **Edit `CLAUDE.md`** — minimal pointer file; the template ships ready, just check the project name.

## Adapting agents

Most agents work as-is. A few have project-tinted defaults that may surprise you:

- **`agents/sysadmin.md`** — the deploy-window enforcement (currently a placeholder 22:00-07:00 MSK) reflects a 24/7 user-facing product. If your product has different traffic patterns, edit the window or remove the time gate entirely.
- **`agents/test-writer.md`** — the "Project handler edge cases" list is categorical but assumes a chat-bot-shape product (user input, AI API, rate limits). Translate to your domain (REST handler, queue consumer, etc.).
- **`agents/ux-designer.md`** — assumes a messaging-platform UI. If your product is web/CLI/desktop, the markup-safety section and message-length-limit guidance need re-keying via your `ux-guidelines.md`.

## Replacing agents

If an agent doesn't fit your workflow, delete its `.md` and any references in:

- `.claude/team-lead.md` (orchestration logic)
- `.claude/commands/*.md` (commands that spawn that agent)
- Other agents' files (cross-references)

A simple grep finds them: `grep -rn "agent-name" .claude/`.

## Adding a new agent

Use `agents/marketer.md` or `agents/product-manager.md` as a template — both are fully generalized. Frontmatter conventions:

```yaml
---
name: <agent-name>
description: <one-line role for the team-lead's classifier>
model: opus | sonnet | haiku
color: <ui-color>
allowed-tools: [Read, Glob, Grep, ...]
memory: project | none
---
```

Then add the agent to relevant slash commands in `.claude/commands/`.

## Sync tooling

If you want to keep a private project's `.claude/` synced with this OS template (e.g., you maintain both):

1. In your private project, copy `.claude/shared/sync-templates/sync-config.example.yml` to `.sync-config.local.yml` (gitignored).
2. Set `sources[0].path` to your private repo root, and `target_path` to your local clone of this OS repo.
3. Run `python .claude/shared/scripts/sync_to_os.py --dry-run` to preview.
4. Run without `--dry-run` to perform the sync (creates a commit in target).
5. Review the diff in target, then push.

The `--self-check` flag runs three idempotent dry-runs in a temp dir as a sanity test.
