# Codex privileged-role protocol — binding receipts, authorization handshake, immutable task runs. Read this before any privileged/high-risk receipt-producing spawn.

## Privileged-effect boundary

The full two-turn binding, filesystem receipt, and authorization handshake in
this document apply only to an action with a live or production effect.
Examples of a live-effect action: SSH access, deploy, destructive operations
on live or shared systems, data migration, secret access, production data or
credential access, and external or public-facing publication. A role whose
result authorizes a high-risk lifecycle gate is treated the same way.

Reading or copying production credentials or production data (dumps,
exports, secrets) counts as a live-effect action even when the file sits on
the local machine — the non-production qualifier is required for the
exemption.

Local, read-only, non-production evidence gathering does not need this
protocol. Examples of a local read-only action: checking whether a required
engine, image, or tool is present on the machine, or reading local
repository state. That work uses the standard bounded task envelope from
Ordinary single-turn execution in the base contract.

Local, state-changing, non-production actions (start a local daemon, build
or run local containers, create a venv) are not privileged; they follow
Ordinary single-turn execution, and any OS elevation they need uses the
native permission request, not this handshake.

This boundary only narrows scope. It never weakens the handshake or receipt
requirement for a live-effect action. When the classification is uncertain,
treat the action as live-effect.

### Binding receipt and authorization handshake

The parent classifies the effect before spawn. A two-turn authorization
handshake is required only for a live-effect role, as defined by the
Privileged-effect boundary above, when that role supports follow-up.
Ordinary low-risk coder and reviewer work follows
`Ordinary single-turn execution` and creates no binding receipt. A strict
single-turn read-only role used for a high-risk lifecycle gate records a
binding receipt from the native spawn but has no followup or child hash.

For a role that requires the authorization handshake:

1. Before spawn, the parent validates the exact profile/source mapping and source
   readability. The parent alone computes the SHA-256 of the canonical source
   path and fingerprints the normalized bounded task envelope. A child never
   authors either digest.
2. The first child turn is instruction-read/confirm only. It returns the
   canonical source path plus the exact source heading/version marker as a
   non-authoritative acknowledgement. It does not calculate or report a source
   hash, and any write during this turn fails the gate.
3. The parent independently verifies the acknowledgement and writes the unique
   parent-owned binding receipt. Only then may it invoke `followup_task` with the
   receipt ID and receipt path to authorize the bounded work turn.
4. The worker copies both receipt_id and receipt_path into its non-terminal
   result. Selector and role binding are authoritative only in the parent-owned
   receipt: the receipt proves invocation and binding, the child result proves
   work, and neither substitutes for the other.

For privileged/high-risk receipt-producing work, the explicit selection rule is:

- Feature/task execution uses the task-scoped form
  `work/{feature}/logs/working/task-{task-id}/spawn-{attempt-id}.receipt.yml`.
  In this form task_id and attempt are mandatory.
- Advisor, bootstrap, deploy, and other operations without a feature/task use
  `work/runtime-receipts/{operation-id}/spawn-{attempt-id}.receipt.yml`.
  In this form operation_id is mandatory and filesystem-safe
  (`[a-z0-9][a-z0-9-]{0,62}`); feature and task fields are optional. This form
  also covers a no-feature strict single-turn read-only spawn.

Every parent-owned receipt records:

- `receipt_id` and `receipt_path`;
- `attempt` plus the task- or operation-form identifiers defined above;
- `semantic_role`, requested `selector`, and requested or accepted `agent_type`;
- `role_source_path` and parent-computed `source_sha256`;
- normalized task-envelope data and its `envelope_fingerprint`;
- `native_child_id` plus `native_result_metadata`, including native tool
  acceptance/failure and a resolved trace only if exposed;
- `handshake_mode` (`authorization` or `strict-read-only`) and
  `handshake_status`;
- `created_at`.

Hash semantics are exact:

- `source_sha256 = SHA-256(exact role-source file bytes)`. Do not decode,
  normalize newlines, or reserialize the role source before hashing.
- To compute `envelope_fingerprint`, recursively normalize CRLF and CR to LF in
  every string value of the envelope, then serialize it as UTF-8 canonical JSON
  with sorted keys, separators `,` and `:`, `ensure_ascii=false`, and no
  insignificant whitespace. The fingerprint is SHA-256 of those serialized
  bytes.

The envelope fingerprint is therefore deterministic across platforms while the
role-source digest remains byte-exact.

When a role requires authorization but the native runtime cannot address it for
a follow-up, fail closed before write, privilege, high-risk, or lifecycle-gate
work. A receipt is invocation/binding evidence, not work evidence. The child
never authors or mutates the parent-owned receipt.

Fail closed before accepting privileged or high-risk work when the canonical
role source is missing, mismatched, or unreadable; the child was not given the
exact role instruction and bounded envelope; the isolated spawn fails; or its
required code, review, security, deployment, QA, or terminal evidence is absent.
Lack of a runtime model selector by itself is not a role-binding failure.

Profile model preferences are structurally restricted to the documented/current
slugs `gpt-5.6-sol` and `gpt-5.6-terra`; effort is one of `low`,
`medium`, or `high`. Generator validation proves only source/TOML structure.
Native runtime acceptance or a live callable selector smoke is the final
compatibility gate for the current environment.

Runtime-managed/fixed roles use their exact native role shape and never pass the
advisory model from `agent-profiles.toml` as an operative spawn override.
Unsupported desired metadata alone does not trigger user escalation.

One generic role-bound fallback is allowed only after a native fixed-role spawn
returns an explicit unsupported-model error. Missing or unverified advisory
metadata never qualifies. The fallback must use the same canonical role source
and the same bounded envelope, repeat the authorization handshake when the role
classification requires it, and preserve the failed native invocation in the
unique spawn receipt. No other fixed-role spawn failure permits a
generic/default retry, and role-free fallback remains forbidden.

## Immutable task runs and current pointer

Terminal task evidence is an immutable terminal run record at
`work/{feature}/logs/working/task-{task-id}/runs/{run-id}.run.yml`. It requires
filesystem-safe `run_id`, matching `task_id`, `approval_status: approved`,
`final_status: done`, evidence references, and optional `supersedes:`. A
terminal record with `final_status: done` is immutable: never overwrite, rename,
or reuse it.

The existing
`work/{feature}/logs/working/task-{task-id}/{task-id}.run.yml` is the atomically
replaced canonical current-run pointer. It is not terminal source of truth. It
contains `current_run_id`, `current_run_path`, `projected_status`, and
`evidence_digest`, where the digest is SHA-256 of the exact immutable run-record
bytes.

Every dependency, resume, and projection gate resolves evidence identically:

1. Read the pointer and validate path containment under the same task's `runs/`
   directory; reject absolute paths, traversal, symlinks, or another task's path.
2. Read the immutable record, require its run_id matches `current_run_id`, its
   `task_id` matches the task directory, and its evidence digest matches the
   pointer.
3. Enumerate the contained run records, validate unique IDs and links, and
   follow the supersedes chain to the latest approved non-superseded run.
   Reject cycles, missing ancestors, multiple approved leaves, or a pointer that
   does not select that leaf.
4. Only that resolved immutable record may satisfy dependency completion,
   resume completion, or a task/feature projection.

For initial completion, write supporting and projection artifacts, then the new
immutable run record, verify it, and atomically replace the canonical
current-run pointer. The pointer is written last. For revision, allocate a new
`run_id`, write a distinct record with `supersedes: <prior-run-id>`, preserve the
prior terminal evidence, then atomically replace the pointer last.

On a pre-pointer interruption, the new run remains unselected: readers continue
to resolve the old valid pointer. Recovery may validate and select the new run
or leave it as an unselected candidate, but it never mutates either terminal
record. Incomplete downstream projections are repaired idempotently only from
the resolved current immutable run.
