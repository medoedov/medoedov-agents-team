# Codex Runtime Audit

## Scope

This audit records the project-side Codex orchestration contract and the
capabilities observed in the current ChatGPT session. `.claude/**` is the source
of truth; generated `AGENTS.md`, `.agents/**`, and `.codex/**` files are outputs.

The audit covers role binding, model selectors, capacity, lifecycle wording,
hooks, durable evidence, and generator validation. It does not certify bot or
application behavior.

## Current environment facts

- The current callable collaboration schema exposes five total slots, including
  the root parent.
- Generic/custom worker calls currently accept the `gpt-5.6-sol` and
  `gpt-5.6-terra` selectors with reasoning-effort overrides.
- A fixed `coder` role using `gpt-5.6` failed for this ChatGPT account. The
  generator's `SUPPORTED_MODELS` allowlist now excludes the bare slug to match
  this confirmed failure; only `gpt-5.6-sol` and `gpt-5.6-terra` are accepted.
- The current official Codex manual still documents `gpt-5.6`,
  `gpt-5.6-terra`, custom-agent `model` and `model_reasoning_effort`, and a
  default `max_threads` value of six. The manual's mention of the bare slug is
  stale relative to the observed live-smoke failure above; do not re-add it
  without a new confirmed-working observation.

These facts describe capability variance, not a contradiction that static TOML
can resolve. The current-session callable behavior wins for this environment.
The generator may accept known documented/current slugs structurally, while
native lint or a live callable selector smoke remains the final compatibility
gate.

## Role and model policy

Role binding and model selection are separate:

1. The parent validates the profile-to-source mapping.
2. The task envelope instructs the isolated child to read the exact canonical
   `.claude/agents/<role>.md`.
3. The envelope bounds objective, files, writes, evidence, tests, ownership, and
   deadline.
4. Generic/custom selectable workers may receive model and effort selectors only
   when the active schema supports them and context forking is none or bounded.
5. Runtime-managed/fixed semantic roles remain locked.

A successful spawn proves that the requested selector was accepted. It does not
provide an independent resolved-model trace. Record the requested selector,
acceptance or failure, and a resolved trace only when the runtime exposes one.

If a fixed role fails solely because its built-in/advisory model is unsupported,
the parent may retry once with a generic role-bound worker. The retry must use
the same canonical role source and identical bounded envelope. A role-free
fallback is forbidden.

## Capacity policy

The generator accepts a configured `max_threads` range of 1 through 6. This
project uses a configured cap of five. Every bounded workload computes
`confirmed free children = min(configured cap - current active agents (including
root), live runtime reported free child slots, explicitly named
workload-specific cap)`. Effective total capacity is still the smaller of the
configured cap and live runtime availability.

The parent checks live agent inventory before every allocation. The root,
workers, reviewers, observers, and interrupted threads that remain open all
consume capacity. Project depth remains one: only the root parent spawns.

## Agent memory

Claude Code may honor `memory: project` frontmatter through its native behavior.
Codex does not provide automatic shared or cross-session agent memory. When
prior lessons are relevant, the parent explicitly instructs the Codex child to
read `.claude/agent-memory/<role>/MEMORY.md` as read-only input. The child must
not infer hidden persistence or automatic loading in a later thread.

## Durable evidence

The parent owns plans, waves, checkpoints, aggregation, retries, conflict
resolution, and resume decisions. A runtime status of `running`, a chat message,
or a checkpoint timestamp is not progress. Progress requires inspectable
artifact or test evidence. Terminal task and feature state require the canonical
run/status artifacts defined by the pipeline contract.

Children do not fan out or mutate shared lifecycle state. Interrupted work may
retain capacity until the live runtime reports otherwise.

## Cross-platform hooks

The generated hook configuration invokes one portable Python helper under
`.codex/hooks/`. The helper only lists `work/*/logs/checkpoint.yml` files and
prints the parent validation reminder. It does not schedule, resume, or mutate
work.

The POSIX command uses `python3` with Git-root resolution. The Windows override
uses a PowerShell 5-compatible command with Git-root resolution and invokes
Python directly; it does not depend on Bash or PowerShell execution policy.
Generated commands contain no absolute checkout path.

## Verification commands

Run focused regression tests:

```bash
python -B -m pytest -n 0 --basetemp .pytest_tmp_codex_parity_worker tests/test_sync_to_codex.py tests/sync_tooling/test_codex_generation.py tests/agent_orchestration/test_codex_privileged_execution_contract.py -q
```

Preview source-to-runtime generation without writing generated targets:

```bash
python .claude/shared/scripts/sync_to_codex.py --project .
```

The parent, after review, performs source-of-truth regeneration and drift checks:

```bash
python .claude/shared/scripts/sync_to_codex.py --project . --apply --prune
python .claude/shared/scripts/sync_to_codex.py --project . --check
```

Then run native Codex lint/profile validation when callable. If CLI native lint
is inaccessible, record that fact and use the current callable selector smoke as
evidence. Do not claim a resolved model without an exposed trace, and do not
invent chat approval text as a substitute for native permission.
