#!/usr/bin/env python3
"""Validate and atomically apply a baseline-bound technical amendment."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml


HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
SAFE_FEATURE = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")
SAFE_TASK = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
WINDOWS_PATH = re.compile(r"\b[A-Za-z]:\\[^\s]+")
POSIX_PATH = re.compile(r"(?<![\w<])/(?:[^/\s]+/)*[^/\s]+")
ISO_TIMESTAMP = re.compile(
    r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}"
    r"(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?\b",
    re.IGNORECASE,
)

APPROVAL_FIELDS = {
    "status",
    "approved_at",
    "owner_ref",
    "approved_plan_sha256",
    "auto_continue",
    "directive_evidence_ref",
    "amendment_gate_manifest_ref",
    "amendment_gate_manifest_sha256",
    "continuation",
}
RISK_SIGNALS = {
    "dependency_or_version_change",
    "download_or_cost_expansion",
    "external_or_destructive_effect",
    "docker_ssh_deploy_or_incident",
    "new_objective_or_unrelated_path",
    "product_or_spec_conflict",
    "unavailable_external_dependency",
    "technical_repair_exhausted",
}
SAFE_CATEGORIES = {
    "runner",
    "fixture",
    "mapping",
    "task_envelope",
    "verification_mechanism",
}
SCENARIO_CLASSIFICATION_TABLE = (
    ("technical_repair_exhausted", "recovery_stop"),
    ("unavailable_external_dependency", "recovery_stop"),
    ("dependency_or_version_change", "product_authority"),
    ("download_or_cost_expansion", "product_authority"),
    ("external_or_destructive_effect", "product_authority"),
    ("docker_ssh_deploy_or_incident", "product_authority"),
    ("new_objective_or_unrelated_path", "product_authority"),
    ("product_or_spec_conflict", "product_authority"),
)


class ValidationError(ValueError):
    """The bundle cannot authorize a technical continuation."""


def _fail(message: str) -> None:
    raise ValidationError(message)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _canonical_json_sha256(value: object) -> str:
    return _sha256(_canonical_json_bytes(value))


def _require_mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        _fail(f"{label} must be a mapping.")
    return value


def _require_list(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        _fail(f"{label} must be a list.")
    return value


def _require_sha(value: object, label: str) -> str:
    if not isinstance(value, str) or not HEX_SHA256.fullmatch(value):
        _fail(f"{label} must be a non-null lowercase SHA-256 digest.")
    return value


def _unique_strings(
    value: object,
    label: str,
    *,
    allow_empty: bool = False,
) -> list[str]:
    items = _require_list(value, label)
    if not allow_empty and not items:
        _fail(f"{label} must not be empty.")
    if any(not isinstance(item, str) or not item for item in items):
        _fail(f"{label} must contain non-empty strings.")
    if len(items) != len(set(items)):
        _fail(f"{label} must contain unique values.")
    return items


def _is_reparse(path: Path) -> bool:
    try:
        details = path.lstat()
    except OSError:
        return False
    attributes = getattr(details, "st_file_attributes", 0)
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return path.is_symlink() or bool(attributes & flag)


def _check_components(root: Path, path: Path) -> None:
    try:
        relative = path.relative_to(root)
    except ValueError:
        _fail("Path is not contained by the project root.")
    current = root
    for part in relative.parts:
        current = current / part
        if current.exists() and _is_reparse(current):
            _fail("Path contains a symlink or reparse point.")


def _relative_ref(reference: object, label: str) -> Path:
    if not isinstance(reference, str) or not reference or "\\" in reference:
        _fail(f"{label} must be a project-relative POSIX path.")
    relative = Path(reference)
    invalid = any(part in {"", ".", ".."} or ":" in part for part in relative.parts)
    if relative.is_absolute() or invalid:
        _fail(f"{label} must be contained and free of traversal.")
    return relative


def _project_path(
    root: Path,
    reference: object,
    *,
    label: str,
    kind: str = "file",
) -> Path:
    relative = _relative_ref(reference, label)
    candidate = root.joinpath(*relative.parts)
    _check_components(root, candidate)
    exists = candidate.is_file() if kind == "file" else candidate.is_dir()
    if not exists:
        _fail(f"{label} required {kind} is missing.")
    return candidate


def _project_output_path(root: Path, reference: object, label: str) -> Path:
    relative = _relative_ref(reference, label)
    candidate = root.joinpath(*relative.parts)
    _check_components(root, candidate)
    if candidate.exists() or not candidate.parent.is_dir():
        _fail(f"{label} already exists or has no existing parent.")
    return candidate


def _read_raw(path: Path, label: str) -> bytes:
    if not path.is_file() or _is_reparse(path):
        _fail(f"{label} is missing or is a symlink/reparse point.")
    data = path.read_bytes()
    if data.startswith(b"\xef\xbb\xbf"):
        _fail(f"{label} contains a forbidden UTF-8 BOM.")
    return data


def _normalized_utf8(path: Path, label: str) -> bytes:
    raw = _read_raw(path, label)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError(f"{label} is not valid UTF-8.") from exc
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def _load_yaml(path: Path, label: str) -> Mapping[str, Any]:
    try:
        value = yaml.safe_load(_normalized_utf8(path, label).decode("utf-8"))
    except yaml.YAMLError as exc:
        raise ValidationError(f"{label} is invalid YAML.") from exc
    return _require_mapping(value, label)


def _load_json(path: Path, label: str) -> Mapping[str, Any]:
    try:
        value = json.loads(_normalized_utf8(path, label).decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{label} is invalid JSON.") from exc
    return _require_mapping(value, label)


def _parse_execution_plan(path: Path) -> tuple[Mapping[str, Any], bytes]:
    normalized = _normalized_utf8(path, "execution plan")
    if not normalized.startswith(b"---\n"):
        _fail("Execution plan is missing YAML frontmatter.")
    closing = normalized.find(b"\n---\n", 4)
    if closing < 0:
        _fail("Execution plan frontmatter is not closed.")
    try:
        header = yaml.safe_load(normalized[4:closing].decode("utf-8"))
    except yaml.YAMLError as exc:
        raise ValidationError("Execution plan frontmatter is invalid.") from exc
    return _require_mapping(header, "execution plan frontmatter"), normalized[
        closing + len(b"\n---\n") :
    ]


def _section_digest(root: Path, ref: object, section: object, label: str) -> str:
    path = _project_path(root, ref, label=f"{label} artifact")
    text = _normalized_utf8(path, f"{label} artifact").decode("utf-8")
    if not isinstance(section, str) or not section.startswith("#"):
        _fail(f"{label} section reference is invalid.")
    wanted = section.lstrip("#").strip().casefold()
    selected, level = [], None
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        if stripped.startswith("#"):
            current = len(stripped) - len(stripped.lstrip("#"))
            heading = stripped[current:].strip().casefold()
            if level is not None and current <= level:
                break
            if heading == wanted:
                level = current
        if level is not None:
            selected.append(line)
    if not selected:
        _fail(f"{label} section reference did not resolve.")
    return _sha256("".join(selected).encode("utf-8"))


def normalize_failure_signature(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail("Failure signature is missing.")
    text = value.replace("\r\n", "\n").replace("\r", "\n")
    text = ISO_TIMESTAMP.sub("<timestamp>", text)
    text = WINDOWS_PATH.sub("<path>", text)
    text = POSIX_PATH.sub("<path>", text)
    return " ".join(text.split()).strip()


def derive_failure_signature(evidence: Mapping[str, Any]) -> str:
    required = {
        "schema_version",
        "evidence_type",
        "error_type",
        "error_code",
        "message",
    }
    if set(evidence) != required or evidence.get("schema_version") != 1:
        _fail("Failure evidence schema is invalid.")
    if evidence.get("evidence_type") != "technical_failure":
        _fail("Failure evidence type is invalid.")
    error_type = evidence.get("error_type")
    error_code = evidence.get("error_code")
    message = evidence.get("message")
    if not all(isinstance(value, str) and value for value in (error_type, error_code, message)):
        _fail("Failure evidence type, code, or message is missing.")
    prefix = f"{error_type.casefold()} {error_code.casefold()}: "
    return prefix + normalize_failure_signature(message)


def compute_blocker_fingerprint(
    *,
    approved_plan_sha256: str,
    objective_ids: Sequence[str],
    failing_gate_id: str,
    failure_signature: str,
) -> str:
    _require_sha(approved_plan_sha256, "approved plan digest")
    objectives = sorted(_unique_strings(list(objective_ids), "objective IDs"))
    if not isinstance(failing_gate_id, str) or not failing_gate_id:
        _fail("Failing gate ID is missing.")
    payload = {
        "approved_plan_sha256": approved_plan_sha256,
        "objective_ids": objectives,
        "failing_gate_id": failing_gate_id,
        "normalized_failure_signature": failure_signature,
    }
    return _canonical_json_sha256(payload)


def classify_scenario(signals: Mapping[str, Any]) -> str:
    if set(signals).intersection(RISK_SIGNALS) != RISK_SIGNALS:
        return "recovery_stop"
    if any(not isinstance(signals[name], bool) for name in RISK_SIGNALS):
        return "recovery_stop"
    for signal, classification in SCENARIO_CLASSIFICATION_TABLE:
        if signals[signal]:
            return classification
    categories = signals.get("change_categories")
    if not isinstance(categories, list) or not categories:
        return "product_authority"
    if not set(categories).issubset(SAFE_CATEGORIES):
        return "product_authority"
    if signals.get("existing_objective") is not True:
        return "product_authority"
    return "technical_execution_amendment"


def _validate_continuation(value: object) -> Mapping[str, Any]:
    target = _require_mapping(value, "continuation")
    if set(target) != {"command", "argv", "digest"}:
        _fail("Continuation fields are invalid.")
    command = target.get("command")
    argv = _unique_strings(target.get("argv"), "continuation argv", allow_empty=True)
    payload = {"command": command, "argv": argv}
    if target.get("digest") != _canonical_json_sha256(payload):
        _fail("Continuation digest mismatch.")
    if command == "/do-task" and len(argv) == 1 and SAFE_TASK.fullmatch(argv[0]):
        return target
    if command == "/do-all-tasks" and len(argv) == 1 and SAFE_FEATURE.fullmatch(argv[0]):
        return target
    if command == "/write-code" and argv == []:
        return target
    _fail("Continuation command or normalized argv is not permitted.")


def _approval_from_plan(
    root: Path,
    plan_path: Path,
) -> tuple[Mapping[str, Any], str]:
    plan, body = _parse_execution_plan(plan_path)
    approval = _require_mapping(plan.get("execution_approval"), "execution approval")
    if set(approval) != APPROVAL_FIELDS or approval.get("status") != "approved":
        _fail("Initial execution approval fields are missing or not approved.")
    if not approval.get("approved_at") or not approval.get("owner_ref"):
        _fail("Initial execution approval metadata is missing.")
    if not isinstance(approval.get("auto_continue"), bool):
        _fail("Execution approval auto_continue must be boolean.")
    plan_digest = _sha256(body)
    if approval.get("approved_plan_sha256") != plan_digest:
        _fail("Approved plan body digest mismatch.")
    _project_path(root, approval.get("directive_evidence_ref"), label="directive evidence")
    _validate_continuation(approval.get("continuation"))
    return approval, plan_digest


def _validate_approval_projection(
    root: Path,
    plan_path: Path,
    approval: Mapping[str, Any],
    checkpoint: Mapping[str, Any],
) -> None:
    projection = _require_mapping(
        checkpoint.get("execution_approval_projection"),
        "execution approval projection",
    )
    expected = APPROVAL_FIELDS | {"plan_ref", "projection_sha256"}
    if set(projection) != expected:
        _fail("Execution approval projection fields are invalid.")
    if projection.get("plan_ref") != plan_path.relative_to(root).as_posix():
        _fail("Execution approval projection plan reference mismatch.")
    if any(projection.get(field) != approval.get(field) for field in APPROVAL_FIELDS):
        _fail("Execution approval projection canonical field mismatch.")
    payload = {key: value for key, value in projection.items() if key != "projection_sha256"}
    if projection.get("projection_sha256") != _canonical_json_sha256(payload):
        _fail("Execution approval projection digest mismatch.")


def _load_manifest(
    root: Path,
    approval: Mapping[str, Any],
    plan_digest: str,
) -> tuple[Path, Mapping[str, Any]]:
    path = _project_path(
        root,
        approval.get("amendment_gate_manifest_ref"),
        label="approval baseline manifest",
    )
    raw = _read_raw(path, "approval baseline manifest")
    if approval.get("amendment_gate_manifest_sha256") != _sha256(raw):
        _fail("Approval baseline manifest exact byte digest mismatch.")
    manifest = _load_yaml(path, "approval baseline manifest")
    if manifest.get("schema_version") != 2:
        _fail("Approval baseline manifest schema version is invalid.")
    if manifest.get("execution_plan_payload_sha256") != plan_digest:
        _fail("Manifest execution plan baseline digest mismatch.")
    if manifest.get("continuation") != approval.get("continuation"):
        _fail("Continuation and immutable manifest mismatch.")
    _validate_continuation(manifest.get("continuation"))
    return path, manifest


def _validate_manifest_sections(root: Path, manifest: Mapping[str, Any]) -> None:
    objectives = _require_mapping(manifest.get("objectives"), "manifest objectives")
    if not objectives:
        _fail("Manifest objectives must not be empty.")
    for objective_id, raw in objectives.items():
        entry = _require_mapping(raw, f"manifest objective {objective_id}")
        expected = _require_sha(entry.get("section_sha256"), "objective baseline digest")
        actual = _section_digest(
            root, entry.get("artifact_ref"), entry.get("section_ref"), f"objective {objective_id}"
        )
        if actual != expected:
            _fail("Current objective differs from immutable baseline.")
        _unique_strings(entry.get("task_ids"), "objective task IDs")
        _unique_strings(entry.get("required_gate_ids"), "objective gate IDs", allow_empty=True)
    acceptance = _require_mapping(
        manifest.get("acceptance_criteria"), "manifest acceptance criteria"
    )
    expected = _require_sha(acceptance.get("section_sha256"), "acceptance baseline digest")
    actual = _section_digest(
        root, acceptance.get("artifact_ref"), acceptance.get("section_ref"), "acceptance"
    )
    if actual != expected:
        _fail("Current acceptance criteria differ from immutable baseline.")


def _manifest_inventory(
    manifest: Mapping[str, Any],
    key: str,
    label: str,
) -> dict[str, Mapping[str, Any]]:
    entries = _require_list(manifest.get(key), label)
    indexed: dict[str, Mapping[str, Any]] = {}
    for raw in entries:
        entry = _require_mapping(raw, label)
        path = entry.get("path")
        if not isinstance(path, str) or path in indexed:
            _fail(f"{label} path is missing or duplicated.")
        indexed[path] = entry
    return indexed


def _validate_manifest_inventories(manifest: Mapping[str, Any]) -> None:
    tasks = _manifest_inventory(
        manifest, "approved_task_plan_artifacts", "approved task/plan artifacts"
    )
    existing = _manifest_inventory(
        manifest, "approved_existing_write_paths", "approved existing write paths"
    )
    addable = _manifest_inventory(
        manifest, "approved_absent_addable_paths", "approved absent/addable paths"
    )
    if set(existing).intersection(addable):
        _fail("Manifest existing and absent path inventories overlap.")
    for entry in [*tasks.values(), *existing.values(), *addable.values()]:
        _unique_strings(entry.get("objective_ids"), "inventory objective IDs")
        _unique_strings(entry.get("task_ids"), "inventory task IDs")
        categories = _unique_strings(entry.get("allowed_categories"), "allowed categories")
        if not set(categories).issubset(SAFE_CATEGORIES):
            _fail("Manifest inventory contains an unsafe category.")
    for entry in [*tasks.values(), *existing.values()]:
        _require_sha(entry.get("sha256"), "manifest exact byte digest")


def _validate_manifest_gate_policy(manifest: Mapping[str, Any]) -> None:
    gates = _require_mapping(manifest.get("gates"), "manifest gates")
    if not gates:
        _fail("Manifest gates must not be empty.")
    for gate_id, raw in gates.items():
        gate = _require_mapping(raw, f"manifest gate {gate_id}")
        if gate.get("evidence_schema") != "terminal-gate/v1":
            _fail("Manifest gate evidence schema is invalid.")
        if gate.get("evidence_type") not in {"application/json", "application/yaml"}:
            _fail("Manifest gate evidence type is invalid.")
        if not gate.get("evaluator_id"):
            _fail("Manifest gate evaluator identity is missing.")
        _unique_strings(gate.get("source_evidence_types"), "source evidence types")
    policy = _require_mapping(manifest.get("classification_policy"), "classification policy")
    if policy.get("evidence_schema") != "technical-amendment-classification/v1":
        _fail("Classification evidence schema is invalid.")
    if policy.get("evidence_type") != "application/json" or not policy.get("evaluator_id"):
        _fail("Classification evidence type or evaluator identity is invalid.")


def _validate_manifest(root: Path, manifest: Mapping[str, Any]) -> None:
    required = {
        "objectives",
        "acceptance_criteria",
        "approved_task_plan_artifacts",
        "task_file_map",
        "approved_existing_write_paths",
        "approved_absent_addable_paths",
        "gates",
        "classification_policy",
        "continuation",
    }
    if not required.issubset(manifest):
        _fail("Approval baseline manifest is incomplete.")
    _validate_manifest_sections(root, manifest)
    _validate_manifest_inventories(manifest)
    _validate_manifest_gate_policy(manifest)
    task_map = _require_mapping(manifest.get("task_file_map"), "manifest task file map")
    _require_sha(task_map.get("sha256"), "task file map baseline digest")
    _require_mapping(task_map.get("approved_entries"), "approved task file map entries")


def _validate_objective_trace(
    root: Path,
    amendment: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> set[str]:
    objectives = _require_mapping(manifest.get("objectives"), "manifest objectives")
    trace = _require_list(amendment.get("objective_trace"), "objective trace")
    affected: set[str] = set()
    for raw in trace:
        entry = _require_mapping(raw, "objective trace entry")
        objective_id = entry.get("objective_id")
        baseline = _require_mapping(objectives.get(objective_id), "objective baseline")
        if objective_id in affected:
            _fail("Objective trace contains a duplicate objective.")
        affected.add(str(objective_id))
        expected = baseline.get("section_sha256")
        before = (entry.get("before_artifact_ref"), entry.get("before_section_ref"), entry.get("before_sha256"))
        baseline_tuple = (baseline.get("artifact_ref"), baseline.get("section_ref"), expected)
        if before != baseline_tuple:
            _fail("Objective before snapshot does not match immutable manifest baseline.")
        after = _section_digest(
            root, entry.get("after_artifact_ref"), entry.get("after_section_ref"), "objective after"
        )
        if entry.get("after_sha256") != after or after != expected:
            _fail("Objective after snapshot differs from immutable baseline.")
    if not affected:
        _fail("Objective trace must not be empty.")
    return affected


def _validate_acceptance(
    root: Path,
    amendment: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> None:
    baseline = _require_mapping(manifest.get("acceptance_criteria"), "acceptance baseline")
    snapshots = _require_mapping(amendment.get("acceptance_criteria"), "acceptance snapshots")
    before = (
        snapshots.get("before_artifact_ref"),
        snapshots.get("before_section_ref"),
        snapshots.get("before_sha256"),
    )
    expected = (
        baseline.get("artifact_ref"),
        baseline.get("section_ref"),
        baseline.get("section_sha256"),
    )
    if before != expected:
        _fail("Acceptance before snapshot does not match immutable manifest baseline.")
    after = _section_digest(
        root,
        snapshots.get("after_artifact_ref"),
        snapshots.get("after_section_ref"),
        "acceptance after",
    )
    if snapshots.get("after_sha256") != after or after != baseline.get("section_sha256"):
        _fail("Acceptance after snapshot differs from immutable baseline.")


def _validate_delta_identity(
    entry: Mapping[str, Any],
    baseline: Mapping[str, Any],
    affected: set[str],
    label: str,
) -> str:
    objectives = set(_unique_strings(entry.get("objective_ids"), f"{label} objective IDs"))
    tasks = set(_unique_strings(entry.get("task_ids"), f"{label} task IDs"))
    if objectives != set(baseline.get("objective_ids", [])) or not objectives.issubset(affected):
        _fail(f"{label} objective IDs do not match immutable manifest.")
    if tasks != set(baseline.get("task_ids", [])):
        _fail(f"{label} task IDs do not match immutable manifest.")
    category = entry.get("category")
    if category not in baseline.get("allowed_categories", []):
        _fail(f"{label} category is not approved by the immutable manifest.")
    return str(category)


def _validate_task_artifact_delta(
    root: Path,
    amendment: Mapping[str, Any],
    manifest: Mapping[str, Any],
    affected: set[str],
) -> set[str]:
    inventory = _manifest_inventory(
        manifest, "approved_task_plan_artifacts", "approved task/plan artifacts"
    )
    delta = _require_mapping(amendment.get("allowed_delta"), "allowed delta")
    entries = _require_list(delta.get("changed_plan_task_artifacts"), "task artifact delta")
    categories: set[str] = set()
    for raw in entries:
        entry = _require_mapping(raw, "task artifact delta entry")
        path_ref = entry.get("path")
        baseline = _require_mapping(inventory.get(path_ref), "task artifact baseline")
        if entry.get("before_sha256") != baseline.get("sha256"):
            _fail("Task artifact before digest does not match immutable baseline.")
        path = _project_path(root, path_ref, label="task artifact after")
        if entry.get("after_sha256") != _sha256(_read_raw(path, "task artifact after")):
            _fail("Task artifact after exact byte digest mismatch.")
        categories.add(_validate_delta_identity(entry, baseline, affected, "task artifact"))
    return categories


def _normalize_task_map(value: Mapping[str, Any]) -> dict[str, list[str]]:
    tasks = value.get("tasks", value)
    mapping = _require_mapping(tasks, "task file map entries")
    normalized: dict[str, list[str]] = {}
    for task_id, paths in mapping.items():
        if not isinstance(task_id, str):
            _fail("Task file map task ID is invalid.")
        normalized[task_id] = sorted(_unique_strings(paths, "task file map paths", allow_empty=True))
    return normalized


def _load_task_map(path: Path, label: str) -> dict[str, list[str]]:
    return _normalize_task_map(_load_yaml(path, label))


def _validate_write_entry(
    root: Path,
    entry: Mapping[str, Any],
    baseline: Mapping[str, Any],
    affected: set[str],
) -> str:
    change = entry.get("change")
    if change == "added" and entry.get("before_sha256") is not None:
        _fail("Added path before digest must be null.")
    if change == "changed" and entry.get("before_sha256") != baseline.get("sha256"):
        _fail("Changed path before digest does not match immutable baseline.")
    if change not in {"added", "changed"}:
        _fail("Write path change type is invalid.")
    path = _project_path(root, entry.get("path"), label="write path after")
    if entry.get("after_sha256") != _sha256(_read_raw(path, "write path after")):
        _fail("Write path after exact byte digest mismatch.")
    return _validate_delta_identity(entry, baseline, affected, "write path")


def _validate_write_path_delta(
    root: Path,
    amendment: Mapping[str, Any],
    manifest: Mapping[str, Any],
    affected: set[str],
) -> tuple[set[str], list[Mapping[str, Any]]]:
    existing = _manifest_inventory(
        manifest, "approved_existing_write_paths", "approved existing write paths"
    )
    addable = _manifest_inventory(
        manifest, "approved_absent_addable_paths", "approved absent/addable paths"
    )
    delta = _require_mapping(amendment.get("allowed_delta"), "allowed delta")
    entries = _require_list(delta.get("added_or_changed_write_paths"), "write path delta")
    categories: set[str] = set()
    seen: set[str] = set()
    for raw in entries:
        entry = _require_mapping(raw, "write path delta entry")
        path_ref = entry.get("path")
        if not isinstance(path_ref, str) or path_ref in seen:
            _fail("Write path delta is missing or duplicated.")
        seen.add(path_ref)
        inventory = addable if entry.get("change") == "added" else existing
        baseline = inventory.get(path_ref)
        if not isinstance(baseline, dict):
            _fail("Write path is unrelated to immutable manifest inventory.")
        categories.add(_validate_write_entry(root, entry, baseline, affected))
    return categories, entries


def _expected_task_map(
    manifest: Mapping[str, Any],
    writes: list[Mapping[str, Any]],
) -> dict[str, list[str]]:
    baseline = _require_mapping(manifest.get("task_file_map"), "manifest task file map")
    expected = _normalize_task_map(
        _require_mapping(baseline.get("approved_entries"), "approved task map entries")
    )
    for entry in writes:
        for task_id in _unique_strings(entry.get("task_ids"), "write path task IDs"):
            expected.setdefault(task_id, [])
            if entry.get("path") not in expected[task_id]:
                expected[task_id].append(str(entry.get("path")))
                expected[task_id].sort()
    return expected


def _validate_task_map_delta(
    root: Path,
    amendment: Mapping[str, Any],
    manifest: Mapping[str, Any],
    writes: list[Mapping[str, Any]],
) -> bool:
    baseline = _require_mapping(manifest.get("task_file_map"), "manifest task file map")
    delta = _require_mapping(amendment.get("allowed_delta"), "allowed delta")
    entry = _require_mapping(delta.get("task_file_map"), "task file map delta")
    if entry.get("path") != baseline.get("path"):
        _fail("Task file map path differs from immutable manifest.")
    if entry.get("before_sha256") != baseline.get("sha256"):
        _fail("Task file map before digest differs from immutable baseline.")
    path = _project_path(root, entry.get("path"), label="task file map after")
    actual_digest = _sha256(_read_raw(path, "task file map after"))
    if entry.get("after_sha256") != actual_digest:
        _fail("Task file map after exact byte digest mismatch.")
    if _load_task_map(path, "task file map after") != _expected_task_map(manifest, writes):
        _fail("Task file map contains an unrelated or missing path.")
    return entry.get("before_sha256") != entry.get("after_sha256")


def _validate_delta(
    root: Path,
    amendment: Mapping[str, Any],
    manifest: Mapping[str, Any],
    affected: set[str],
) -> set[str]:
    categories = _validate_task_artifact_delta(root, amendment, manifest, affected)
    write_categories, writes = _validate_write_path_delta(
        root, amendment, manifest, affected
    )
    categories.update(write_categories)
    if _validate_task_map_delta(root, amendment, manifest, writes):
        categories.add("mapping")
    if not categories or not categories.issubset(SAFE_CATEGORIES):
        _fail("Allowed delta has no provable safe change category.")
    return categories


def _derive_required_gates(
    manifest: Mapping[str, Any],
    affected: set[str],
) -> set[str]:
    objectives = _require_mapping(manifest.get("objectives"), "manifest objectives")
    all_gates = set(_require_mapping(manifest.get("gates"), "manifest gates"))
    required: set[str] = set()
    for objective_id in affected:
        objective = _require_mapping(objectives.get(objective_id), "objective baseline")
        mapped = set(
            _unique_strings(
                objective.get("required_gate_ids"),
                "objective required gates",
                allow_empty=True,
            )
        )
        required.update(mapped or all_gates)
    if not required or not required.issubset(all_gates):
        _fail("Derived required gate set is invalid.")
    return required


def _load_digest_bound_json(
    root: Path,
    ref: object,
    digest: object,
    label: str,
) -> tuple[Path, Mapping[str, Any]]:
    path = _project_path(root, ref, label=label)
    raw = _read_raw(path, label)
    if _require_sha(digest, f"{label} digest") != _sha256(raw):
        _fail(f"{label} exact byte digest mismatch.")
    return path, _load_json(path, label)


def _validate_failure_identity(
    root: Path,
    amendment: Mapping[str, Any],
    plan_digest: str,
    affected: set[str],
    required_gates: set[str],
) -> tuple[str, Path]:
    failing_gate = amendment.get("failing_gate_id")
    if failing_gate not in required_gates:
        _fail("Failing gate is not in the immutable derived required gate set.")
    path, evidence = _load_digest_bound_json(
        root,
        amendment.get("failure_evidence_ref"),
        amendment.get("failure_evidence_sha256"),
        "failure evidence",
    )
    signature = derive_failure_signature(evidence)
    fingerprint = compute_blocker_fingerprint(
        approved_plan_sha256=plan_digest,
        objective_ids=sorted(affected),
        failing_gate_id=str(failing_gate),
        failure_signature=signature,
    )
    expected = (fingerprint, f"ta-{fingerprint[:24]}", f"repair-{fingerprint[:24]}")
    actual = (
        amendment.get("blocker_fingerprint"),
        amendment.get("amendment_id"),
        amendment.get("repair_loop_id"),
    )
    if actual != expected or amendment.get("root_blocker_id") != fingerprint:
        _fail("Amendment identity is not derived from immutable failure fingerprint.")
    return fingerprint, path


def _validate_amendment_record_path(
    root: Path,
    amendment_path: Path,
    amendment: Mapping[str, Any],
) -> None:
    amendment_id = amendment.get("amendment_id")
    if not isinstance(amendment_id, str) or not SAFE_ID.fullmatch(amendment_id):
        _fail("Amendment identity is not filesystem safe.")
    relative = amendment_path.relative_to(root).as_posix()
    if amendment.get("record_path") != relative:
        _fail("Amendment record path does not match its canonical path.")
    if amendment_path.name != f"{amendment_id}.yml":
        _fail("Amendment filename does not match its derived identity.")


def _ledger_files(directory: Path) -> tuple[Path, list[Path]]:
    all_yml = sorted(directory.glob("*.yml"))
    if any(_is_reparse(path) for path in all_yml):
        _fail("Ledger contains a symlink or reparse point.")
    heads = [path for path in all_yml if path.name.startswith("head")]
    if len(heads) != 1 or heads[0].name != "head.yml":
        _fail("Ledger must contain exactly one canonical head.")
    records = [path for path in all_yml if path.name.startswith("attempt-")]
    expected_names = [f"attempt-{number:03d}.yml" for number in range(1, len(records) + 1)]
    if [path.name for path in records] != expected_names:
        _fail("Ledger attempt sequence has a gap or truncation.")
    if len(all_yml) != len(records) + 1:
        _fail("Ledger contains an unexpected YAML record.")
    return heads[0], records


def _validate_attempt_record(
    root: Path,
    path: Path,
    attempt_no: int,
    previous: str | None,
    fingerprint: str,
    amendment: Mapping[str, Any],
) -> tuple[str, str]:
    record = _load_yaml(path, f"attempt {attempt_no}")
    expected_fields = {
        "schema_version",
        "blocker_fingerprint",
        "attempt_no",
        "previous_attempt_sha256",
        "failure_evidence_ref",
        "failure_evidence_sha256",
        "outcome",
        "created_at",
    }
    if set(record) != expected_fields or record.get("schema_version") != 1:
        _fail("Ledger attempt schema is invalid.")
    identity = (record.get("blocker_fingerprint"), record.get("attempt_no"), record.get("previous_attempt_sha256"))
    if identity != (fingerprint, attempt_no, previous):
        _fail("Ledger attempt chain identity mismatch.")
    failure = (record.get("failure_evidence_ref"), record.get("failure_evidence_sha256"))
    expected_failure = (amendment.get("failure_evidence_ref"), amendment.get("failure_evidence_sha256"))
    if failure != expected_failure:
        _fail("Ledger attempt failure evidence changed fingerprint identity.")
    _load_digest_bound_json(root, *failure, f"attempt {attempt_no} failure evidence")
    if record.get("outcome") not in {"passed", "failed"} or not record.get("created_at"):
        _fail("Ledger attempt outcome or timestamp is invalid.")
    return _sha256(_read_raw(path, f"attempt {attempt_no}")), str(record.get("outcome"))


def _validate_ledger_head(
    root: Path,
    head_path: Path,
    records: list[Path],
    fingerprint: str,
    final_digest: str,
) -> Mapping[str, Any]:
    head = _load_yaml(head_path, "ledger head")
    expected_fields = {
        "schema_version",
        "blocker_fingerprint",
        "attempt_count",
        "head_record_ref",
        "head_record_sha256",
    }
    if set(head) != expected_fields or head.get("schema_version") != 1:
        _fail("Ledger head schema is invalid.")
    expected_ref = records[-1].relative_to(root).as_posix()
    identity = (head.get("blocker_fingerprint"), head.get("attempt_count"))
    if identity != (fingerprint, len(records)):
        _fail("Ledger head count or fingerprint mismatch.")
    if head.get("head_record_ref") != expected_ref or head.get("head_record_sha256") != final_digest:
        _fail("Ledger digest-chained head mismatch.")
    return head


def _validate_ledger(
    root: Path,
    amendment: Mapping[str, Any],
    fingerprint: str,
) -> tuple[Path, int, bool]:
    ledger = _require_mapping(
        amendment.get("technical_validation_ledger"), "technical validation ledger"
    )
    directory = _project_path(
        root, ledger.get("directory_ref"), label="attempt ledger", kind="directory"
    )
    expected_suffix = f"technical-amendment-attempts/{fingerprint}"
    if not directory.relative_to(root).as_posix().endswith(expected_suffix):
        _fail("Attempt ledger directory is not canonical for the fingerprint.")
    head_path, records = _ledger_files(directory)
    if not records or len(records) > 3:
        _fail("Attempt ledger must contain one to three records; attempt four is refused.")
    previous, outcomes = None, []
    for attempt_no, record_path in enumerate(records, start=1):
        previous, outcome = _validate_attempt_record(
            root, record_path, attempt_no, previous, fingerprint, amendment
        )
        outcomes.append(outcome)
    _validate_ledger_head(root, head_path, records, fingerprint, str(previous))
    if ledger.get("head_ref") != head_path.relative_to(root).as_posix():
        _fail("Amendment ledger head reference mismatch.")
    if ledger.get("head_sha256") != _sha256(_read_raw(head_path, "ledger head")):
        _fail("Amendment ledger head exact byte digest mismatch.")
    exhausted = len(records) == 3 and outcomes[-1] == "failed"
    return head_path, len(records), exhausted


def _validate_attempt_status(
    amendment: Mapping[str, Any],
    count: int,
    exhausted: bool,
    head_path: Path,
) -> None:
    last = _load_yaml(
        head_path.parent / f"attempt-{count:03d}.yml",
        "last technical attempt",
    )
    if exhausted and amendment.get("status") != "technical-repair-exhausted":
        _fail("Third failed attempt must be technical-repair-exhausted.")
    if exhausted:
        return
    if amendment.get("status") != "validated" or last.get("outcome") != "passed":
        _fail("Validated amendment requires a passed ledger head attempt.")


def _classification_evidence(
    root: Path,
    amendment: Mapping[str, Any],
    manifest: Mapping[str, Any],
    categories: set[str],
    affected: set[str],
    exhausted: bool,
) -> Mapping[str, Any]:
    inputs = _require_mapping(amendment.get("classification_inputs"), "classification inputs")
    if set(inputs.get("change_categories", [])) != categories:
        _fail("Classification categories do not match the manifest-bound delta.")
    if set(inputs.get("objective_ids", [])) != affected:
        _fail("Classification objective IDs do not match the manifest-bound delta.")
    _, evidence = _load_digest_bound_json(
        root, inputs.get("evidence_ref"), inputs.get("evidence_sha256"), "classification evidence"
    )
    policy = _require_mapping(manifest.get("classification_policy"), "classification policy")
    identity = (evidence.get("evidence_schema"), evidence.get("evaluator_id"))
    expected = (policy.get("evidence_schema"), policy.get("evaluator_id"))
    if evidence.get("schema_version") != 1 or identity != expected:
        _fail("Classification evidence schema or evaluator identity mismatch.")
    if set(evidence.get("change_categories", [])) != categories:
        _fail("Classification evidence categories mismatch.")
    if set(evidence.get("objective_ids", [])) != affected:
        _fail("Classification evidence objective IDs mismatch.")
    signals = _require_mapping(evidence.get("signals"), "classification signals")
    if set(signals) != RISK_SIGNALS or any(not isinstance(value, bool) for value in signals.values()):
        _fail("Classification signal is missing or unprovable.")
    if signals.get("new_objective_or_unrelated_path") is not False:
        _fail(
            "Technical classification rejected bundle as product_authority: "
            "path/objective signal conflicts with the validated baseline."
        )
    if signals.get("technical_repair_exhausted") is not exhausted:
        _fail(
            "Technical classification rejected bundle as recovery_stop: "
            "repair exhaustion signal conflicts with the ledger."
        )
    return signals


def _validate_classification(
    root: Path,
    amendment: Mapping[str, Any],
    manifest: Mapping[str, Any],
    categories: set[str],
    affected: set[str],
    exhausted: bool,
) -> str:
    signals = dict(
        _classification_evidence(
            root, amendment, manifest, categories, affected, exhausted
        )
    )
    signals["change_categories"] = sorted(categories)
    signals["existing_objective"] = True
    classification = classify_scenario(signals)
    if classification != "technical_execution_amendment":
        _fail(f"Technical classification rejected bundle as {classification}.")
    if amendment.get("classification") != classification:
        _fail("Amendment classification does not match executable policy.")
    return classification


def _load_typed_evidence(
    root: Path,
    gate: Mapping[str, Any],
    ref: object,
    digest: object,
) -> tuple[Path, Mapping[str, Any]]:
    path = _project_path(root, ref, label="terminal gate evidence")
    raw = _read_raw(path, "terminal gate evidence")
    if _require_sha(digest, "terminal gate evidence digest") != _sha256(raw):
        _fail("Terminal gate evidence exact byte digest mismatch.")
    if gate.get("evidence_type") == "application/json":
        return path, _load_json(path, "terminal gate evidence")
    return path, _load_yaml(path, "terminal gate evidence")


def _validate_source_evidence(
    root: Path,
    sources: object,
    allowed_types: set[str],
) -> None:
    entries = _require_list(sources, "terminal source evidence")
    if not entries:
        _fail("Terminal gate source evidence must not be empty.")
    for raw in entries:
        entry = _require_mapping(raw, "terminal source evidence entry")
        if set(entry) != {"evidence_type", "ref", "sha256"}:
            _fail("Terminal source evidence schema is invalid.")
        if entry.get("evidence_type") not in allowed_types:
            _fail("Terminal source evidence type is not approved.")
        path = _project_path(root, entry.get("ref"), label="terminal source evidence")
        if entry.get("sha256") != _sha256(_read_raw(path, "terminal source evidence")):
            _fail("Terminal source evidence digest mismatch.")


def _validate_terminal_evidence(
    root: Path,
    gate_id: str,
    gate: Mapping[str, Any],
    result: Mapping[str, Any],
) -> None:
    _, evidence = _load_typed_evidence(
        root, gate, result.get("evidence_ref"), result.get("evidence_sha256")
    )
    expected_fields = {
        "schema_version",
        "gate_id",
        "evaluator_id",
        "status",
        "terminal_gate_passed",
        "source_evidence",
        "completed_at",
    }
    if set(evidence) != expected_fields or evidence.get("schema_version") != 1:
        _fail("Terminal gate evidence schema is invalid; process summaries cannot pass.")
    identity = (evidence.get("gate_id"), evidence.get("evaluator_id"))
    if identity != (gate_id, gate.get("evaluator_id")):
        _fail("Terminal gate evaluator identity mismatch.")
    if evidence.get("status") != "passed" or evidence.get("terminal_gate_passed") is not True:
        _fail("Terminal gate evidence did not pass terminally.")
    if not evidence.get("completed_at") or result.get("status") != "passed":
        _fail("Terminal gate status or completion timestamp is invalid.")
    allowed = set(gate.get("source_evidence_types", []))
    _validate_source_evidence(root, evidence.get("source_evidence"), allowed)


def _validate_gate_results(
    root: Path,
    amendment: Mapping[str, Any],
    manifest: Mapping[str, Any],
    required: set[str],
) -> None:
    declared = _unique_strings(amendment.get("required_gate_ids"), "required gate IDs")
    if set(declared) != required:
        _fail("Required gate IDs differ from immutable objective mapping.")
    results = _require_list(amendment.get("validation_results"), "validation results")
    if len(results) != len(required):
        _fail("Validation results do not exactly cover required gates.")
    gates = _require_mapping(manifest.get("gates"), "manifest gates")
    seen: set[str] = set()
    for raw in results:
        result = _require_mapping(raw, "validation result")
        gate_id = result.get("gate_id")
        if not isinstance(gate_id, str) or gate_id in seen or gate_id not in required:
            _fail("Validation result gate ID is missing, duplicate, or unrelated.")
        seen.add(gate_id)
        gate = _require_mapping(gates.get(gate_id), f"manifest gate {gate_id}")
        _validate_terminal_evidence(root, gate_id, gate, result)


def _validate_checkpoint_amendment(
    root: Path,
    checkpoint: Mapping[str, Any],
    amendment: Mapping[str, Any],
    amendment_path: Path,
    head_path: Path,
) -> None:
    projection = _require_mapping(
        checkpoint.get("technical_amendment"), "checkpoint technical amendment"
    )
    relative = amendment_path.relative_to(root).as_posix()
    expected = {
        "active_amendment_ref": relative,
        "amendment_id": amendment.get("amendment_id"),
        "classification": amendment.get("classification"),
        "status": amendment.get("status"),
        "root_blocker_id": amendment.get("root_blocker_id"),
        "repair_loop_id": amendment.get("repair_loop_id"),
        "blocker_fingerprint": amendment.get("blocker_fingerprint"),
        "base_approval_ref": amendment.get("base_approval_ref"),
        "approved_plan_sha256": amendment.get("approved_plan_sha256"),
        "required_gate_ids": amendment.get("required_gate_ids"),
        "ledger_head_ref": head_path.relative_to(root).as_posix(),
        "ledger_head_sha256": amendment["technical_validation_ledger"]["head_sha256"],
    }
    if any(projection.get(key) != value for key, value in expected.items()):
        _fail("Checkpoint technical amendment projection mismatch.")
    awaiting = _require_mapping(checkpoint.get("awaiting_user"), "awaiting user")
    if awaiting.get("active") is True and awaiting.get("amendment_ref") != relative:
        _fail("Awaiting-user amendment reference mismatch.")


def _validate_resume_projection(checkpoint: Mapping[str, Any]) -> None:
    resume = _require_mapping(checkpoint.get("resume_ready"), "resume ready")
    expected = {
        "active",
        "decision",
        "amendment_ref",
        "validator_evidence_ref",
        "validator_evidence_sha256",
        "continuation",
    }
    if set(resume) != expected:
        _fail("Resume-ready projection fields are invalid.")


def _bundle_paths(
    root: Path,
    execution_plan_path: Path,
    amendment_path: Path,
    checkpoint_path: Path,
) -> tuple[Path, Path, Path]:
    for path, label in (
        (execution_plan_path, "execution plan"),
        (amendment_path, "technical amendment"),
        (checkpoint_path, "checkpoint"),
    ):
        _check_components(root, path)
        _read_raw(path, label)
    return execution_plan_path, amendment_path, checkpoint_path


def _base_bundle(
    root: Path,
    plan_path: Path,
    amendment_path: Path,
    checkpoint_path: Path,
) -> tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any], Path, str]:
    checkpoint = _load_yaml(checkpoint_path, "checkpoint")
    approval, plan_digest = _approval_from_plan(root, plan_path)
    _validate_approval_projection(root, plan_path, approval, checkpoint)
    manifest_path, manifest = _load_manifest(root, approval, plan_digest)
    _validate_manifest(root, manifest)
    amendment = _load_yaml(amendment_path, "technical amendment")
    expected_base = plan_path.relative_to(root).as_posix() + "#execution_approval"
    if amendment.get("base_approval_ref") != expected_base:
        _fail("Amendment base approval reference mismatch.")
    if amendment.get("approved_plan_sha256") != plan_digest:
        _fail("Amendment approved plan digest mismatch.")
    return checkpoint, manifest, amendment, manifest_path, plan_digest


def _validate_bundle_core(
    root: Path,
    amendment_path: Path,
    checkpoint: Mapping[str, Any],
    manifest: Mapping[str, Any],
    amendment: Mapping[str, Any],
    plan_digest: str,
) -> tuple[str, set[str], set[str], Path, int]:
    affected = _validate_objective_trace(root, amendment, manifest)
    _validate_acceptance(root, amendment, manifest)
    categories = _validate_delta(root, amendment, manifest, affected)
    required = _derive_required_gates(manifest, affected)
    fingerprint, _ = _validate_failure_identity(
        root, amendment, plan_digest, affected, required
    )
    _validate_amendment_record_path(root, amendment_path, amendment)
    head_path, count, exhausted = _validate_ledger(root, amendment, fingerprint)
    _validate_attempt_status(amendment, count, exhausted, head_path)
    classification = _validate_classification(
        root, amendment, manifest, categories, affected, exhausted
    )
    _validate_gate_results(root, amendment, manifest, required)
    _validate_checkpoint_amendment(
        root, checkpoint, amendment, amendment_path, head_path
    )
    _validate_resume_projection(checkpoint)
    return classification, affected, required, head_path, count


def _artifact_result(
    root: Path,
    plan_path: Path,
    amendment_path: Path,
    checkpoint_path: Path,
    manifest_path: Path,
    head_path: Path,
) -> dict[str, str]:
    paths = {
        "execution_plan": plan_path,
        "amendment": amendment_path,
        "checkpoint": checkpoint_path,
        "manifest": manifest_path,
        "ledger_head": head_path,
    }
    result: dict[str, str] = {}
    for name, path in paths.items():
        result[f"{name}_ref"] = path.relative_to(root).as_posix()
        result[f"{name}_sha256"] = _sha256(_read_raw(path, name))
    return result


def validate_bundle(
    project_root: Path,
    execution_plan_path: Path,
    amendment_path: Path,
    checkpoint_path: Path,
) -> dict[str, Any]:
    if _is_reparse(project_root):
        _fail("Project root is a symlink/reparse point.")
    root = project_root.resolve()
    if not root.is_dir() or _is_reparse(root):
        _fail("Project root is missing or unsafe.")
    plan_path, amendment_path, checkpoint_path = _bundle_paths(
        root, execution_plan_path, amendment_path, checkpoint_path
    )
    checkpoint, manifest, amendment, manifest_path, plan_digest = _base_bundle(
        root, plan_path, amendment_path, checkpoint_path
    )
    classification, affected, required, head_path, count = _validate_bundle_core(
        root, amendment_path, checkpoint, manifest, amendment, plan_digest
    )
    approval, _ = _approval_from_plan(root, plan_path)
    direct = approval.get("auto_continue") is True
    result: dict[str, Any] = {
        "schema_version": 2,
        "valid": True,
        "classification": classification,
        "decision": "direct_resume" if direct else "resume_ready",
        "continuation": copy.deepcopy(approval.get("continuation")),
        "clear_awaiting_user": True,
        "resume_ready": not direct,
        "reapproval_required": False,
        "approved_plan_sha256": plan_digest,
        "amendment_id": amendment.get("amendment_id"),
        "blocker_fingerprint": amendment.get("blocker_fingerprint"),
        "required_gate_ids": sorted(required),
        "verified_objective_ids": sorted(affected),
        "ledger_attempt_count": count,
    }
    result.update(
        _artifact_result(
            root, plan_path, amendment_path, checkpoint_path, manifest_path, head_path
        )
    )
    return result


def _evidence_payload(
    validation: Mapping[str, Any],
    created_at: str,
) -> dict[str, Any]:
    keys = {
        "decision",
        "continuation",
        "classification",
        "required_gate_ids",
        "execution_plan_ref",
        "execution_plan_sha256",
        "amendment_ref",
        "amendment_sha256",
        "manifest_ref",
        "manifest_sha256",
        "ledger_head_ref",
        "ledger_head_sha256",
    }
    payload = {key: copy.deepcopy(validation[key]) for key in keys}
    payload.update(
        {
            "schema_version": 2,
            "validator_id": "technical-amendment-validator/v2",
            "valid": True,
            "pre_transition_checkpoint_ref": validation["checkpoint_ref"],
            "pre_transition_checkpoint_sha256": validation["checkpoint_sha256"],
            "created_at": created_at,
        }
    )
    payload["result_sha256"] = _canonical_json_sha256(payload)
    return payload


def _write_json_no_clobber(path: Path, value: Mapping[str, Any]) -> None:
    data = json.dumps(
        value, ensure_ascii=False, indent=2, sort_keys=True
    ).encode("utf-8") + b"\n"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        raise


def write_validation_evidence(
    project_root: Path,
    execution_plan_path: Path,
    amendment_path: Path,
    checkpoint_path: Path,
    evidence_path: Path,
    *,
    created_at: str | None = None,
) -> dict[str, Any]:
    root = project_root.resolve()
    _check_components(root, evidence_path)
    if evidence_path.exists() or not evidence_path.parent.is_dir():
        _fail("Validation evidence no-clobber path already exists or is invalid.")
    validation = validate_bundle(
        root, execution_plan_path, amendment_path, checkpoint_path
    )
    timestamp = created_at or datetime.now(timezone.utc).isoformat()
    payload = _evidence_payload(validation, timestamp)
    _write_json_no_clobber(evidence_path, payload)
    return payload


def _validate_result_digest(evidence: Mapping[str, Any]) -> None:
    claimed = evidence.get("result_sha256")
    payload = {key: value for key, value in evidence.items() if key != "result_sha256"}
    if claimed != _canonical_json_sha256(payload):
        _fail("Validator evidence result digest is invalid or tampered.")
    if evidence.get("validator_id") != "technical-amendment-validator/v2":
        _fail("Validator evidence identity is invalid.")
    if evidence.get("valid") is not True:
        _fail("Validator evidence is not valid.")


def _verify_transition_artifacts(
    root: Path,
    evidence: Mapping[str, Any],
) -> None:
    for name in ("execution_plan", "amendment", "manifest", "ledger_head"):
        path = _project_path(root, evidence.get(f"{name}_ref"), label=name)
        actual = _sha256(_read_raw(path, name))
        if evidence.get(f"{name}_sha256") != actual:
            _fail(f"Validator evidence {name} digest is stale or tampered.")
    _validate_continuation(evidence.get("continuation"))
    if evidence.get("decision") not in {"direct_resume", "resume_ready"}:
        _fail("Validator evidence resume decision is invalid.")


def _transitioned_checkpoint(
    checkpoint: Mapping[str, Any],
    evidence: Mapping[str, Any],
    evidence_ref: str,
    evidence_sha256: str,
) -> dict[str, Any]:
    updated = copy.deepcopy(dict(checkpoint))
    awaiting = _require_mapping(updated.get("awaiting_user"), "awaiting user")
    awaiting["active"] = False
    awaiting["since"] = None
    awaiting["question"] = None
    awaiting["blocked_teammates"] = []
    awaiting["amendment_ref"] = None
    awaiting["cleared_reason"] = "false_technical_approval_gate"
    awaiting["cleared_at"] = evidence.get("created_at")
    technical = _require_mapping(updated.get("technical_amendment"), "technical amendment")
    technical["status"] = "validated"
    technical["validator_evidence_ref"] = evidence_ref
    technical["validator_evidence_sha256"] = evidence_sha256
    resume = _require_mapping(updated.get("resume_ready"), "resume ready")
    resume["active"] = evidence.get("decision") == "resume_ready"
    resume["decision"] = evidence.get("decision")
    resume["amendment_ref"] = evidence.get("amendment_ref")
    resume["validator_evidence_ref"] = evidence_ref
    resume["validator_evidence_sha256"] = evidence_sha256
    resume["continuation"] = copy.deepcopy(evidence.get("continuation"))
    return updated


def _atomic_yaml_replace(path: Path, value: Mapping[str, Any]) -> None:
    data = yaml.safe_dump(
        dict(value), allow_unicode=True, sort_keys=False
    ).encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".checkpoint-transition-", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        if temporary.exists():
            temporary.unlink()


def _fsync_directory(directory: Path) -> None:
    flags = getattr(os, "O_RDONLY", 0)
    directory_flag = getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(directory, flags | directory_flag)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _verify_transition(
    checkpoint: Mapping[str, Any],
    evidence: Mapping[str, Any],
    evidence_ref: str,
    evidence_sha256: str,
) -> None:
    awaiting = _require_mapping(checkpoint.get("awaiting_user"), "awaiting user")
    if awaiting.get("active") is not False:
        _fail("Atomic transition did not clear awaiting_user.")
    if awaiting.get("cleared_reason") != "false_technical_approval_gate":
        _fail("Atomic transition clear reason is invalid.")
    technical = _require_mapping(checkpoint.get("technical_amendment"), "technical amendment")
    identity = (technical.get("validator_evidence_ref"), technical.get("validator_evidence_sha256"))
    if identity != (evidence_ref, evidence_sha256) or technical.get("status") != "validated":
        _fail("Atomic transition validator evidence projection is invalid.")
    resume = _require_mapping(checkpoint.get("resume_ready"), "resume ready")
    if resume.get("decision") != evidence.get("decision"):
        _fail("Atomic transition resume decision is invalid.")
    if resume.get("continuation") != evidence.get("continuation"):
        _fail("Atomic transition continuation target is invalid.")


def apply_checkpoint_transition(
    project_root: Path,
    checkpoint_path: Path,
    evidence_path: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    _check_components(root, checkpoint_path)
    _check_components(root, evidence_path)
    evidence = _load_json(evidence_path, "validator evidence")
    _validate_result_digest(evidence)
    evidence_sha256 = _sha256(_read_raw(evidence_path, "validator evidence"))
    current = _read_raw(checkpoint_path, "checkpoint")
    if evidence.get("pre_transition_checkpoint_sha256") != _sha256(current):
        _fail("Checkpoint digest is stale; transition refused.")
    if evidence.get("pre_transition_checkpoint_ref") != checkpoint_path.relative_to(root).as_posix():
        _fail("Checkpoint transition reference mismatch.")
    _verify_transition_artifacts(root, evidence)
    checkpoint = _load_yaml(checkpoint_path, "checkpoint")
    evidence_ref = evidence_path.relative_to(root).as_posix()
    updated = _transitioned_checkpoint(
        checkpoint, evidence, evidence_ref, evidence_sha256
    )
    _atomic_yaml_replace(checkpoint_path, updated)
    verified = _load_yaml(checkpoint_path, "transitioned checkpoint")
    _verify_transition(verified, evidence, evidence_ref, evidence_sha256)
    return dict(verified)


def _resolve_cli_input(root: Path, reference: str, label: str) -> Path:
    return _project_path(root, reference, label=label)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate and transition a technical amendment."
    )
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--execution-plan", required=True)
    parser.add_argument("--amendment", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--transition", action="store_true")
    return parser


def _run_cli(args: argparse.Namespace) -> None:
    root_input = Path(args.project_root)
    if not root_input.is_absolute() or _is_reparse(root_input):
        _fail("Project root must be an absolute non-reparse directory.")
    root = root_input.resolve(strict=True)
    plan = _resolve_cli_input(root, args.execution_plan, "execution plan")
    amendment = _resolve_cli_input(root, args.amendment, "technical amendment")
    checkpoint = _resolve_cli_input(root, args.checkpoint, "checkpoint")
    result = _project_output_path(root, args.result, "validator result")
    write_validation_evidence(root, plan, amendment, checkpoint, result)
    if args.transition:
        apply_checkpoint_transition(root, checkpoint, result)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        _run_cli(args)
    except (OSError, ValidationError, yaml.YAMLError) as exc:
        print(f"technical amendment validation failed: {exc}", file=sys.stderr)
        return 2
    print("technical amendment validation completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
