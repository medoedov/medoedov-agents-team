# Project: [PROJECT NAME]

> **[ONE SENTENCE - WHAT THIS PROJECT IS ABOUT]**

---

## How This Project Works

**Context:** All project knowledge is in `.claude/skills/project-knowledge/` skill with guides for architecture, patterns, and deployment (+ optional UX guidelines and domain-specific files).

**Default branch:** `dev`

**Library Documentation:** Always use context7 when you need code generation, setup or configuration steps, or library/API documentation. This means you should automatically use the Context7 MCP tools to resolve library id and get library docs without user having to explicitly ask.

## Dual runtime

`CLAUDE.md` and `.claude/**` are editable sources. If this project contains
`.claude/shared/scripts/sync_to_codex.py`, regenerate `AGENTS.md`, `.agents/**`,
and managed `.codex/**` after changing agent instructions or Project Knowledge:

```bash
python .claude/shared/scripts/sync_to_codex.py --project . --apply --prune
```
