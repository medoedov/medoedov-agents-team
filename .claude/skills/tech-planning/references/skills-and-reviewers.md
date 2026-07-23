# Skills and Reviewers Catalog

Single source of truth for selecting skills and reviewers in Implementation Tasks.
Used by: tech-planning (Phase 4), task-decomposition (Phase 1).

## Execution Skills

| Skill | What it's for | Typical tasks |
|-------|--------------|---------------|
| `code-writing` | Writing/modifying code, TDD cycle | API endpoints, models, services, components, migrations, tests |
| `infrastructure-setup` | Framework scaffolding and development-environment configuration | Dockerfile, pre-commit hooks, folder structure, .gitignore, test-runner setup |
| `deploy-pipeline` | CI/CD pipelines, deployment config, automated deploy | GitHub Actions, deploy scripts, platform config, secrets management |
| `documentation-writing` | Documentation, Project Knowledge updates | Architecture docs, API docs, conventions, patterns |
| `skill-master` | Creating/updating skills and agents | New skills, skill modifications |
| `pre-deploy-qa` | Acceptance testing before deploy (tests + acceptance criteria) | QA task in Final Wave |
| `post-deploy-qa` | Live environment verification after deploy via MCP tools | Post-deploy task in Final Wave |
| `prompt-master` | Writing/improving LLM prompts, prompt engineering | System prompts, user prompt templates, few-shot examples, prompt optimization |

| `code-reviewing` | Full-feature code quality audit | Selected by the Risk-Based Feature Audit Policy below |
| `security-auditor` | Full-feature security audit | Selected by the Risk-Based Feature Audit Policy below |
| `test-master` | Full-feature test quality audit | Selected by the Risk-Based Feature Audit Policy below |
| `bug-hunter` (agent) | Adversarial audit: API cross-reference, data flow failures, error UX | Selected by the Risk-Based Feature Audit Policy below; spawn as agent with `skills: []` |

Tasks without skill (user instructions) — skill not specified, description is in the task itself. Example: "ask user to register a bot in BotFather".

Prompt tasks (LLM system prompts, user templates) use `prompt-master` skill — they are NOT code-writing tasks. TDD Anchor is replaced by manual verification on sample data.

Substantial Python, service behavior, or automated-test implementation uses `code-writing`.
Keep infrastructure scaffolding in a separate atomic task when the feature also changes
application behavior; `infrastructure-setup` alone is not a substitute for `code-writing`.

## Reviewer Agents

| Agent | What it checks | Model |
|-------|---------------|-------|
| `code-reviewer` | Code quality: structure, patterns, naming, complexity, error handling | sonnet |
| `code-simplifier` | Behavior-preserving simplification, readability, alignment with project patterns | sonnet |
| `security-auditor` | OWASP Top 10, injection, XSS, auth, input validation, secrets | inherit |
| `test-reviewer` | Test quality: coverage, meaningful assertions, test pyramid balance | inherit |
| `skill-checker` | Skill compliance: frontmatter, structure, skill-master guidelines | inherit |
| `prompt-reviewer` | Prompt quality: clarity, positive framing, examples over rules, compression, XML structure, success criteria | inherit |
| `deploy-infra-reviewer` | CI/CD pipeline, deploy config, Docker, pre-commit, .gitignore, infrastructure setup quality | inherit |
| `documentation-reviewer` | Project-knowledge documentation quality: code blocks, generic content, missing operational details, duplication, bloat | inherit |

## Skill → Reviewers Mapping

| Skill | Default reviewers |
|-------|------------------|
| `code-writing` | `code-reviewer` |
| `infrastructure-setup` | `code-reviewer`, `security-auditor`, `deploy-infra-reviewer` |
| `deploy-pipeline` | `code-reviewer`, `security-auditor`, `deploy-infra-reviewer` |
| `documentation-writing` | `code-reviewer` |
| `skill-master` | `skill-checker` |
| `pre-deploy-qa` | none — QA is its own verification |
| `post-deploy-qa` | none — verification result is the review |
| `prompt-master` | `prompt-reviewer` |
| `code-reviewing` | none — auditor IS the review (Audit Wave) |
| `security-auditor` | none — auditor IS the review (Audit Wave) |
| `test-master` | none — auditor IS the review (Audit Wave) |
| `bug-hunter` (agent) | N/A — bug-hunter is an agent, not a skill. Spawn via feature-execution with `skills: []` |

Default rows are planning inputs, not execution-time fallback. Task decomposition must
materialize every selected reviewer in task frontmatter. Empty reviewers on a
`code-writing` task fail closed. Code-reviewer is required for every code change.
Code-simplifier is conditional: add it only for a broad refactor or
after a code-reviewer finding about complexity/readability. Other
trigger-based reviewers remain additive.

A generic default fallback is valid only when the selected skill explicitly allows omission
and names its default reviewers in that skill's contract. Otherwise empty reviewers fail
closed. An explicit `reviewers: []` remains valid for a cataloged task whose worker is the
review (Feature Audit) or whose skill contract explicitly defines no review (Final QA or
post-deploy verification).

## Risk-Based Feature Audit Policy

The Feature Audit Wave is conditional and risk-based:

- A simple size S feature may skip it after all task reviews pass and no audit trigger matches.
- Size M/L or cross-cutting features get a holistic code audit (`code-reviewing`).
- Security Audit runs only for auth, payments, secrets, or user data.
- Test Audit runs only for cross-task business-logic or test risk.
- Bug Hunt runs only for external APIs, queues, or data writers.

This is one feature-level audit pass, not a duplicate always-on review wave. If several
audits trigger, feature-execution schedules bounded batches. This project has a configured
cap of five and computes `confirmed free children = min(configured cap - current active
agents (including root), live runtime reported free child slots, explicitly named
workload-specific cap)`. Batches must fit confirmed free child slots and live runtime
availability. Final QA remains mandatory regardless of whether feature audits run.

## Examples

### Code task (most common)
```yaml
skills: [code-writing]
reviewers: [code-reviewer]
```

### Broad refactor
```yaml
skills: [code-writing]
reviewers: [code-reviewer, code-simplifier]
```

### Infrastructure setup task
```yaml
skills: [infrastructure-setup]
reviewers: [code-reviewer, security-auditor, deploy-infra-reviewer]
```

### Deploy pipeline task
```yaml
skills: [deploy-pipeline]
reviewers: [code-reviewer, security-auditor, deploy-infra-reviewer]
```

### Task handling user input or auth
```yaml
skills: [code-writing]
reviewers: [code-reviewer, security-auditor]
```
Security review is triggered because auth is in scope; code-simplifier is not
added unless complexity/readability or broad-refactor conditions also match.

### Documentation task
```yaml
skills: [documentation-writing]
reviewers: [code-reviewer]
```

### Triggered audit task (conditional Feature Audit Wave)
```yaml
skills: [code-reviewing]  # or security-auditor, test-master
reviewers: []
```

### QA task (Final Wave)
```yaml
skills: [pre-deploy-qa]
reviewers: []
```

### Post-deploy verification (Final Wave)
```yaml
skills: [post-deploy-qa]
reviewers: []
```

### Prompt task
```yaml
skills: [prompt-master]
reviewers: [prompt-reviewer]
```
