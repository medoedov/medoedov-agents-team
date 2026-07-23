---
description: Подтягивает последнюю версию агентного фреймворка из публичного OS-репозитория в этот проект
command: python .claude/shared/scripts/sync_from_os.py
---

# /update-framework

Pulls the latest agent framework FROM the public `medoedov-agents-team` repo back INTO
this project — the reverse of `/sync-os`. Updates agents, commands, skills (except
Project Knowledge), shared tooling, and the sync tooling itself, while preserving every
piece of project-local content, then regenerates the Codex runtime locally.

Read `.claude/shared/pipeline-contract.md` first and follow the `/update-framework` row.
Its preconditions, durable output/state, completion gate, and next transitions are
normative.

## Когда запускать

- Периодически, чтобы подтянуть фиксы и улучшения агентной системы из публичного репозитория.
- После того как в `medoedov-agents-team` вышло исправление, которое актуально для этого проекта.
- Перед началом крупной фичи — чтобы работать на актуальной версии фреймворка.
- Всегда сначала `--dry-run`, чтобы посмотреть, что изменится, прежде чем применять.

## Требования

- Этот проект уже инициализирован (`.claude/` существует).
- Git CLI в PATH.
- Сетевой доступ к GitHub (не нужен при `--from <local clone>`).

## Preserve vs Update

The partition is structural (`sync_tool.inbound_filter`), not config-driven — it never
reads the outbound `.sync-config.local.yml` settings of this project.

| Bucket | Examples | Behavior |
| --- | --- | --- |
| **PRESERVE** | `.claude/agent-memory/**`, `.claude/skills/project-knowledge/**` (incl. `SKILL.md`), root `CLAUDE.md`, `.claude/settings*.json`, `.claude/agents/IMPROVEMENT_LOG.md`, `.sync-config.local.yml`, `.sync-baseline-whitelist.yml`, `work/**`, `logs/**`, `.env`/`.env.*`, and the generated Codex runtime (`AGENTS.md`, `.agents/**`, `.codex/**` at the project root) | Never touched, never overwritten, never deleted — the generated runtime is preserved here and regenerated separately (see Codex regen below), not pulled as if it were framework source. |
| **UPDATE** | `.claude/agents/*.md` (except `IMPROVEMENT_LOG.md`), `.claude/commands/**`, `.claude/skills/**` (except `project-knowledge`), `.claude/shared/**` (including the sync tooling itself), `.claude/team-lead.md`, `.claude/codex/**` (the source `agent-profiles.toml`, not the generated root `.codex/`), `.claude/hooks/**` | Overwritten with upstream content; removed if upstream drops the file. |
| **out of scope** | root `README.md`/`LICENSE`/`.gitignore`, `src/**`, other application code outside `.claude/` that is not itself a PRESERVE entry above | Never walked, never touched — outside `.claude/`, the only scope this command considers, and not one of the explicitly preserved root-level paths either. |

The sync tooling itself (`.claude/shared/scripts/sync_to_os.py`, `sync_from_os.py`,
`sync_tool/*.py`, `.claude/shared/sync-templates/*`) is always in the UPDATE set —
tooling fixes reach every consumer even if a private maintainer outbound
`skip_list` happens to exclude that tooling from a specific OS publish.

## Codex regen

After applying updates, `/update-framework` checks whether this project uses the Codex
runtime (`.codex/` directory or `AGENTS.md` file present). If neither is present, regen
is skipped and reported as such — nothing is generated for a Claude-only project. If
present, it runs `python .claude/shared/scripts/sync_to_codex.py --project . --apply
--prune` against the freshly-updated source. A regen failure does NOT roll back the
already-applied file updates; it reports `Codex runtime: regen не удался` and suggests
running `/sync-codex` manually.

Ordering matters for safety: every non-tooling framework file is written and mirrored-
deleted FIRST, regen runs against the generator still on disk from before this run, and
only THEN does the sync tooling subtree itself (`.claude/shared/scripts/**`, including
`sync_to_codex.py`) get written. A pulled generator update is never executed as part of
the same run that pulled it — it takes effect starting with the NEXT `/update-framework`
run, after this run report and any local commit have already given the operator a chance
to review it.

## Security and trust

This command pulls and executes framework tooling from a remote git repository. Only run
it against an upstream you trust. It writes agent instructions, commands, skills, and
executable sync tooling directly into this project, and — once Codex regen runs — that
content shapes hooks and generated runtime files that execute in later sessions. Review
`git diff` (or the dry-run report) before treating the change as applied, especially
after switching `--ref` to a branch or tag outside the normal release flow. The resolved
upstream commit SHA is always included in the report so the operator can see exactly what
was pulled.

## Флаги

| Флаг | Описание |
|------|----------|
| `--dry-run` | Показать added/updated/removed без изменений на диске (default). |
| `--apply` | Записать обновления, применить удаления, перегенерировать Codex runtime. |
| `--ref <ref>` | Git ref в upstream-репозитории (default: `main`). |
| `--from <path>` | Использовать уже существующий локальный клон вместо fetch из upstream. |
| `--commit` | Закоммитить применённые изменения локально (per-path `git add`, никогда `git add .`). Требует `--apply` — без него команда завершается ошибкой парсинга аргументов, а не тихим no-op. Никогда не пушит. |
| `--quiet` | Подавить progress/report вывод. Ошибки всегда печатаются. |
| `--target <path>` | Корень проекта-потребителя (default: текущая директория). |
| `--help` | Показать эту справку. |

## Safety workflow

Preserve the executable declaration `python .claude/shared/scripts/sync_from_os.py` and
pass the command arguments the user gave through unchanged; do not reinterpret, reorder,
or silently drop flags.

1. Always run `/update-framework --dry-run` first and review the reported file list.
2. Only run `--apply` within the explicit authorization the user gave for this target.
3. If `.claude` has uncommitted local changes, `--apply` refuses (fail-closed) with
   concrete `git diff`/`checkout`/`stash` commands scoped to `.claude`. Dirty
   project-local or app code (agent-memory, `work/`, `src/`) never blocks an apply.
4. `--commit` only ever creates a local commit. Never push, publish, open a PR, or
   otherwise update a remote automatically — that requires separate explicit user
   authorization, same as `/sync-os`.

The applied file updates, mirrored deletions, `.sync-framework-state.json`, and the
Codex regen result are the durable state. **Completion gate:** dry-run and the
dirty-target check pass, preserved paths are byte-identical before/after, applied
updates match upstream content, mirrored deletions are a subset of the UPDATE set, and
Codex regen succeeds or is cleanly reported as skipped/failed.

## Примеры

```bash
# Preview — что изменится
/update-framework --dry-run

# Реальное обновление (без коммита)
/update-framework --apply

# Обновление + локальный коммит
/update-framework --apply --commit

# Из конкретной ветки/тега upstream
/update-framework --dry-run --ref v2

# Из уже склонированной локальной копии (офлайн / тестирование)
/update-framework --apply --from /path/to/local/clone
```

## Формат report

```
SUCCESS: dry-run завершён.
  upstream: 3f8a1c2
  добавлено: 2
  обновлено: 5
  без изменений: 118
  удалено: 1
  + .claude/agents/new-specialist.md
  ~ .claude/team-lead.md
  - .claude/commands/retired-command.md
```

`upstream` is the resolved short SHA of the upstream clone HEAD — always shown, dry-run
and apply alike, so the operator sees exactly what was pulled. Shows `unknown` when it
cannot be determined (e.g. a `--from` directory that is not itself a git checkout).

## Формат error-сообщений

**Dirty update-set (uncommitted changes в `.claude/`):**
```
Ошибка: в .claude/ (framework update-set) есть незакоммиченные изменения.
  Review:   git -C /path/to/target diff -- .claude
  Discard:  git -C /path/to/target checkout -- .claude
  Preserve: git -C /path/to/target stash push -- .claude
Then re-run /update-framework.
```

**Bad clone/ref (missing `.claude/`):**
```
Ошибка: не удалось получить upstream: /path/to/clone не похож на framework-репозиторий:
отсутствует .claude/. Проверь --ref/--from.
```

**Codex regen failure (updates already applied, not rolled back):**
```
Codex runtime: regen не удался: <detail>
Запусти /sync-codex вручную.
```

**`--commit` without `--apply` (hard error, argument parsing fails before any run):**
```
usage: sync_from_os.py [-h] [--dry-run | --apply] [--ref REF]
                       [--from FROM_PATH] [--commit] [--quiet]
                       [--target TARGET]
sync_from_os.py: error: --commit requires --apply (a dry-run never commits).
```
