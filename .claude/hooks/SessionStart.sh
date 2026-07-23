#!/bin/bash
# Context-only recovery hook. It never mutates checkpoint state, increments a
# retry counter, or emits an operative resume command. The parent start-session
# workflow validates durable evidence and exclusively owns resume.

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
  CANDIDATE_ACTIVE=$(awk '
    /^stall_state:/{found=1; next}
    found && /^[^[:space:]]/{exit}
    found && /^[[:space:]]+active:/{sub(/^[[:space:]]+active:[[:space:]]*/,""); gsub(/["'"'"']/,""); print; exit}
  ' "$dir/checkpoint.yml")
  if [ "$CANDIDATE_ACTIVE" = "true" ]; then
    CHECKPOINT="$dir/checkpoint.yml"
    break
  fi
done

[ -z "$CHECKPOINT" ] && exit 0
CHECKPOINT_SIZE=$(wc -c < "$CHECKPOINT" 2>/dev/null || echo 0)
[ "$CHECKPOINT_SIZE" -eq 0 ] || [ "$CHECKPOINT_SIZE" -gt 65536 ] && exit 0

FEATURE=$(awk '/^feature:/{sub(/^feature:[[:space:]]*/,""); gsub(/["'"'"']/,""); print; exit}' "$CHECKPOINT")
[ -z "$FEATURE" ] && exit 0
[[ "$FEATURE" =~ ^[a-z0-9][a-z0-9-]{1,63}$ ]] || exit 0

RESET_AT=$(awk '
  /^stall_state:/{found=1; next}
  found && /^[^[:space:]]/{exit}
  found && /^[[:space:]]+reset_at:/{sub(/^[[:space:]]+reset_at:[[:space:]]*/,""); gsub(/["'"'"']/,""); print; exit}
' "$CHECKPOINT")
[ -z "$RESET_AT" ] || [ "$RESET_AT" = "null" ] && exit 0

RESET_EPOCH=$(date -d "$RESET_AT" +%s 2>/dev/null)
if [ -z "$RESET_EPOCH" ]; then
  RESET_EPOCH=$(python3 -c "from datetime import datetime; import sys; s=sys.argv[1]; s=s[:-1]+'+00:00' if s.endswith('Z') else s; print(int(datetime.fromisoformat(s).timestamp()))" "$RESET_AT" 2>/dev/null)
fi
[ -z "$RESET_EPOCH" ] && exit 0

NOW_EPOCH=$(date +%s)
[ "$RESET_EPOCH" -le "$NOW_EPOCH" ] || exit 0

echo "# SessionStart context: resume_due feature=$FEATURE; parent must validate checkpoint and decide whether to resume"
exit 0
