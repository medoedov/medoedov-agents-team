#!/usr/bin/env python3
"""Fail closed before approving or executing a task manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import Any

import yaml
from yaml.tokens import AliasToken, AnchorToken


MAX_MANIFEST_BYTES = 512_000
MAX_REPORT_BYTES = 512_000
MAX_REFS = 100
MAX_TASKS = 500
MAX_FINDINGS = 1_000
MAX_ERRORS = 100
VALIDATORS = {"task-validator", "reality-checker"}
SEVERITIES = {"critical", "major", "minor", "info"}
CATEGORIES = {
    "atomicity", "skill_task_mismatch", "template", "traceability", "reality",
    "dependency", "file_ownership", "shared_resource", "security", "other",
}
FORBIDDEN_DISPOSITIONS = {
    "waived", "accepted_as_is", "accepted_by_parent", "exception",
    "approved_exception", "waiver", "accepted_exception",
}


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_digest(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return _digest(data.encode("utf-8"))


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _is_link(path: Path, stop: Path) -> bool:
    current = path
    while _inside(current, stop):
        try:
            info = current.lstat()
        except OSError:
            return True
        attrs = getattr(info, "st_file_attributes", 0)
        if stat.S_ISLNK(info.st_mode) or attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
            return True
        if current == stop:
            break
        current = current.parent
    return False


def _bounded_bytes(path: Path, limit: int) -> bytes:
    size = path.stat().st_size
    if size > limit:
        raise ValueError(f"file exceeds {limit} bytes")
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"file exceeds {limit} bytes")
    return data


def _load_yaml(path: Path) -> tuple[dict[str, Any], bytes]:
    data = _bounded_bytes(path, MAX_MANIFEST_BYTES)
    text = data.decode("utf-8")
    if any(isinstance(token, (AliasToken, AnchorToken)) for token in yaml.scan(text)):
        raise ValueError("YAML anchors and aliases are forbidden")
    value = yaml.safe_load(text)
    if not isinstance(value, dict):
        raise ValueError("manifest must be a YAML mapping")
    return value, data


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(_bounded_bytes(path, MAX_REPORT_BYTES).decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("report must be a JSON object")
    return value


def _safe_file(project: Path, path: Path, scope: Path) -> bool:
    try:
        resolved = path.resolve(strict=True)
        project_resolved = project.resolve(strict=True)
        scope_resolved = scope.resolve(strict=True)
    except OSError:
        return False
    return _inside(resolved, project_resolved) and _inside(resolved, scope_resolved) and not _is_link(path, project)


def _strings(value: Any, name: str, errors: list[str], maximum: int = MAX_TASKS) -> list[str]:
    if not isinstance(value, list) or len(value) > maximum:
        errors.append(f"{name} must be a list with at most {maximum} items")
        return []
    if any(not isinstance(item, str) or not item for item in value):
        errors.append(f"{name} must contain nonempty strings")
        return []
    return value


def _refs(value: Any, errors: list[str]) -> list[dict[str, str]]:
    if not isinstance(value, list) or not value or len(value) > MAX_REFS:
        errors.append(f"validation_reports must be a nonempty list with at most {MAX_REFS} items")
        return []
    refs: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            errors.append("validation report refs require exactly path and sha256")
            continue
        if not isinstance(item["path"], str) or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"] or ""):
            errors.append("validation report ref path/hash is malformed")
            continue
        refs.append(item)
    return refs


def _task_state(project: Path, manifest: dict[str, Any], feature: str, errors: list[str]) -> tuple[list[dict[str, Any]], dict[str, Any], str, str]:
    tasks = manifest.get("tasks")
    if not isinstance(tasks, list) or not tasks or len(tasks) > MAX_TASKS:
        errors.append(f"tasks must be a nonempty list with at most {MAX_TASKS} items")
        return [], {}, "", ""
    canonical: list[dict[str, Any]] = []
    ids: set[str] = set()
    task_scope = project / "work" / feature / "tasks"
    for index, task in enumerate(tasks):
        if not isinstance(task, dict):
            errors.append(f"tasks[{index}] must be a mapping")
            continue
        task_id = task.get("id")
        if not isinstance(task_id, str) or not task_id:
            legacy = task.get("task_id")
            errors.append(f"tasks[{index}] requires canonical id" + (f"; migrate legacy task_id {legacy!r}" if legacy else ""))
            continue
        path, deps = task.get("path"), task.get("depends_on")
        if task_id in ids or not isinstance(path, str) or not path or not isinstance(deps, list):
            errors.append(f"task {task_id!r} has duplicate id or malformed path/depends_on")
            continue
        if any(not isinstance(dep, str) or not dep for dep in deps):
            errors.append(f"task {task_id!r} depends_on must contain canonical IDs")
            continue
        task_path = project / path
        if not _safe_file(project, task_path, task_scope):
            errors.append(f"task path is missing, linked, or outside feature tasks: {path}")
            task_file_hash = ""
        else:
            try:
                task_file_hash = _digest(_bounded_bytes(task_path, MAX_MANIFEST_BYTES))
            except (OSError, ValueError) as exc:
                errors.append(f"task file is unreadable: {path}: {type(exc).__name__}: {exc}")
                task_file_hash = ""
        ids.add(task_id)
        canonical.append({"id": task_id, "path": path, "depends_on": deps, "sha256": task_file_hash})
    if any(dep not in ids for task in canonical for dep in task["depends_on"]):
        errors.append("task dependencies must reference current canonical IDs")
    elif _has_cycle(canonical):
        errors.append("task dependency graph must be acyclic")
    count = manifest.get("task_count")
    if isinstance(count, bool) or not isinstance(count, int) or count != len(tasks):
        errors.append("task_count must be an exact integer matching tasks")
    mapping, map_digest = _file_map(project, manifest, feature, ids, errors)
    return canonical, mapping, _json_digest(canonical) if canonical else "", map_digest


def _has_cycle(tasks: list[dict[str, Any]]) -> bool:
    pending = {task["id"]: set(task["depends_on"]) for task in tasks}
    while pending:
        ready = {task_id for task_id, deps in pending.items() if not deps}
        if not ready:
            return True
        pending = {task_id: deps - ready for task_id, deps in pending.items() if task_id not in ready}
    return False


def _file_map(project: Path, manifest: dict[str, Any], feature: str, ids: set[str], errors: list[str]) -> tuple[dict[str, Any], str]:
    ref = manifest.get("task_files_map")
    scope = project / "work" / feature
    if not isinstance(ref, str) or not ref or not _safe_file(project, project / ref, scope):
        errors.append("task_files_map must reference an existing contained non-link file")
        return {}, ""
    try:
        mapping, data = _load_yaml(project / ref)
    except (OSError, UnicodeError, ValueError, yaml.YAMLError, RecursionError) as exc:
        errors.append(f"task_files_map is malformed: {type(exc).__name__}: {exc}")
        return {}, ""
    if set(mapping) != ids or any(not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value) for value in mapping.values()):
        errors.append("task_files_map must exactly cover current IDs with string path lists")
    return mapping, _digest(data)


def _finding(value: Any, ref: str, errors: list[str]) -> dict[str, Any] | None:
    required = {"severity", "category", "blocking"}
    if not isinstance(value, dict) or not required.issubset(value):
        errors.append(f"malformed finding in {ref}")
        return None
    finding_id = value.get("semantic_id", value.get("id"))
    if not isinstance(finding_id, str) or not finding_id:
        errors.append(f"finding in {ref} requires stable semantic_id or id")
        return None
    if value["severity"] not in SEVERITIES or value["category"] not in CATEGORIES or type(value["blocking"]) is not bool:
        errors.append(f"finding {finding_id} in {ref} has invalid typed fields")
        return None
    for key in ("disposition", "resolution"):
        if value.get(key) in FORBIDDEN_DISPOSITIONS:
            errors.append(f"finding {finding_id} in {ref} uses forbidden structured disposition")
    return {**value, "stable_id": finding_id}


def _report(value: dict[str, Any], ref: str, feature: str, task_hash: str, map_hash: str, task_files: dict[str, str], errors: list[str]) -> tuple[dict[str, Any], list[dict[str, Any]]] | None:
    validator = value.get("validator")
    identity = value.get("iteration", value.get("run_id"))
    exact = value.get("validated_task_ids")
    if value.get("schema_version") != 1 or validator not in VALIDATORS:
        errors.append(f"report has invalid schema_version/validator: {ref}")
        return None
    if value.get("feature") != feature or value.get("status") != "approved":
        errors.append(f"report has wrong feature or non-approved status: {ref}")
    if isinstance(identity, bool) or not isinstance(identity, (str, int)) or identity == "":
        errors.append(f"report lacks iteration/run identity: {ref}")
    ids = _strings(exact, f"validated_task_ids in {ref}", errors)
    reported_files = value.get("validated_task_sha256")
    expected_files = {task_id: task_files[task_id] for task_id in ids if task_id in task_files}
    if not isinstance(reported_files, dict) or reported_files != expected_files:
        errors.append(f"report has stale or malformed validated_task_sha256: {ref}")
    if value.get("task_set_sha256") != task_hash or value.get("task_files_map_sha256") != map_hash:
        errors.append(f"report has stale task-set or file-map digest: {ref}")
    raw_findings = value.get("findings")
    if not isinstance(raw_findings, list) or len(raw_findings) > MAX_FINDINGS:
        errors.append(f"findings in {ref} must be a bounded list")
        raw_findings = []
    findings = [item for raw in raw_findings if (item := _finding(raw, ref, errors))]
    return {**value, "validated_task_ids": ids, "ref": ref}, findings


def _active_reports(project: Path, manifest: dict[str, Any], feature: str, task_hash: str, map_hash: str, task_files: dict[str, str], errors: list[str]) -> list[tuple[dict[str, Any], list[dict[str, Any]]]]:
    refs = _refs(manifest.get("validation_reports"), errors)
    scope = project / "work" / feature / "logs" / "tasks"
    loaded: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    for ref_item in refs:
        ref = ref_item["path"]
        path = project / ref
        immutable_name = re.search(r"(?:iteration[-_]?\d+|run[-_][a-zA-Z0-9-]+)\.json$", path.name)
        if not immutable_name or not _safe_file(project, path, scope):
            errors.append(f"report is missing, linked, or outside logs/tasks: {ref}")
            continue
        try:
            data = _bounded_bytes(path, MAX_REPORT_BYTES)
            if _digest(data) != ref_item["sha256"]:
                raise ValueError("report SHA-256 mismatch")
            report = json.loads(data.decode("utf-8"))
            if not isinstance(report, dict):
                raise ValueError("report must be a JSON object")
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError, RecursionError) as exc:
            errors.append(f"report is malformed: {ref}: {type(exc).__name__}: {exc}")
            continue
        parsed = _report(report, ref, feature, task_hash, map_hash, task_files, errors)
        if parsed:
            loaded.append(parsed)
    return loaded


def _coverage(reports: list[tuple[dict[str, Any], list[dict[str, Any]]]], ids: set[str], errors: list[str]) -> None:
    task_validator = set().union(*(set(r["validated_task_ids"]) for r, _ in reports if r["validator"] == "task-validator"))
    reality = set().union(*(set(r["validated_task_ids"]) for r, _ in reports if r["validator"] == "reality-checker" and r.get("cross_task") is True))
    if task_validator != ids:
        errors.append("task-validator reports must exactly cover every current task")
    if reality != ids:
        errors.append("cross-task reality-checker reports must exactly cover every current task")
    for report, findings in reports:
        for finding in findings:
            if finding["severity"] == "critical" or (finding["severity"] == "major" and finding["blocking"]):
                errors.append(f"active report retains blocking finding: {report['ref']}#{finding['stable_id']}")


def _split_resolutions(project: Path, manifest: dict[str, Any], feature: str, tasks: list[dict[str, Any]], mapping: dict[str, Any], reports: list[tuple[dict[str, Any], list[dict[str, Any]]]], errors: list[str]) -> None:
    resolutions = manifest.get("atomicity_resolutions", [])
    if not isinstance(resolutions, list) or len(resolutions) > MAX_FINDINGS:
        errors.append("atomicity_resolutions must be a bounded list")
        return
    by_id = {task["id"]: task for task in tasks}
    active = [report for report, _ in reports]
    for index, item in enumerate(resolutions):
        if not isinstance(item, dict) or item.get("resolution") != "resolved_by_split":
            errors.append(f"atomicity_resolutions[{index}] must be resolved_by_split")
            continue
        source_id, ref, finding_id = item.get("source_task_id"), item.get("report_ref"), item.get("finding_id")
        source_hash = item.get("source_task_sha256")
        replacements = item.get("replacement_task_ids", item.get("replacement_tasks"))
        valid_source = isinstance(source_hash, str) and re.fullmatch(r"[0-9a-f]{64}", source_hash)
        if not all(isinstance(value, str) and value for value in (source_id, finding_id)) or not valid_source or not isinstance(ref, dict):
            errors.append(f"atomicity_resolutions[{index}] lacks source_task_id/report_ref/finding_id")
            continue
        replacement_ids = _strings(replacements, f"replacement IDs for {finding_id}", errors)
        if len(set(replacement_ids)) < 2 or any(value not in by_id or value not in mapping for value in replacement_ids):
            errors.append(f"resolved_by_split {finding_id} requires at least two distinct current replacement IDs covered by paths/map")
            continue
        if source_id in by_id or not _historical_finding(project, feature, ref, finding_id, source_id, source_hash, errors):
            continue
        if not any(_supersedes(report.get("supersedes"), ref, finding_id) and set(replacement_ids) <= set(report["validated_task_ids"]) for report in active):
            errors.append(f"resolved_by_split {finding_id} lacks active revalidation superseding the exact source finding and covering replacements")


def _supersedes(value: Any, ref: dict[str, str], finding_id: str) -> bool:
    return isinstance(value, list) and any(isinstance(item, dict) and item == {"report_ref": ref, "finding_id": finding_id} for item in value)


def _historical_finding(project: Path, feature: str, ref: dict[str, str], finding_id: str, source_id: str, source_hash: str, errors: list[str]) -> bool:
    scope = project / "work" / feature / "logs" / "tasks"
    if not isinstance(ref, dict) or set(ref) != {"path", "sha256"} or not isinstance(ref.get("path"), str) or not re.fullmatch(r"[0-9a-f]{64}", str(ref.get("sha256", ""))):
        errors.append("historical source report ref requires path and sha256")
        return False
    path = project / ref["path"]
    if not re.search(r"(?:iteration[-_]?\d+|run[-_][a-zA-Z0-9-]+)\.json$", path.name) or not _safe_file(project, path, scope):
        errors.append(f"historical source report is missing or outside logs/tasks: {ref}")
        return False
    try:
        data = _bounded_bytes(path, MAX_REPORT_BYTES)
        if _digest(data) != ref.get("sha256"):
            raise ValueError("report SHA-256 mismatch")
        report = json.loads(data.decode("utf-8"))
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError, RecursionError) as exc:
        errors.append(f"historical source report is malformed: {ref.get('path')}: {type(exc).__name__}: {exc}")
        return False
    if not isinstance(report, dict):
        errors.append("historical source report must be a JSON object")
        return False
    findings = report.get("findings")
    task_ids = report.get("validated_task_ids")
    task_files = report.get("validated_task_sha256")
    required = (report.get("schema_version") == 1 and report.get("validator") in VALIDATORS and
                report.get("status") == "changes_required" and isinstance(task_ids, list) and source_id in task_ids and
                isinstance(task_files, dict) and task_files.get(source_id) == source_hash and
                isinstance(report.get("task_set_sha256"), str) and isinstance(report.get("task_files_map_sha256"), str) and
                isinstance(report.get("iteration", report.get("run_id")), (str, int)))
    if not required or report.get("feature") != feature or not isinstance(findings, list) or len(findings) > MAX_FINDINGS:
        errors.append(f"historical source report has wrong feature or findings: {ref.get('path')}")
        return False
    found = [raw for raw in findings if isinstance(raw, dict) and raw.get("semantic_id", raw.get("id")) == finding_id]
    parsed = _finding(found[0], ref["path"], errors) if len(found) == 1 else None
    blocking_source = parsed and parsed["category"] in {"atomicity", "skill_task_mismatch"} and parsed["severity"] in {"critical", "major"} and parsed["blocking"] is True
    if not blocking_source:
        errors.append(f"historical source finding is missing or malformed: {ref.get('path')}#{finding_id}")
        return False
    return True


def validation_result(project: Path, manifest_path: Path, logical_path: Path | None = None) -> dict[str, Any]:
    errors: list[str] = []
    project = project.resolve()
    if not _safe_file(project, manifest_path, project):
        errors.append("manifest is missing, linked, or outside project")
        return _result(logical_path or manifest_path, b"", "", "", errors)
    try:
        manifest, data = _load_yaml(manifest_path)
    except (OSError, UnicodeError, ValueError, yaml.YAMLError, RecursionError) as exc:
        errors.append(f"manifest is malformed: {type(exc).__name__}: {exc}")
        return _result(logical_path or manifest_path, b"", "", "", errors)
    logical = logical_path or manifest_path
    feature = manifest.get("feature")
    if not isinstance(feature, str) or not feature or "/" in feature or "\\" in feature:
        errors.append("feature must be a nonempty path-safe string")
        feature = "__invalid__"
    expected_logical = project / "work" / feature / "tasks-manifest.yml"
    if logical.resolve() != expected_logical.resolve():
        errors.append("logical manifest path must be canonical work/{feature}/tasks-manifest.yml")
    _manifest_dispositions(manifest, errors)
    tasks, mapping, task_hash, map_hash = _task_state(project, manifest, feature, errors)
    task_files = {task["id"]: task["sha256"] for task in tasks}
    reports = _active_reports(project, manifest, feature, task_hash, map_hash, task_files, errors)
    _coverage(reports, {task["id"] for task in tasks}, errors)
    _split_resolutions(project, manifest, feature, tasks, mapping, reports, errors)
    cross = manifest.get("cross_task_pass")
    if not isinstance(cross, dict) or cross.get("completed") is not True or cross.get("unresolved_findings") != []:
        errors.append("cross_task_pass requires completed true and exactly empty unresolved_findings")
    return _result(logical, data, task_hash, map_hash, errors)


def _manifest_dispositions(manifest: dict[str, Any], errors: list[str]) -> None:
    values: list[Any] = [manifest.get("atomicity_disposition")]
    triage = manifest.get("validation_triage")
    if isinstance(triage, dict):
        atomicity = triage.get("atomicity")
        if isinstance(atomicity, dict):
            values.append(atomicity.get("disposition"))
    if any(value in FORBIDDEN_DISPOSITIONS for value in values):
        errors.append("manifest uses forbidden structured atomicity disposition")


def _result(path: Path, data: bytes, task_hash: str, map_hash: str, errors: list[str]) -> dict[str, Any]:
    bounded = errors[:MAX_ERRORS]
    if len(errors) > MAX_ERRORS:
        bounded.append(f"additional errors omitted: {len(errors) - MAX_ERRORS}")
    return {"schema_version": 1, "passed": not errors, "manifest": str(path), "manifest_sha256": _digest(data) if data else "", "task_set_sha256": task_hash, "task_files_map_sha256": map_hash, "errors": bounded, "run_id": _json_digest([_digest(data), task_hash, map_hash])[:16]}


def validate(project: Path, manifest_path: Path) -> list[str]:
    return validation_result(project, manifest_path)["errors"]


def _write_report(project: Path, path: Path, result: dict[str, Any], logical: Path) -> None:
    project = project.resolve()
    target = path.resolve()
    scope = (logical.parent / "logs" / "tasks").resolve()
    unique = re.fullmatch(r"manifest-guard-(?:\d+|iteration-?\d+|run-[a-zA-Z0-9-]+)\.json", path.name)
    if not unique or not _inside(target, scope) or _is_link(path.parent, project) or path.exists():
        raise ValueError("report output must be a non-linked JSON path in current feature logs/tasks")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temp.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def main(args: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--logical-manifest", type=Path)
    parser.add_argument("--report", type=Path)
    parsed = parser.parse_args(args)
    project = parsed.project.resolve()
    manifest = parsed.manifest if parsed.manifest.is_absolute() else project / parsed.manifest
    logical = parsed.logical_manifest if parsed.logical_manifest and parsed.logical_manifest.is_absolute() else project / parsed.logical_manifest if parsed.logical_manifest else manifest
    result = validation_result(project, manifest, logical)
    if parsed.report:
        report = parsed.report if parsed.report.is_absolute() else project / parsed.report
        try:
            _write_report(project, report, result, logical)
        except (OSError, UnicodeError, ValueError) as exc:
            result["passed"] = False
            result["errors"].append(f"cannot write report: {type(exc).__name__}: {exc}")
    print("Task manifest guard: PASS" if result["passed"] else f"Task manifest guard: FAIL ({len(result['errors'])} errors)")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
