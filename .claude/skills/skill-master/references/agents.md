# Skill + Agent Pattern

Parent-scheduled workers handle context-heavy subtasks for orchestrator skills. Each runs in
isolated context, performs one bounded assignment, and returns structured evidence or
explicitly scoped file changes.

## Why Isolated Workers

The orchestrator's context window is limited. Loading a skill, conversation history, and project context already consumes significant space. If the orchestrator opens many files, runs extensive analysis, or generates verbose output, context fills up and quality degrades.

**Solution:** Delegate heavy work to isolated workers. Each performs one task and returns a
structured result, so the parent receives only the evidence it needs.

## Orchestration Rules

Only the root parent schedules workers. Workers cannot schedule other workers; this keeps
orchestration one level deep across supported runtimes:

```
Orchestrator (main skill)
    ├── code-reviewer (subagent) ✓
    ├── security-auditor (subagent) ✓
    └── test-reviewer (subagent) ✓

code-reviewer
    └── another-agent ✗ FORBIDDEN
```

If a worker needs more work, it returns evidence to the parent, which decides whether to
schedule another bounded turn.

The parent schedules every worker through the current runtime after checking available
capacity. Each worker receives named role instructions, minimal context, and a disjoint
output contract. Do not request or claim a model override unless the runtime returns
enforceable binding evidence. Runtime adapters may map this contract to Claude agents,
Codex subagents, or another supported primitive without changing ownership or counts.

## When to Use Isolated Workers

| Task Type | Why a Worker Helps | Example |
|-----------|-------------------|---------|
| Reviews | Fresh context for objective assessment | code-reviewer, security-auditor |
| Research | Extensive file reading stays isolated | Exploring codebase, reading docs |
| Debugging | Isolated diagnosis without polluting main context | Error analysis, root cause |
| Validation | Schema/format checking with clean slate | skill-checker, schema-validator |
| Parallel work | Multiple independent directions | Research 3 modules simultaneously |
| High-volume output | Tests, logs don't bloat main context | Running test suite, log analysis |

## Ad-hoc Workers

For a simple one-off task, the parent may schedule a bounded current-runtime worker without
creating a reusable agent file. The prompt still names the role, objective, read/write scope,
output contract, and verification evidence. Use descriptive roles such as exploration,
diagnosis, or planning; a scheduling label alone is never proof of role or model binding.

**When to use:**
- Simple research/exploration
- One-off file operations
- Tasks under 50 lines of instructions
- No reuse needed

## Dedicated Agents (Skill + Agent Pattern)

For complex, reusable tasks — create **Skill + Agent pair**:

1. **Skill** — holds methodology (WHAT to do, HOW to analyze)
   - Usable inline via `/skill-name`
   - Contains knowledge

2. **Agent** — adds isolation + output contract
   - Uses `skills:` to preload methodology
   - Defines output: JSON, file changes, or actions
   - Runs in isolated context

**Example:**

```yaml
# skills/code-reviewing/SKILL.md — methodology
---
name: code-reviewing
description: Code review methodology and quality standards.
---
## What to Check
- Architecture, error handling, edge cases...

## Severity Levels
- Critical, Major, Minor...
```

```yaml
# agents/code-reviewer.md — isolation + format
---
name: code-reviewer
description: Review code quality after implementation.
color: blue
skills:
  - code-reviewing    # Full SKILL.md content loaded
allowed-tools: Read, Glob, Grep
---
Follow code-reviewing methodology.

## Output
{ "findings": [...], "summary": {...} }
```

**Benefits:**
- Methodology usable inline (`/code-reviewing`) OR in isolation (via agent)
- Multiple agents can run in parallel
- No methodology duplication — skill is single source of truth
- Agent adds structure (output contract) without bloating skill

## Agent File Format

Agent files use YAML frontmatter + Markdown body. Store in `.claude/agents/{name}.md`.

```yaml
---
name: agent-name
description: |
  When Claude should delegate to this agent. Include:
  - Purpose and capabilities
  - Example triggers
  - What NOT to use it for
color: blue
skills:
  - methodology-skill
allowed-tools: Read, Glob, Grep
---

# Agent Instructions

## Input
[What the agent receives from the orchestrator]

## Process
[Step-by-step methodology — or reference preloaded skill]

## Output
[Output contract: JSON schema, file changes, or actions]
```

### Required Fields

| Field | Description |
|-------|-------------|
| `name` | Unique identifier (kebab-case) |
| `description` | When/why to use — Claude reads this to decide delegation |
| `color` | Badge color for visual identification (see below) |
| `skills` | Skill(s) to preload — agent must have methodology from skill |

### Color Recommendations

All agents must have a color for visual identification. Valid values: `red`, `blue`, `green`, `yellow`, `purple`, `orange`, `pink`, `cyan`.

| Color | Agent Type |
|-------|------------|
| blue/cyan | Analysis, review (code-reviewer, test-reviewer) |
| red | Security, critical (security-auditor) |
| yellow | Validation, caution (skill-checker, schema-validator) |
| green | Success-oriented, exploration (Explore) |
| purple/pink | Creative, generation, research |
| orange | Infrastructure, deployment |

### Optional Fields

| Field | Default | Description |
|-------|---------|-------------|
| `model` | `inherit` | Desired runtime policy only; never claim it was enforced without binding evidence |
| `allowed-tools` | All tools | Restrict to necessary tools (e.g., `Read, Glob, Grep`) |
| `permissionMode` | `default` | Permission handling: `default`, `acceptEdits`, `bypassPermissions`, `plan` |
| `hooks` | None | Lifecycle hooks for validation |

## Output Contracts

Agents always return JSON report — even if they modify files or execute commands. Work is the process, output is the report.

**Analysis agents** — findings and recommendations:
```json
{
  "status": "approved" | "changes_required",
  "findings": [...],
  "summary": "..."
}
```

**Executor agents** — report of changes made:
```json
{
  "status": "success" | "partial" | "failed",
  "files_modified": ["path/to/file.ts", ...],
  "files_created": ["path/to/new.ts", ...],
  "summary": "Created 2 files, modified 3 files"
}
```

**Automation agents** — report of actions taken:
```json
{
  "status": "success" | "failed",
  "actions": ["ran tests", "deployed to staging"],
  "results": {...},
  "errors": []
}
```

## Continuing Workers

If the current runtime returns a reusable worker identity, the parent may schedule a bounded
follow-up turn on that worker. Treat the identity as routing metadata, not durable state or
role/model evidence.

**When to resume:**
- Need clarification on agent's findings
- Iterative refinement (agent found X, now do Y based on X)

**When NOT to resume (start fresh):**
- Different task, unrelated to previous
- Context would confuse agent
- Previous work is complete, new work begins

## Writing Effective Descriptions

The `description` field is critical — Claude uses it to decide when to delegate. Include:

1. **Purpose** — what the agent does
2. **Triggers** — when to use (with examples)
3. **Exclusions** — what NOT to use it for

Example from `code-reviewer`:
```yaml
description: |
  Use this agent when code has been written or modified and needs quality assessment.

  **Examples of when to use:**
  - After implementing a feature
  - After refactoring code
  - Before committing changes

  **Proactive usage**: Invoke automatically after any code implementation task.
```

## Invoking from Skills

Reference named specialist roles in the skill workflow; the parent schedules them in bounded
batches through the current runtime:

```markdown
## Post-work

1. **Run Reviews** (parent schedules a bounded batch)
   - `code-reviewer` — quality, architecture, patterns
   - `security-auditor` — OWASP Top 10, vulnerabilities

2. **Process Findings**
   Evaluate each finding on merit — severity is metadata, not a filter.
   - Valid, improves result → apply (any severity)
   - Disagree or uncertain → discuss with user
   Log each finding with action taken.
```

For agents needing specific input:

```markdown
Use `code-reviewer` subagent with:
- files: {list of modified files}
- userspec: {user requirements document}
- techspec: {technical specifications}
```

## Best Practices

1. **Define clear output contract** — JSON for analysis, file changes for executors
2. **Restrict tools** — Most agents only need `Read, Glob, Grep`
3. **Prefer `model: inherit` in Claude-compatible source** — Avoid an unnecessary override;
   do not claim any model binding without enforceable runtime evidence
4. **Always preload skill** — Agent must have methodology, not just output format
5. **Include examples in description** — Helps Claude know when to invoke
6. **One level of orchestration** — Subagents cannot call other subagents

## Example Agents

See existing agents for full examples:
- `.claude/agents/code-reviewer.md` — Detailed methodology with review dimensions
- `.claude/agents/security-auditor.md` — OWASP-based security analysis
- `.claude/agents/skill-checker.md` — Skill validation against standards

## References

- [Create custom subagents - Claude Code Docs](https://code.claude.com/docs/en/sub-agents)
- [Multi-agent research system - Anthropic](https://www.anthropic.com/engineering/multi-agent-research-system)
