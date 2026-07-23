#!/bin/bash
# Context-only recovery hook for SessionStart(compact). It reports a bounded,
# sanitized checkpoint summary; the parent workflow validates all durable
# evidence and exclusively decides whether execution may continue.

command -v jq &>/dev/null || exit 0

INPUT=$(cat)
CWD=$(echo "$INPUT" | jq -r '.cwd // empty')
[ -z "$CWD" ] && CWD="$PWD"
[ -d "$CWD/work" ] || exit 0

CHECKPOINT=""
for dir in "$CWD"/work/*/logs/; do
  case "$dir" in
    "$CWD"/work/completed/*) continue ;;
  esac
  [ -f "$dir/checkpoint.yml" ] || continue
  CHECKPOINT="$dir/checkpoint.yml"
  break
done

[ -z "$CHECKPOINT" ] && exit 0
CHECKPOINT_SIZE=$(wc -c < "$CHECKPOINT" 2>/dev/null || echo 0)
[ "$CHECKPOINT_SIZE" -eq 0 ] || [ "$CHECKPOINT_SIZE" -gt 65536 ] && exit 0

FEATURE=$(awk '/^feature:/{sub(/^feature:[[:space:]]*/,""); gsub(/["'"'"']/,""); print; exit}' "$CHECKPOINT")
[ -z "$FEATURE" ] && exit 0
[[ "$FEATURE" =~ ^[a-z0-9][a-z0-9-]{1,63}$ ]] || exit 0

PENDING_TASKS=$(awk '
  /^[[:space:]]+pending_tasks:/{found=1; next}
  found && /^[[:space:]]+-[[:space:]]+[A-Za-z0-9._-]+[[:space:]]*$/{
    sub(/^[[:space:]]+-[[:space:]]+/,"")
    sub(/[[:space:]]+$/,"")
    tasks=(tasks ? tasks "," : "") $0
    next
  }
  found{exit}
  END{print tasks}
' "$CHECKPOINT")
CHECKPOINT_REF=${CHECKPOINT#"$CWD"/}

echo "# SessionStart compact context: feature=$FEATURE checkpoint=$CHECKPOINT_REF pending_tasks=${PENDING_TASKS:-none}; parent must validate durable evidence and decide whether continuation is authorized"
exit 0
