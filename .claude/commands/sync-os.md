---
description: Зеркалирует .claude/ из приватного проекта в публичный OS-репозиторий
command: python .claude/shared/scripts/sync_to_os.py
---

# /sync-os

Зеркалирует директорию `.claude/` из приватного проекта проекта в публичный репозиторий
`medoedov-claude-team` с защитой от утечки секретов и project-specific drift.

## Когда запускать

- После редактирования агентных файлов (`.claude/agents/*.md`, `.claude/skills/`, `.claude/commands/`)
- Перед публикацией изменений в OS-репо (перед `git push` в `medoedov-claude-team`)
- Для проверки что sync не содержит секретов — используй `--dry-run` сначала

## Требования

- Файл `.sync-config.local.yml` в корне проекта (создаётся из шаблона,
  см. `.claude/shared/sync-templates/sync-config.example.yml`)
- Git CLI в PATH
- `pip install -r .claude/shared/scripts/sync-requirements.txt`

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
