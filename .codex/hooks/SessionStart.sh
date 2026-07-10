#!/bin/bash
# SessionStart.sh — M4 backstop for rate-limit stall auto-resume.
# Triggered on every Claude Code session start (not just after compaction).
# If runtime automation was unavailable or the Claude process crashed mid-run,
# this hook detects a pending stall in any active feature's checkpoint.yml
# and emits a /do-all-tasks invocation to resume execution.
#
# Modelled structurally on post-compact-restore.sh: same jq guard, same
# 64 KB size cap, same case-pattern skip for work/completed/.
#
# NOTE (v1.0 limitation): resume_attempts is read (check present below) but
# the counter is never incremented in this iteration — atomic YAML write-back
# from bash is non-trivial and deferred to v1.1. The "escalate after 3
# attempts" guard always passes in v1.0 (counter stays at 0). Tracked in T11.
#
# Resume mode: the plain /do-all-tasks {feature} invocation is sufficient.
# The feature-execution skill Phase 1 reads checkpoint.yml (last_completed_wave,
# stall_state) on every invocation and detects resume autonomously — no
# explicit --resume flag is required.

# Guard: jq required (matches post-compact-restore.sh dependency)
command -v jq &>/dev/null || exit 0

INPUT=$(cat)
CWD=$(echo "$INPUT" | jq -r '.cwd // empty')

# Fall back to current working directory if hook input did not provide one.
[ -z "$CWD" ] && CWD="$PWD"
[ -d "$CWD/work" ] || exit 0

# Find the first active feature checkpoint with stall_state.active == true
# (skip work/completed/).
#
# Multi-feature ambiguity note: if more than one feature directory has a
# checkpoint.yml, the previous code picked the first one alphabetically
# regardless of whether its stall_state was active. This caused a confirmed
# bug (BH-005): an alphabetically-earlier feature with stall_state.active=false
# would shadow a later feature whose stall was genuinely pending resume.
# Fix: iterate ALL feature directories, extract stall_state.active from each
# candidate via awk (mirror the feature-name awk pattern already in this script),
# and only stop (break) when active==true is found. If no feature has an active
# stall, exit 0 silently. Multiple concurrent active stalls are not handled in
# v1.0; the first active one found (alphabetical) is selected and the others
# are left for the next session start.
CHECKPOINT=""
for dir in "$CWD"/work/*/logs/; do
  case "$dir" in
    "$CWD"/work/completed/*) continue ;;
  esac
  [ -f "$dir/checkpoint.yml" ] || continue
  # Extract stall_state.active from this candidate before committing to it.
  # Uses the same two-pass awk pattern as the STALL_ACTIVE extraction below.
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

# Sanity check: checkpoint must be non-empty and under 64 KB
CHECKPOINT_SIZE=$(wc -c < "$CHECKPOINT" 2>/dev/null || echo 0)
[ "$CHECKPOINT_SIZE" -eq 0 ] || [ "$CHECKPOINT_SIZE" -gt 65536 ] && exit 0

# Extract feature name (strip quotes and whitespace)
FEATURE=$(awk '/^feature:/{sub(/^feature:[[:space:]]*/,""); gsub(/["'"'"']/,""); print; exit}' "$CHECKPOINT")
[ -z "$FEATURE" ] && exit 0

# CWE-78 / CWE-22 guard: validate feature name before any shell expansion.
# Whitelist: lowercase alphanumeric + hyphens, 2-64 chars, must start alnum.
[[ "$FEATURE" =~ ^[a-z0-9][a-z0-9-]{1,63}$ ]] || exit 0

# Extract nested stall_state fields with awk (jq cannot parse YAML).
# Two-pass: enter stall_state block, capture the desired sub-field, exit.
STALL_ACTIVE=$(awk '
  /^stall_state:/{found=1; next}
  found && /^[^[:space:]]/{exit}
  found && /^[[:space:]]+active:/{sub(/^[[:space:]]+active:[[:space:]]*/,""); gsub(/["'"'"']/,""); print; exit}
' "$CHECKPOINT")

# Missing stall_state block or active != true → no resume
[ "$STALL_ACTIVE" = "true" ] || exit 0

# Infinite-retry guard: read resume_attempts; if ≥ 3 escalate to user instead
# of auto-resuming. v1.0 stub — counter is never incremented, so this always
# passes (see header). Wired now so v1.1 only needs to add the increment.
RESUME_ATTEMPTS=$(awk '
  /^stall_state:/{found=1; next}
  found && /^[^[:space:]]/{exit}
  found && /^[[:space:]]+resume_attempts:/{sub(/^[[:space:]]+resume_attempts:[[:space:]]*/,""); gsub(/["'"'"']/,""); print; exit}
' "$CHECKPOINT")

# Default missing/non-numeric to 0 (treat as "never attempted")
[[ "$RESUME_ATTEMPTS" =~ ^[0-9]+$ ]] || RESUME_ATTEMPTS=0

if [ "$RESUME_ATTEMPTS" -ge 3 ]; then
  echo "# SessionStart: resume_attempts >= 3 for $FEATURE — skipping auto-resume, manual intervention required"
  exit 0
fi

RESET_AT=$(awk '
  /^stall_state:/{found=1; next}
  found && /^[^[:space:]]/{exit}
  found && /^[[:space:]]+reset_at:/{sub(/^[[:space:]]+reset_at:[[:space:]]*/,""); gsub(/["'"'"']/,""); print; exit}
' "$CHECKPOINT")

# Treat null/empty reset_at as "not ready" → conservative no-op
[ -z "$RESET_AT" ] || [ "$RESET_AT" = "null" ] && exit 0

# ISO-8601 → epoch. GNU date (Linux/Debian) first, python3 fallback for macOS.
# Python fallback rewrites trailing 'Z' to '+00:00' so fromisoformat parses UTC
# correctly (rstrip would silently drop the offset → wrong local-time epoch).
RESET_EPOCH=$(date -d "$RESET_AT" +%s 2>/dev/null)
if [ -z "$RESET_EPOCH" ]; then
  RESET_EPOCH=$(python3 -c "from datetime import datetime; import sys; s=sys.argv[1]; s=s[:-1]+'+00:00' if s.endswith('Z') else s; print(int(datetime.fromisoformat(s).timestamp()))" "$RESET_AT" 2>/dev/null)
fi

# Parse failure → conservative no-op (matches tech-spec risk mitigation)
[ -z "$RESET_EPOCH" ] && exit 0

NOW_EPOCH=$(date +%s)

# Reset window not yet reached → silent no-op
[ "$RESET_EPOCH" -le "$NOW_EPOCH" ] || exit 0

# Stall active AND reset window passed → emit resume invocation
echo "Resume feature execution for $FEATURE. Load .agents/skills/source-command-do-all-tasks/SKILL.md and continue from checkpoint.yml."
exit 0
