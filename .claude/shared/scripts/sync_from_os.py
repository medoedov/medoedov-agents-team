#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sync_from_os — consumer-side reverse sync: medoedov-agents-team -> this
project.

The reverse of `sync_to_os.py`. Where `sync_to_os.py` publishes `.claude/**`
FROM a private project TO the public medoedov-agents-team repo, this script
pulls the latest agent framework FROM that public repo back INTO this
project — updating agents/commands/skills/shared tooling/etc. while
preserving project-local content (agent-memory, project-knowledge,
CLAUDE.md, settings, `.sync-config.local.yml`, work/, logs/) — then
regenerates the Codex runtime locally.

The preserve/update partition is a pure predicate module,
`sync_tool.inbound_filter`; this script is a thin orchestrator around it
and around `sync_to_os.py`'s own building blocks (`run_subprocess`,
`SubprocessError`, the git-binary cache, `atomic_replace`, the
dirty-target-check pattern) — reused, not duplicated.

Dry-run by default (`--dry-run`); `--apply` writes. Never pushes; `--commit`
only creates a local commit, per-path `git add`, never `git add .`.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

import sync_to_os
from sync_to_os import SubprocessError, run_subprocess
from sync_tool import inbound_filter
from sync_tool.atomic_write import (
    LockHeldError,
    acquire_pid_lock,
    atomic_replace,
    lstat_refuse_symlink,
    release_pid_lock,
)
from sync_tool.manifest import Manifest, ManifestFile, reconcile

UPSTREAM_URL = "https://github.com/medoedov/medoedov-agents-team.git"

# Distinct from the outbound `.sync-state.json` (sync_tool.manifest) so the
# two directions never collide over the same manifest file in a project that
# happens to run both `/sync-os` and `/update-framework`.
_STATE_FILENAME = ".sync-framework-state.json"
_LOCK_FILENAME = ".sync-framework.lock"

# The sync tooling subtree, including the Codex generator itself
# (sync_to_codex.py). Deliberately applied LAST in an apply — see
# _apply_ordered's docstring (security review M2).
_TOOLING_PREFIX = ".claude/shared/scripts/"

FileContent = Union[str, bytes]


# ---------------------------------------------------------------------------
# Public exceptions
# ---------------------------------------------------------------------------


class ClonePreconditionError(RuntimeError):
    """Raised when a clone/`--from` path does not look like the framework
    repo (missing `.claude/`)."""


class UpdateSetCheckError(RuntimeError):
    """Raised by `_check_update_set_dirty` when git status for the `.claude`
    update-set scope cannot be determined — fail-closed."""


class PathContainmentError(RuntimeError):
    """Raised by `_ensure_within` when a rel path would escape `target`
    after resolution — a `..` path component, or resolving through a
    symlinked intermediate directory to somewhere outside `target`
    (security review m5)."""


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


@dataclass
class Report:
    """Outcome of diffing the upstream UPDATE set against the downstream
    tree. `removed` starts as the PLANNED deletion set (mirrors upstream
    drops) but is overwritten with the actual outcome of `_apply_deletions`
    once an apply runs (security review m9) -- a path that was already
    manually removed before `--apply` must not be reported as "just
    deleted". `upstream_sha` is the resolved clone HEAD (security review
    M2: "operator sees exactly what was pulled"), "unknown" when it cannot
    be determined (e.g. a non-git `--from` directory)."""

    added: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    upstream_sha: str = "unknown"


def _print_report(report: Report, *, dry_run: bool, quiet: bool) -> None:
    if quiet:
        return
    print("SUCCESS: dry-run завершён." if dry_run else "SUCCESS: framework обновлён.")
    print(f"  upstream: {report.upstream_sha}")
    print(f"  добавлено: {len(report.added)}")
    print(f"  обновлено: {len(report.updated)}")
    print(f"  без изменений: {len(report.unchanged)}")
    print(f"  удалено: {len(report.removed)}")
    for label, items in (("+", report.added), ("~", report.updated), ("-", report.removed)):
        for rel in items:
            print(f"  {label} {rel}")


# ---------------------------------------------------------------------------
# _parse_args
# ---------------------------------------------------------------------------


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="sync_from_os.py",
        description=(
            "Pull the latest agent framework from the public "
            "medoedov-agents-team repo and update this project, preserving "
            "project-local content (agent-memory, project-knowledge, "
            "CLAUDE.md, settings, .sync-config.local.yml, work/, logs/)."
        ),
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run", action="store_true",
        help="Preview added/updated/removed files; write nothing (default).",
    )
    mode.add_argument(
        "--apply", action="store_true",
        help="Write updates, apply mirrored deletions, and regenerate the Codex runtime.",
    )
    parser.add_argument("--ref", default="main", help="Upstream git ref to clone (default: main).")
    parser.add_argument(
        "--from", dest="from_path", default=None,
        help="Use an existing local clone instead of fetching from upstream.",
    )
    parser.add_argument(
        "--commit", action="store_true",
        help="Commit applied changes locally (per-path git add; never pushes). Requires --apply.",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress progress/report output.")
    parser.add_argument("--target", default=".", help="Downstream project root (default: current directory).")
    ns = parser.parse_args(argv)
    ns.dry_run = not ns.apply
    if ns.commit and not ns.apply:
        # security review m6: --commit without --apply used to silently
        # no-op (dry-run always returns before the commit step is ever
        # reached) -- fail loud instead of quietly dropping the flag.
        parser.error("--commit requires --apply (a dry-run never commits).")
    return ns


# ---------------------------------------------------------------------------
# Fetch: _resolve_upstream / _clone_upstream / _validate_clone_shape
# ---------------------------------------------------------------------------


def _validate_clone_shape(clone_root: Path) -> None:
    if not (clone_root / ".claude").is_dir():
        raise ClonePreconditionError(
            f"{clone_root} не похож на framework-репозиторий: отсутствует .claude/. "
            f"Проверь --ref/--from."
        )


def _clone_upstream(ref: str, dest: Path) -> None:
    if sync_to_os._GIT_BIN is None:
        raise RuntimeError("git не найден в PATH; невозможно клонировать upstream.")
    run_subprocess(
        [sync_to_os._GIT_BIN, "clone", "--depth", "1", "--branch", ref, UPSTREAM_URL, str(dest)],
        timeout=120,
    )


def _resolve_upstream(
    args: argparse.Namespace,
) -> tuple[Path, Optional[tempfile.TemporaryDirectory]]:
    """Return (clone_root, tmp_ctx). `tmp_ctx` is owned by the caller for
    cleanup (None when `--from` is used — that directory is not ours)."""
    if args.from_path:
        clone_root = Path(args.from_path).resolve()
        _validate_clone_shape(clone_root)
        return clone_root, None

    tmp_ctx = tempfile.TemporaryDirectory(prefix="sync-from-os-")
    clone_root = Path(tmp_ctx.name) / "clone"
    _clone_upstream(args.ref, clone_root)
    _validate_clone_shape(clone_root)
    return clone_root, tmp_ctx


def _read_clone_sha(clone_root: Path) -> str:
    """Best-effort short SHA of the upstream clone HEAD, surfaced in the
    report so the operator sees exactly what was pulled (security review
    M2). "unknown" when it cannot be determined -- e.g. a `--from`
    directory that is not itself a git checkout."""
    if sync_to_os._GIT_BIN is None:
        return "unknown"
    try:
        r = run_subprocess(
            [sync_to_os._GIT_BIN, "-C", str(clone_root), "rev-parse", "--short", "HEAD"],
            timeout=30,
        )
        return r.stdout.decode().strip()
    except SubprocessError:
        return "unknown"


# ---------------------------------------------------------------------------
# _collect_update_files
# ---------------------------------------------------------------------------


def _read_update_file(abs_path: Path) -> FileContent:
    """Read one framework file, normalizing text content.

    `lstat_refuse_symlink` is defense-in-depth (security review M1):
    `inbound_filter.walk_update_set` already skips symlink entries before
    ever yielding them, so this should never fire in normal operation --
    but this function's contract (read a real file's bytes) must hold even
    if it is ever reached some other way, since `read_bytes()` follows
    symlinks and would otherwise exfiltrate an arbitrary local file's
    content (e.g. `~/.ssh/id_rsa`) into a tracked framework file.

    Binary content — detected via a NUL byte, the same convention the
    outbound pipeline uses (see `tests/sync_tooling/_sync_helpers.py`
    `_process_file`) — passes through as raw bytes unchanged. Text content:
    strip a UTF-8 BOM, normalize CRLF -> LF, then decode.
    """
    lstat_refuse_symlink(abs_path)
    raw = abs_path.read_bytes()
    if b"\x00" in raw:
        return raw
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    raw = raw.replace(b"\r\n", b"\n")
    return raw.decode("utf-8", errors="replace")


def _collect_update_files(clone_root: Path) -> list[tuple[str, FileContent]]:
    """Walk the UPDATE set in `clone_root`; return sorted (rel_posix, content)."""
    results: list[tuple[str, FileContent]] = []
    for abs_path in inbound_filter.walk_update_set(clone_root):
        rel = abs_path.relative_to(clone_root).as_posix()
        results.append((rel, _read_update_file(abs_path)))
    results.sort(key=lambda item: item[0])
    return results


# ---------------------------------------------------------------------------
# Manifest / state — own tiny JSON reader/writer (distinct filename from the
# outbound `.sync-state.json`; reuses the pure `reconcile()` + dataclasses).
# ---------------------------------------------------------------------------


def _content_bytes(content: FileContent) -> bytes:
    return content.encode("utf-8") if isinstance(content, str) else content


def _build_manifest(file_results: list[tuple[str, FileContent]]) -> Manifest:
    files = [
        ManifestFile(path=rel, sha256=hashlib.sha256(_content_bytes(content)).hexdigest())
        for rel, content in file_results
    ]
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return Manifest(schema_version=1, last_sync_at=now, files=files)


def _read_state(target: Path) -> Optional[Manifest]:
    """Read `.sync-framework-state.json`. None on absent/corrupted (treated
    as a first run — idempotent recovery, mirrors manifest.py's contract)."""
    state_path = target / _STATE_FILENAME
    if not state_path.exists():
        return None
    try:
        raw = json.loads(state_path.read_text(encoding="utf-8"))
        files = [ManifestFile(path=f["path"], sha256=f.get("sha256", "")) for f in raw.get("files", [])]
        return Manifest(
            schema_version=int(raw.get("schema_version", 1)),
            last_sync_at=str(raw.get("last_sync_at", "")),
            files=files,
        )
    except (json.JSONDecodeError, OSError, KeyError, ValueError, TypeError):
        return None


def _write_state(target: Path, manifest: Manifest) -> None:
    data = {
        "schema_version": manifest.schema_version,
        "last_sync_at": manifest.last_sync_at,
        "files": [{"path": f.path, "sha256": f.sha256} for f in manifest.files],
    }
    state_path = target / _STATE_FILENAME
    fd, tmp_name = tempfile.mkstemp(dir=target, suffix=".framework-state.tmp")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        atomic_replace(tmp_path, state_path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# _diff_against_downstream
# ---------------------------------------------------------------------------


def _diff_against_downstream(
    file_results: list[tuple[str, FileContent]],
    target: Path,
    to_delete: list[str],
) -> Report:
    report = Report(removed=list(to_delete))
    for rel, content in file_results:
        dest = target / rel
        if not dest.exists():
            report.added.append(rel)
            continue
        try:
            existing = dest.read_bytes()
        except OSError:
            report.updated.append(rel)
            continue
        if existing == _content_bytes(content):
            report.unchanged.append(rel)
        else:
            report.updated.append(rel)
    return report


# ---------------------------------------------------------------------------
# _apply_updates / _apply_deletions
# ---------------------------------------------------------------------------


def _ensure_within(target: Path, rel: str) -> Path:
    """Return `target / rel`, refusing (`PathContainmentError`) if `rel`
    would escape `target` (security review m5).

    Two checks: (1) `rel` has no `..` path component; (2) after resolving
    symlinks, `target / rel` still sits under `resolve()`d `target` — this
    second check is what catches a symlinked INTERMEDIATE directory (e.g.
    `target/.claude` itself replaced with a symlink pointing elsewhere),
    which a bare `..`-component check cannot see. `rel` in normal
    operation always comes from a safe `Path.relative_to()` computation
    (never containing `..`) and `is_update()` already independently rejects
    anything outside `.claude/`, so this is defense-in-depth against a
    corrupted/tampered state entry or a future code path that does not
    route through those guards.
    """
    if ".." in Path(rel).parts:
        raise PathContainmentError(f"refusing path with '..' component: {rel!r}")
    candidate = target / rel
    resolved_target = target.resolve()
    resolved_candidate = candidate.resolve()
    if not resolved_candidate.is_relative_to(resolved_target):
        raise PathContainmentError(
            f"refusing path outside target after resolution: {rel!r} -> {resolved_candidate}"
        )
    return candidate


def _write_update_file(rel: str, content: FileContent, target: Path, tmp_root: Path) -> None:
    dest = _ensure_within(target, rel)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp_file = tmp_root / rel
    tmp_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_file.write_bytes(_content_bytes(content))
    atomic_replace(tmp_file, dest)


def _apply_updates(file_results: list[tuple[str, FileContent]], target: Path) -> None:
    """Write every UPDATE-set file to `target` via `.sync-tmp/` + atomic
    replace. Mirrors `sync_to_os._write_to_target`'s shape (per-file tmp
    path to dodge basename collisions, `atomic_replace`'s CWE-59 symlink
    guard, best-effort tmp cleanup) but writes raw bytes directly —
    `sync_to_os._write_single_file` is `write_text`/str-only because its
    own pipeline only ever hands it already-decoded source text; framework
    content here can include binary skill assets.
    """
    target.mkdir(parents=True, exist_ok=True)
    tmp_root = target / ".sync-tmp"
    tmp_root.mkdir(exist_ok=True)
    try:
        for rel, content in file_results:
            _write_update_file(rel, content, target, tmp_root)
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)


def _apply_deletions(to_delete: list[str], target: Path) -> list[str]:
    """Remove files that mirror an upstream deletion.

    Deletion safety (three independent guarantees — plan Risks "Deletion
    safety" + security review m5):
      1. `to_delete` is derived only by reconciling old vs new UPDATE-set
         state, so it is a subset of the UPDATE set by construction.
      2. Per-path check here: refuse (raise) unless
         `is_update(rel) and not is_preserved(rel)` — defense in depth
         against a future classification-rule drift making guarantee 1 no
         longer hold for an OLD manifest entry.
      3. `_ensure_within` refuses a `..` component or a path that resolves
         outside `target` (e.g. through a symlinked intermediate
         directory) — defense in depth against a tampered/corrupted state
         entry that somehow still passes guarantee 2 (see `_ensure_within`
         docstring for a concrete example).
    Never removes directories; only unlinks plain files/symlinks that
    actually exist.
    """
    removed: list[str] = []
    for rel in to_delete:
        if not (inbound_filter.is_update(rel) and not inbound_filter.is_preserved(rel)):
            raise RuntimeError(
                f"refusing to delete out-of-partition path: {rel!r} — to_delete "
                f"must be a subset of the UPDATE set."
            )
        path = _ensure_within(target, rel)
        if path.is_file() or path.is_symlink():
            path.unlink(missing_ok=True)
            removed.append(rel)
    return removed


# ---------------------------------------------------------------------------
# Dirty-target check, scoped to the `.claude` update-set — sync_to_os.py's
# _check_dirty_target pattern (raw subprocess.run so the "not a git repo"
# exit-128 case can be distinguished from a genuine error), narrowed to
# `.claude` and filtered to only UPDATE-set paths.
# ---------------------------------------------------------------------------


def _porcelain_paths(porcelain_output: str) -> list[str]:
    """Extract relative paths from `git status --porcelain` output,
    including the `old -> new` rename-arrow form (keeps the new path)."""
    paths: list[str] = []
    for line in porcelain_output.splitlines():
        if not line.strip():
            continue
        raw_path = line[3:] if len(line) > 3 else ""
        if " -> " in raw_path:
            raw_path = raw_path.split(" -> ", 1)[1]
        raw_path = raw_path.strip().strip('"')
        if raw_path:
            paths.append(raw_path)
    return paths


def _is_git_repo(target: Path) -> bool:
    if sync_to_os._GIT_BIN is None:
        return False
    try:
        result = subprocess.run(
            [sync_to_os._GIT_BIN, "-C", str(target), "rev-parse", "--is-inside-work-tree"],
            shell=False, capture_output=True, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and result.stdout.decode().strip() == "true"


def _check_update_set_dirty(target: Path) -> bool:
    """True if the `.claude` update-set scope of `target` has uncommitted
    changes. Fail-closed: raises UpdateSetCheckError on any inability to
    determine status. Dirty PRESERVED or out-of-scope paths (agent-memory
    edits, work/, app code) never block an update — only lines whose path
    is_update() count.
    """
    if sync_to_os._GIT_BIN is None:
        raise UpdateSetCheckError("git не найден в PATH; не могу проверить чистоту .claude/.")
    try:
        result = subprocess.run(
            [sync_to_os._GIT_BIN, "-C", str(target), "status", "--porcelain", "--", ".claude"],
            shell=False, capture_output=True, timeout=30,
        )
    except subprocess.TimeoutExpired as exc:
        raise UpdateSetCheckError(f"git status превысил таймаут для {target}: {exc}") from exc
    except OSError as exc:
        raise UpdateSetCheckError(f"Не удалось запустить git status для {target}: {exc}") from exc

    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")[:200]
        if result.returncode == 128 and "not a git repository" in stderr.lower():
            return False
        raise UpdateSetCheckError(
            f"git status вернул код {result.returncode} для {target}.\nstderr: {stderr}"
        )

    dirty_paths = _porcelain_paths(result.stdout.decode("utf-8", errors="replace"))
    return any(inbound_filter.is_update(p) for p in dirty_paths)


def _refuse_if_dirty(target: Path) -> bool:
    """Errors and the refusal message always print — matching /sync-os
    convention that dirty-target/precondition failures are never silenced
    by --quiet."""
    try:
        dirty = _check_update_set_dirty(target)
    except UpdateSetCheckError as exc:
        print(f"Ошибка проверки чистоты .claude/: {exc}", file=sys.stderr)
        return True
    if not dirty:
        return False
    print(
        "Ошибка: в .claude/ (framework update-set) есть незакоммиченные изменения.\n"
        f"  Review:   git -C {target} diff -- .claude\n"
        f"  Discard:  git -C {target} checkout -- .claude\n"
        f"  Preserve: git -C {target} stash push -- .claude\n"
        "Then re-run /update-framework.",
        file=sys.stderr,
    )
    return True


# ---------------------------------------------------------------------------
# Codex regen
# ---------------------------------------------------------------------------


def _downstream_uses_codex(target: Path) -> bool:
    return (target / ".codex").is_dir() or (target / "AGENTS.md").is_file()


def _register_python_binary() -> None:
    """Register the running interpreter in sync_to_os's binary cache so
    run_subprocess() (Decision 16(b) contract — see sync_to_os.py) accepts
    it for the Codex-regen subprocess call below.

    Called lazily, right before the one call site that needs it (security
    review m7) — merely IMPORTING this module should not have a permanent
    side effect on sync_to_os's shared process-wide `_BINARY_CACHE`; the
    mutation only happens if Codex regen is actually about to run.
    """
    python_basename = Path(sys.executable).name
    python_cache_key = python_basename.lower().removesuffix(".exe")
    sync_to_os._BINARY_CACHE[python_cache_key] = sys.executable


def _regenerate_codex_local(target: Path, quiet: bool) -> str:
    """Regenerate the Codex runtime in place. Returns "skipped"/"ok"/"failed".

    On failure: does NOT roll back already-applied file updates (plan Risks
    "Regen failure") — reports failure and suggests `/sync-codex`.
    """
    if not _downstream_uses_codex(target):
        if not quiet:
            print("Codex runtime: не используется (.codex/ и AGENTS.md отсутствуют) — regen пропущен.")
        return "skipped"

    script = target / ".claude" / "shared" / "scripts" / "sync_to_codex.py"
    if not script.is_file():
        # Failures always print, even under --quiet (/sync-os convention:
        # errors are never suppressed) -- a "failed" status below causes
        # a non-zero exit and the caller needs to see why.
        print(
            f"Codex runtime: {script} отсутствует после обновления framework. "
            "Запусти /sync-codex вручную.",
            file=sys.stderr,
        )
        return "failed"

    _register_python_binary()
    try:
        run_subprocess(
            [sys.executable, str(script), "--project", str(target), "--apply", "--prune"],
            timeout=120,
        )
    except SubprocessError as exc:
        print(
            f"Codex runtime: regen не удался: {exc}\n"
            f"Запусти /sync-codex вручную.",
            file=sys.stderr,
        )
        return "failed"
    if not quiet:
        print("Codex runtime: обновлён.")
    return "ok"


# ---------------------------------------------------------------------------
# _maybe_commit
# ---------------------------------------------------------------------------


def _maybe_commit(
    target: Path,
    ref: str,
    updated_paths: list[str],
    removed_paths: list[str],
    quiet: bool,
) -> Optional[str]:
    """Stage + commit applied changes. Per-path `git add --` (never
    `git add .`); deletions staged via `git add -u -- :(literal)<path>`
    (same convention as `sync_tool.manifest.git_stage_manifest`). Never
    pushes."""
    if sync_to_os._GIT_BIN is None:
        if not quiet:
            print("Commit пропущен: git не найден в PATH.", file=sys.stderr)
        return None
    git = sync_to_os._GIT_BIN

    for rel in sorted(set(updated_paths) | {_STATE_FILENAME}):
        try:
            run_subprocess([git, "-C", str(target), "add", "--", rel], timeout=30)
        except SubprocessError as exc:
            if not quiet:
                print(f"git add не удался для {rel}: {exc}", file=sys.stderr)
            return None

    for rel in sorted(set(removed_paths)):
        try:
            run_subprocess([git, "-C", str(target), "add", "-u", "--", f":(literal){rel}"], timeout=30)
        except SubprocessError as exc:
            if "did not match any files" not in str(exc):
                if not quiet:
                    print(f"git add -u не удался для {rel}: {exc}", file=sys.stderr)
                return None

    return _commit_and_get_sha(target, ref, quiet)


def _commit_and_get_sha(target: Path, ref: str, quiet: bool) -> Optional[str]:
    git = sync_to_os._GIT_BIN
    commit_msg = f"framework: update from upstream @{ref}"
    try:
        run_subprocess([git, "-C", str(target), "commit", "-m", commit_msg], timeout=30)
    except SubprocessError as exc:
        stderr_txt = str(exc)
        if "nothing to commit" in stderr_txt or "working tree clean" in stderr_txt:
            if not quiet:
                print("Commit пропущен: нет изменений.")
            return None
        if not quiet:
            print(f"git commit не удался: {exc}", file=sys.stderr)
        return None
    try:
        r = run_subprocess([git, "-C", str(target), "rev-parse", "--short", "HEAD"], timeout=30)
        return r.stdout.decode().strip()
    except SubprocessError:
        return "unknown"


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


@dataclass
class _PreparedUpdate:
    file_results: list[tuple[str, FileContent]]
    new_manifest: Manifest
    to_delete: list[str]
    report: Report


def _prepare_update(target: Path, clone_root: Path) -> _PreparedUpdate:
    file_results = _collect_update_files(clone_root)
    old_state = _read_state(target)
    new_manifest = _build_manifest(file_results)
    rec = reconcile(old_state, new_manifest, target)
    report = _diff_against_downstream(file_results, target, rec.to_delete)
    report.upstream_sha = _read_clone_sha(clone_root)
    return _PreparedUpdate(file_results, new_manifest, rec.to_delete, report)


def _is_tooling_path(rel: str) -> bool:
    """True iff `rel` sits under the tooling subtree, normalized THE SAME
    WAY `inbound_filter.is_update`/`classify` normalize before matching
    (security review, second pass): a raw case-sensitive `startswith()`
    here let a case-variant path (e.g.
    `.claude/Shared/scripts/sync_to_codex.py`) pass `is_update()` as
    UPDATE while being routed to the "rest" (written-before-regen) batch
    instead of "tooling" (written-after-regen) — on a case-insensitive
    filesystem that variant is the SAME on-disk file as the real
    generator, so the M2 RCE-ordering fix was bypassable. `_TOOLING_PREFIX`
    is already lowercase/forward-slash, so normalizing only the input side
    is sufficient.
    """
    return inbound_filter.normalize_path(rel).startswith(_TOOLING_PREFIX)


def _split_tooling_results(
    file_results: list[tuple[str, FileContent]],
) -> tuple[list[tuple[str, FileContent]], list[tuple[str, FileContent]]]:
    tooling = [item for item in file_results if _is_tooling_path(item[0])]
    rest = [item for item in file_results if not _is_tooling_path(item[0])]
    return tooling, rest


def _split_tooling(paths: list[str]) -> tuple[list[str], list[str]]:
    tooling = [p for p in paths if _is_tooling_path(p)]
    rest = [p for p in paths if not _is_tooling_path(p)]
    return tooling, rest


def _apply_ordered(prepared: _PreparedUpdate, target: Path, quiet: bool) -> tuple[list[str], str]:
    """Apply updates/deletions and run Codex regen in an RCE-safe order.

    Security review M2: a naive "write everything, then regen" ordering
    would overwrite `.claude/shared/scripts/sync_to_codex.py` (and the
    rest of the sync tooling) with upstream content and then EXECUTE that
    just-pulled file via subprocess in the same `--apply` — a compromised
    upstream repo would get arbitrary code execution on the very first
    pull. Fix: write and delete every non-tooling path first, run Codex
    regen against the STILL-OLD, already-trusted on-disk generator (it
    only needs the freshly-updated agent/skill/command sources under
    `.claude/`, not the generator's own code), and only then write/delete
    the tooling subtree (`.claude/shared/scripts/**`) itself — the new
    generator lands on disk for the NEXT run, but is never executed as
    part of THIS one.

    Returns (removed_paths, regen_status) — `removed_paths` merges both
    phases' actual `_apply_deletions` outcomes.
    """
    tooling_updates, rest_updates = _split_tooling_results(prepared.file_results)
    tooling_deletes, rest_deletes = _split_tooling(prepared.to_delete)

    _apply_updates(rest_updates, target)
    removed = _apply_deletions(rest_deletes, target)

    regen_status = _regenerate_codex_local(target, quiet)

    _apply_updates(tooling_updates, target)
    removed += _apply_deletions(tooling_deletes, target)

    return removed, regen_status


def _apply_and_report(args: argparse.Namespace, target: Path, prepared: _PreparedUpdate) -> int:
    is_git_target = _is_git_repo(target)
    if is_git_target:
        if _refuse_if_dirty(target):
            return 1
    elif not args.quiet:
        print("Внимание: target не git-репозиторий — dirty-check и --commit недоступны.")

    pid_lock = None
    try:
        pid_lock = acquire_pid_lock(target / _LOCK_FILENAME)
    except LockHeldError as exc:
        print(f"Ошибка: update-framework уже выполняется: {exc}", file=sys.stderr)
        return 1

    try:
        removed, regen_status = _apply_ordered(prepared, target, args.quiet)
        _write_state(target, prepared.new_manifest)
    finally:
        release_pid_lock(pid_lock)

    # security review m9: report the ACTUAL deletion outcome, not the
    # pre-apply plan — a path already removed by hand before --apply must
    # not be reported as "just deleted".
    prepared.report.removed = removed

    commit_sha = None
    if args.commit:
        if not is_git_target:
            print("Внимание: --commit недоступен для non-git target — пропущено.", file=sys.stderr)
        else:
            updated_paths = [rel for rel, _ in prepared.file_results]
            commit_sha = _maybe_commit(target, args.ref, updated_paths, removed, args.quiet)

    _print_report(prepared.report, dry_run=False, quiet=args.quiet)
    if not args.quiet and commit_sha:
        print(f"Done. Commit: {commit_sha}.")

    return 1 if regen_status == "failed" else 0


def _run_update(args: argparse.Namespace, target: Path, clone_root: Path) -> int:
    prepared = _prepare_update(target, clone_root)
    if args.dry_run:
        _print_report(prepared.report, dry_run=True, quiet=args.quiet)
        return 0
    return _apply_and_report(args, target, prepared)


def do_update_framework(args: argparse.Namespace) -> int:
    target = Path(args.target).resolve()
    if not target.is_dir():
        print(f"Ошибка: target не найден: {target}", file=sys.stderr)
        return 1

    try:
        clone_root, tmp_ctx = _resolve_upstream(args)
    except (ClonePreconditionError, RuntimeError, SubprocessError) as exc:
        print(f"Ошибка: не удалось получить upstream: {exc}", file=sys.stderr)
        return 1

    try:
        return _run_update(args, target, clone_root)
    except (OSError, RuntimeError) as exc:
        # Security review M3: without this, any I/O error, a symlink
        # refusal (SymlinkRefusedError/OSError, M1), a path-containment
        # refusal (PathContainmentError/RuntimeError, m5), or
        # _apply_deletions's own safety-assert RuntimeError surfaced as a
        # raw traceback instead of this tool's established clean
        # RU-error-and-exit-1 convention (matches the _resolve_upstream
        # handling three lines above and sync_to_os.do_real_run).
        print(f"Ошибка: обновление framework не удалось: {exc}", file=sys.stderr)
        return 1
    finally:
        if tmp_ctx is not None:
            tmp_ctx.cleanup()


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    return do_update_framework(args)


if __name__ == "__main__":
    # No sys.path setup needed here: Python already inserts this script's
    # own directory (.claude/shared/scripts, sibling to sync_to_os.py and
    # sync_tool/) at sys.path[0] before any top-level code in this module
    # runs, including the `import sync_to_os` above.
    sys.exit(main())
