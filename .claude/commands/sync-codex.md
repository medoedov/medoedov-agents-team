---
description: Generate the Codex runtime from CLAUDE.md and .claude sources.
allowed-tools:
  - Read
  - Bash
---

# /sync-codex

Generate `AGENTS.md`, `.agents/skills/**`, and `.codex/agents/*.toml` from the
Claude-side source of truth.

## Source-of-truth rule

- Edit only `CLAUDE.md` and `.claude/**`.
- Never edit generated `AGENTS.md`, `.agents/**`, or managed `.codex/**` files directly.
- Commit source and generated changes together.

## Workflow

1. Preview:

   ```bash
   python .claude/shared/scripts/sync_to_codex.py --project .
   ```

2. Apply and remove stale manifest-owned outputs:

   ```bash
   python .claude/shared/scripts/sync_to_codex.py --project . --apply --prune
   ```

3. Verify zero drift:

   ```bash
   python .claude/shared/scripts/sync_to_codex.py --project . --check
   ```

If the generator reports a conflict, stop. Inspect the generated target and
move any intentional change back into its `CLAUDE.md` or `.claude/**` source.
Use `--force` only after that review; it deliberately replaces unmanaged or
independently edited generated files.

