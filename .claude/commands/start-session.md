Start of Agent Team working session.

Use for complex multi-day projects.

Steps:
1. If work/backlog.md exists, read it — incomplete tasks from the previous session; otherwise skip
2. Read .claude/agent-memory/team-lead/MEMORY.md — improvement context (see "Historical IMPROVEMENT_LOG" section)
3. Read the latest report from work/session-reports/
4. Ask the user what to work on today
5. Begin coordination (follow instructions from team-lead.md):
   - Complex task → Task(subagent_type="architect") for decomposition
   - Simple task → Task(subagent_type="coder") directly
   - For features → /interview (creates user-spec.md)

Env: CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 (already in settings.json)
