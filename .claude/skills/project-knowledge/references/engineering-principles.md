# Engineering Principles

Universal engineering principles. Referenced by coder and reviewer agents.

## Code style

- Functions stay short. Extract or invert when a function grows past a screen.
- Limit nesting depth. Prefer early returns over deeply nested conditionals.
- Type or annotate public APIs (parameters and return types) when the language supports it.
- Catch the narrowest error you can handle. Avoid catch-all `except` / `catch (Exception)` unless you re-raise.
- Do not block the main path with synchronous I/O on hot loops or async/event-driven code paths.
- Names describe intent, not implementation. Delete dead code instead of commenting it out.

## Testing

- TDD for new logic: write the failing test first, then make it pass.
- Mock at I/O boundaries (network, disk, clock, external SDKs) — never mock the unit under test.
- Test pyramid: many fast unit tests, fewer integration tests, minimal end-to-end.
- Litmus test: would this test fail if the behavior breaks? If no, delete or rewrite it.
- Cover the contract, not the implementation. Renaming a private helper must not break tests.

## Architecture

- Read existing patterns before adding new ones. Match the conventions already in the file.
- Prefer reuse over extension over new code. Search before you write.
- Three-instances rule: extract an abstraction only after the third duplication, not the second.
- Validate at boundaries (HTTP entry, CLI input, queue payload). Trust internal callers.
- Treat external input as untrusted; sanitize and validate before it crosses trust boundaries. No string-concat into SQL, shell, or filesystem paths (use parameterized queries, argv lists, path APIs). No `eval`/`exec` on user input — that is injection waiting to happen.
- One module, one responsibility. Cross-module knowledge belongs in an explicit interface.

## Errors

- Fail loudly at boundaries; degrade gracefully inside. Silent fallbacks hide bugs.
- Do not catch what you cannot handle. Re-raise or let it bubble to a top-level handler.
- Log with context: operation, identifiers, error type. Never log secrets or PII.
- Distinguish expected errors (return or typed result) from bugs (raise). Do not conflate them.

## Security

- Never commit secrets, credentials, or tokens. Keep them in `.env` / secret stores; ensure the secret file pattern is ignored.
- Run a secret-scanning tool in pre-commit (e.g. gitleaks). Treat a hit as a blocker, not a warning.
- Pin and audit third-party dependencies. Review transitive dependencies before adding a new package.
- Apply least-privilege to credentials, tokens, and service accounts. Rotate on suspected exposure.
- Threat-model at boundaries: untrusted input, deserialization, file uploads, redirects, template rendering.
- Prefer cryptographic primitives from the standard library or a vetted library. Do not roll your own.
