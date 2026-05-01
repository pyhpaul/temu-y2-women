from __future__ import annotations

import json
from pathlib import Path
from shutil import copyfile
from typing import Any, Mapping, Sequence

from temu_y2_women.feedback_loop import apply_reviewed_dress_concept_feedback


_SCHEMA_VERSION = "style-family-visual-feedback-dry-run-v1"
_BATCH_SCHEMA_VERSION = "style-family-visual-feedback-batch-v1"
_WORKSPACE_ELEMENTS = "elements.json"
_WORKSPACE_LEDGER = "feedback_ledger.json"
_REPORTS_DIR = "reports"


def dry_run_visual_feedback_apply(
    *,
    batch_path: Path,
    workspace_dir: Path,
    active_elements_path: Path,
    ledger_path: Path,
    taxonomy_path: Path,
) -> dict[str, Any]:
    batch = _read_batch(batch_path)
    workspace_paths = _prepare_workspace(workspace_dir, active_elements_path, ledger_path)
    case_reports = [
        _apply_case(batch_path, case, workspace_paths, taxonomy_path)
        for case in _batch_cases(batch)
    ]
    element_changes = _element_changes(
        _read_json_object(active_elements_path),
        _read_json_object(workspace_paths["elements"]),
    )
    return _dry_run_report(
        batch_path=batch_path,
        active_elements_path=active_elements_path,
        ledger_path=ledger_path,
        taxonomy_path=taxonomy_path,
        workspace_paths=workspace_paths,
        cases=case_reports,
        element_changes=element_changes,
    )


def write_visual_feedback_dry_run_report(report: Mapping[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def _prepare_workspace(
    workspace_dir: Path,
    active_elements_path: Path,
    ledger_path: Path,
) -> dict[str, Path]:
    workspace_dir.mkdir(parents=True, exist_ok=True)
    reports_dir = workspace_dir / _REPORTS_DIR
    reports_dir.mkdir(parents=True, exist_ok=True)
    elements_copy = workspace_dir / _WORKSPACE_ELEMENTS
    ledger_copy = workspace_dir / _WORKSPACE_LEDGER
    copyfile(active_elements_path, elements_copy)
    if ledger_path.exists():
        copyfile(ledger_path, ledger_copy)
    else:
        _write_json(ledger_copy, {"schema_version": "feedback-ledger-v1", "records": []})
    return {"root": workspace_dir, "elements": elements_copy, "ledger": ledger_copy, "reports": reports_dir}


def _apply_case(
    batch_path: Path,
    case: Mapping[str, Any],
    workspace_paths: Mapping[str, Path],
    taxonomy_path: Path,
) -> dict[str, Any]:
    family_id = _string_value(case, "style_family_id")
    report_path = workspace_paths["reports"] / f"{family_id}-feedback_report.json"
    result = apply_reviewed_dress_concept_feedback(
        reviewed_path=_resolved_path(batch_path, _string_value(case, "feedback_review_path")),
        result_path=_resolved_path(batch_path, _string_value(case, "concept_path")),
        active_elements_path=workspace_paths["elements"],
        ledger_path=workspace_paths["ledger"],
        report_path=report_path,
        taxonomy_path=taxonomy_path,
    )
    if "error" in result:
        return _error_case_report(family_id, case, result)
    return _applied_case_report(family_id, case, report_path, result)


def _applied_case_report(
    family_id: str,
    case: Mapping[str, Any],
    report_path: Path,
    result: Mapping[str, Any],
) -> dict[str, Any]:
    summary = _mapping_value(result, "summary")
    affected = result.get("affected_elements", [])
    affected_elements = affected if isinstance(affected, list) else []
    return {
        "style_family_id": family_id,
        "feedback_decision": _string_value(case, "feedback_decision") or _string_value(summary, "decision"),
        "status": "applied",
        "report_path": str(report_path),
        "affected_element_count": int(summary.get("affected_element_count", 0)),
        "applied_delta": float(summary.get("applied_delta", 0.0)),
        "clamped_element_count": int(summary.get("clamped_element_count", 0)),
        "affected_element_ids": _affected_element_ids(affected_elements),
    }


def _error_case_report(
    family_id: str,
    case: Mapping[str, Any],
    result: Mapping[str, Any],
) -> dict[str, Any]:
    error = _mapping_value(result, "error")
    return {
        "style_family_id": family_id,
        "feedback_decision": _string_value(case, "feedback_decision"),
        "status": "error",
        "error_code": _string_value(error, "code"),
        "affected_element_count": 0,
        "applied_delta": 0.0,
        "clamped_element_count": 0,
        "affected_element_ids": [],
    }


def _dry_run_report(
    *,
    batch_path: Path,
    active_elements_path: Path,
    ledger_path: Path,
    taxonomy_path: Path,
    workspace_paths: Mapping[str, Path],
    cases: Sequence[Mapping[str, Any]],
    element_changes: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": _SCHEMA_VERSION,
        "status": "applied" if not _error_count(cases) else "partial_failure",
        "source_artifacts": _source_artifacts(batch_path, active_elements_path, ledger_path, taxonomy_path),
        "workspace": {key: str(path) for key, path in workspace_paths.items()},
        "summary": _summary(cases, element_changes),
        "cases": list(cases),
        "element_changes": list(element_changes),
    }


def _summary(
    cases: Sequence[Mapping[str, Any]],
    element_changes: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    return {
        "total": len(cases),
        "applied": sum(1 for case in cases if case.get("status") == "applied"),
        "errors": _error_count(cases),
        "keep": sum(1 for case in cases if case.get("feedback_decision") == "keep"),
        "reject": sum(1 for case in cases if case.get("feedback_decision") == "reject"),
        "affected_element_events": sum(int(case.get("affected_element_count", 0)) for case in cases),
        "unique_affected_elements": len(_unique_affected_ids(cases)),
        "net_changed_elements": len(element_changes),
    }


def _element_changes(
    original: Mapping[str, Any],
    updated: Mapping[str, Any],
) -> list[dict[str, Any]]:
    original_by_id = _elements_by_id(original)
    changes = []
    for element in _elements(updated):
        element_id = str(element.get("element_id", ""))
        original_element = original_by_id.get(element_id)
        if original_element:
            change = _element_change(original_element, element)
            if change:
                changes.append(change)
    return changes


def _element_change(original: Mapping[str, Any], updated: Mapping[str, Any]) -> dict[str, Any] | None:
    old_score = _score(original)
    new_score = _score(updated)
    delta = round(new_score - old_score, 4)
    if delta == 0:
        return None
    return {
        "element_id": str(updated.get("element_id", "")),
        "slot": str(updated.get("slot", "")),
        "value": str(updated.get("value", "")),
        "original_base_score": old_score,
        "dry_run_base_score": new_score,
        "delta": delta,
    }


def _read_batch(path: Path) -> Mapping[str, Any]:
    payload = _read_json_object(path)
    if payload.get("schema_version") != _BATCH_SCHEMA_VERSION:
        raise ValueError("Visual feedback batch schema_version is not supported.")
    return payload


def _batch_cases(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return _cases(payload)


def _cases(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    cases = payload.get("cases", [])
    if isinstance(cases, list):
        return [case for case in cases if isinstance(case, dict)]
    return []


def _source_artifacts(batch_path: Path, elements_path: Path, ledger_path: Path, taxonomy_path: Path) -> dict[str, str]:
    return {
        "visual_feedback_batch": str(batch_path),
        "active_elements": str(elements_path),
        "ledger": str(ledger_path),
        "taxonomy": str(taxonomy_path),
    }


def _affected_element_ids(affected_elements: Sequence[Any]) -> list[str]:
    return [str(item["element_id"]) for item in affected_elements if isinstance(item, dict) and "element_id" in item]


def _unique_affected_ids(cases: Sequence[Mapping[str, Any]]) -> set[str]:
    return {
        str(element_id)
        for case in cases
        for element_id in case.get("affected_element_ids", [])
    }


def _error_count(cases: Sequence[Mapping[str, Any]]) -> int:
    return sum(1 for case in cases if case.get("status") == "error")


def _elements_by_id(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {str(element.get("element_id", "")): element for element in _elements(payload)}


def _elements(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    elements = payload.get("elements", [])
    if isinstance(elements, list):
        return [element for element in elements if isinstance(element, dict)]
    return []


def _score(payload: Mapping[str, Any]) -> float:
    return round(float(payload.get("base_score", 0.0)), 4)


def _resolved_path(anchor_path: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute() or candidate.exists():
        return candidate
    return anchor_path.parent / candidate


def _mapping_value(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key, {})
    return value if isinstance(value, dict) else {}


def _string_value(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key, "")
    return value if isinstance(value, str) else ""


def _read_json_object(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
