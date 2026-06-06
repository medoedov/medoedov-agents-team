End of Agent Team working session.

Steps:
1. Check the status of active tasks — identify any incomplete ones
2. Launch the meta-reviewer:
   Task(subagent_type="meta-reviewer", prompt="Analyze the session...", model="opus")
3. Wait for the report
4. Append lessons to .claude/agent-memory/team-lead/MEMORY.md under a new session entry
5. Output a summary to the user:
   - Tasks completed: N of M
   - Key outcomes
   - What remains for the next session
   - Which improvements were applied

If there are incomplete tasks — save them to work/backlog.md.
