---
description: Зеркалирует .claude/ из приватного проекта в публичный OS-репозиторий
command: python .claude/shared/scripts/sync_to_os.py
---

# /sync-os

Зеркалирует директорию `.claude/` из приватного проекта проекта в публичный репозиторий
`medoedov-claude-team` с защитой от утечки секретов и project-specific drift.

Read `.claude/shared/pipeline-contract.md` first and follow the `/sync-os` row. Its
preconditions, durable output/state, completion gate, and next transitions are normative.

## Когда запускать

- После редактирования агентных файлов (`.claude/agents/*.md`, `.claude/skills/`, `.claude/commands/`)
- Перед публикацией изменений в OS-репо (перед `git push` в `medoedov-claude-team`)
- Для проверки что sync не содержит секретов — используй `--dry-run` сначала

## Требования

- Файл `.sync-config.local.yml` в корне проекта (создаётся из шаблона,
  см. `.claude/shared/sync-templates/sync-config.example.yml`)
- Git CLI в PATH
- `pip install -r .claude/shared/scripts/sync-requirements.txt`

## Dual-runtime transaction

`.claude/**` is the source of truth. `sync_to_os.py` generates the public
Codex runtime from the already-sanitized target after substitutions and secret
checks, but before writing the manifest and creating the sync commit. A Codex
generation failure aborts the sync; partial output must never be committed.

For local Codex use in the private source project, run `/sync-codex` after
changing the agent system. `/sync-os` independently regenerates the sanitized
public runtime, so private Project Knowledge cannot leak through generated files.

## Safety workflow and authorization

Preserve the executable declaration `python .claude/shared/scripts/sync_to_os.py` and pass
the user's command arguments through unchanged; do not reinterpret, reorder, or silently
drop flags. Before the default mutating sync:

1. Run the staged forbidden-word/secret check and require success.
2. Run `/sync-os --dry-run`, require exit 0, review the proposed file set, and require zero
   secret findings before writing the target.
3. Generate the Codex runtime only inside the already-sanitized target, after substitutions
   and secret checks. A generation or validation failure aborts before manifest/commit.
4. Run the mutating sync only within the user's explicit authorization for that target.

The target sync commit, generated manifest, commit hash, and success/secret-check audit are
the durable state. **Completion gate:** dry-run and secret checks pass, sanitized-target
generation succeeds, the target commit is complete and clean, and the command reports its
durable commit hash/audit result.

Creating the authorized target commit is not publication. Never push, publish, open a PR,
or otherwise update a remote automatically; each such action requires separate explicit
user authorization. Diagnostic flags and the explicitly requested `--undo` retain their
documented argument semantics and do not imply publication permission.

## Флаги

| Флаг | Описание |
|------|----------|
| `--dry-run` | Показать что будет скопировано без реальных изменений. Выводит 3 progress-линии, exit 0, target не трогает. |
| `--undo` | Откатить последний sync commit в target. Работает только если HEAD — sync commit (prefixed `sync:` или author = sync bot configured in target). |
| `--self-check` | Запустить 3 прогона sync в temp dir и проверить byte-identical idempotency локально. Игнорирует `.sync-config.local.yml`. |
| `--quiet` | Подавить progress-линии `[1/3]`/`[2/3]`/`[3/3]`. Показывать только финальный SUCCESS/FAIL. Ошибки всегда печатаются (quiet не подавляет). |
| `--check-staged` | Проверить staged `.claude/` файлы на forbidden words (используется pre-commit hook и CI). Не выполняет sync. |
| `--help` | Показать эту справку. |

## Примеры

```bash
# Preview — что будет скопировано
/sync-os --dry-run

# Реальный sync (commit создаётся в target)
/sync-os

# Откатить последний sync commit
/sync-os --undo

# Проверить idempotency в изоляции
/sync-os --self-check

# Silent sync (только SUCCESS/FAIL)
/sync-os --quiet
```

## Формат success-сообщения

```
Done. Commit: abc1234. To undo: /sync-os --undo.
```

## Формат error-сообщений

**Dirty target (uncommitted changes в OS-репо):**
```
Target has uncommitted changes in /path/to/target
  Review:   git -C /path/to/target diff
  Discard:  git -C /path/to/target checkout .
  Preserve: git -C /path/to/target stash
Then re-run /sync-os.
```

**Missing config:**
```
No .sync-config.local.yml found.
Copy example: cp .claude/shared/sync-templates/sync-config.example.yml ./.sync-config.local.yml
Tip: используй --dry-run для preview изменений.
```

**Forbidden word hit:**
```
SECRET LEAK: file=X line=Y match='...' pattern='...'
PUSH REFUSED. Files NOT written. Add substitution rule or fix file. Then re-run /sync-os.
```
