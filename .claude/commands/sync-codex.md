---
description: Generate the Codex runtime from CLAUDE.md and .claude sources.
allowed-tools:
  - Read
  - Bash
---

# /sync-codex

Generate `AGENTS.md`, `.agents/skills/**`, and `.codex/agents/*.toml` from the
Claude-side source of truth.

Read `.claude/shared/pipeline-contract.md` first and follow the `/sync-codex` row. Its
preconditions, durable output/state, completion gate, and next transitions are normative.

## Source-of-truth rule

- Edit only `CLAUDE.md` and `.claude/**`.
- Never edit generated `AGENTS.md`, `.agents/**`, or managed `.codex/**` files directly.
- Commit source and generated changes together.

## Workflow

1. Preview:

   ```bash
   python .claude/shared/scripts/sync_to_codex.py --project .
   ```

2. Run targeted generator and generated-runtime tests before mutation:

   ```bash
   python -B -m pytest tests/test_sync_to_codex.py tests/sync_tooling/test_codex_generation.py -q
   ```

   Add focused tests for any changed command, skill, hook, or profile source. A preview is
   not permission to apply when a targeted test fails.

3. Validate explicit agent profiles in `.claude/codex/agent-profiles.toml`: every generated
   native agent MUST have a source entry and an explicit structurally supported `model` and
   `effort`; do not rely on an implicit default model for an omitted profile. Static policy
   and TOML validation are not proof that the current runtime accepts a selector.

4. Apply and remove stale manifest-owned outputs:

   ```bash
   python .claude/shared/scripts/sync_to_codex.py --project . --apply --prune
   ```

5. Verify zero drift:

   ```bash
   python .claude/shared/scripts/sync_to_codex.py --project . --check
   ```

6. Run the current Codex runtime's native lint or validation against the generated
   `AGENTS.md` and `.codex/agents/*.toml`, then smoke the agent profiles/selectors when the
   runtime exposes a callable path. Native acceptance is the final compatibility gate. If
   CLI native lint is inaccessible, record that limitation truthfully and use the current
   callable selector smoke as evidence. A successful spawn proves requested-selector
   acceptance only; do not claim an independent resolved model unless the runtime exposes
   that trace. If neither native lint nor a callable selector smoke is available, report the
   compatibility gate as unverified instead of inventing proof.

If the generator reports a conflict, stop. Inspect the generated target and
move any intentional change back into its `CLAUDE.md` or `.claude/**` source.
Use `--force` only after that review; it deliberately replaces unmanaged or
independently edited generated files.

## Result reporting

Report the two outcomes separately:

- `generation_status: complete|failed`. Generation completion is `complete`
  only when targeted tests pass, apply/prune succeeds, and `--check` confirms
  zero drift.
- `native_compatibility: verified|unverified|failed`. This reports only the
  available native lint and callable selector evidence.

Unverified or failed native compatibility does not downgrade completed generation.
Conversely, successful native compatibility cannot rescue failed
generation. Never overstate either result or infer resolved-model proof from
static configuration.

## Durable state and completion gate

The durable result is the regenerated manifest-owned runtime plus its generator manifest;
source and generated changes are committed together. **Completion gate:** targeted tests
pass, structural generator validation passes, every source agent has an explicit
profile/model, apply/prune succeeds without an unreviewed conflict, `--check` reports zero
drift, and the available native lint/profile smoke evidence is recorded without overstating
selector or resolved-model proof.
