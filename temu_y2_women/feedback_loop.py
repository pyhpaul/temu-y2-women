from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from temu_y2_women.errors import GenerationError
from temu_y2_women.evidence_repository import (
    load_elements,
    load_evidence_taxonomy,
    validate_element_records,
)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_ACTIVE_ELEMENTS_PATH = _PROJECT_ROOT / "data/mvp/dress/elements.json"
_DEFAULT_TAXONOMY_PATH = _PROJECT_ROOT / "data/mvp/dress/evidence_taxonomy.json"
_DEFAULT_LEDGER_PATH = _PROJECT_ROOT / "data/feedback/dress/feedback_ledger.json"
_REVIEW_SCHEMA_VERSION = "feedback-review-v1"
_LEDGER_SCHEMA_VERSION = "feedback-ledger-v1"
_REPORT_SCHEMA_VERSION = "feedback-report-v1"
_DECISION_DELTAS = {"keep": 0.02, "reject": -0.02}
_REVIEW_ROOT_FIELDS = {
    "schema_version",
    "category",
    "feedback_target",
    "decision",
    "notes",
}
_TARGET_FIELDS = {
    "request_normalized",
    "selected_elements",
    "selected_element_ids",
    "concept_score",
    "request_fingerprint",
    "concept_fingerprint",
}


def prepare_dress_concept_feedback(
    result_path: Path,
) -> dict[str, Any]:
    try:
        result = _load_success_result(result_path)
        return _build_review_template(result)
    except GenerationError as error:
        return error.to_dict()
    except OSError as error:
        return _io_error(error).to_dict()


def apply_reviewed_dress_concept_feedback(
    reviewed_path: Path,
    result_path: Path,
    active_elements_path: Path = _DEFAULT_ACTIVE_ELEMENTS_PATH,
    ledger_path: Path = _DEFAULT_LEDGER_PATH,
    report_path: Path | None = None,
    taxonomy_path: Path = _DEFAULT_TAXONOMY_PATH,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    try:
        reviewed, expected, taxonomy, active_elements = _prepare_validated_feedback(
            reviewed_path=reviewed_path,
            result_path=result_path,
            active_elements_path=active_elements_path,
            taxonomy_path=taxonomy_path,
        )
        updated_elements, affected_elements, warnings = _apply_score_delta(
            active_elements=active_elements,
            reviewed=reviewed,
            taxonomy=taxonomy,
        )
        ledger = _append_ledger_record(
            ledger_path=ledger_path,
            reviewed=reviewed,
            feedback_target=expected["feedback_target"],
            recorded_at=recorded_at or _current_timestamp(),
        )
        report = _build_feedback_report(
            reviewed_path=reviewed_path,
            result_path=result_path,
            reviewed=reviewed,
            affected_elements=affected_elements,
            warnings=warnings,
        )
        output_path = report_path or result_path.with_name("feedback_report.json")
        _write_output_files(
            (active_elements_path, {"schema_version": "mvp-v1", "elements": updated_elements}),
            (ledger_path, ledger),
            (output_path, report),
        )
        return report
    except GenerationError as error:
        return error.to_dict()
    except OSError as error:
        return _io_error(error).to_dict()


def _prepare_validated_feedback(
    reviewed_path: Path,
    result_path: Path,
    active_elements_path: Path,
    taxonomy_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    expected = _build_review_template(_load_success_result(result_path))
    reviewed = _load_review_bundle(reviewed_path)
    _validate_review_bundle(reviewed_path, reviewed, expected)
    taxonomy = load_evidence_taxonomy(taxonomy_path)
    active_elements = load_elements(active_elements_path, taxonomy_path=taxonomy_path)
    _ensure_selected_targets_exist(reviewed_path, reviewed["feedback_target"], active_elements)
    return reviewed, expected, taxonomy, active_elements


def _load_success_result(path: Path) -> dict[str, Any]:
    payload = _load_json_object(path, "INVALID_FEEDBACK_INPUT", "feedback input root must be an object")
    if "error" in payload:
        raise _feedback_error(path, "result", "INVALID_FEEDBACK_INPUT", "feedback input must be a successful concept result")
    request = payload.get("request_normalized")
    concept = payload.get("composed_concept")
    if not isinstance(request, dict):
        raise _feedback_error(path, "request_normalized", "INVALID_FEEDBACK_INPUT", "feedback input is missing request_normalized")
    if request.get("category") != "dress":
        raise _feedback_error(path, "category", "INVALID_FEEDBACK_INPUT", "feedback input category is unsupported")
    if not isinstance(concept, dict):
        raise _feedback_error(path, "composed_concept", "INVALID_FEEDBACK_INPUT", "feedback input is missing composed_concept")
    _validate_selected_elements(path, concept.get("selected_elements"))
    if not isinstance(concept.get("concept_score"), (int, float)):
        raise _feedback_error(path, "concept_score", "INVALID_FEEDBACK_INPUT", "feedback input concept_score must be numeric")
    return payload


def _validate_selected_elements(path: Path, selected: Any) -> None:
    if not isinstance(selected, dict) or not selected:
        raise _feedback_error(path, "selected_elements", "INVALID_FEEDBACK_INPUT", "feedback input must contain selected active elements")
    for slot, element in selected.items():
        if not isinstance(slot, str):
            raise _feedback_error(path, "selected_elements", "INVALID_FEEDBACK_INPUT", "feedback input slot keys must be strings")
        if not isinstance(element, dict):
            raise _feedback_error(path, "selected_elements", "INVALID_FEEDBACK_INPUT", "feedback input selected elements must be objects")
        for field in ("element_id", "value"):
            if not isinstance(element.get(field), str) or not element[field].strip():
                raise _feedback_error(path, field, "INVALID_FEEDBACK_INPUT", f"feedback input field '{field}' must be a non-empty string")


def _build_review_template(result: dict[str, Any]) -> dict[str, Any]:
    request = dict(result["request_normalized"])
    selected_elements = _selected_element_summaries(result["composed_concept"]["selected_elements"])
    concept_score = round(float(result["composed_concept"]["concept_score"]), 4)
    feedback_target = {
        "request_normalized": request,
        "selected_elements": selected_elements,
        "selected_element_ids": [item["element_id"] for item in selected_elements],
        "concept_score": concept_score,
        "request_fingerprint": _fingerprint(request),
        "concept_fingerprint": _fingerprint(
            {"selected_elements": selected_elements, "concept_score": concept_score}
        ),
    }
    return {
        "schema_version": _REVIEW_SCHEMA_VERSION,
        "category": "dress",
        "feedback_target": feedback_target,
        "decision": "pending",
        "notes": "",
    }


def _selected_element_summaries(selected_elements: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "slot": slot,
            "element_id": str(element["element_id"]),
            "value": str(element["value"]),
        }
        for slot, element in sorted(selected_elements.items())
    ]


def _load_review_bundle(path: Path) -> dict[str, Any]:
    payload = _load_json_object(path, "INVALID_FEEDBACK_REVIEW", "feedback review root must be an object")
    if payload.get("schema_version") != _REVIEW_SCHEMA_VERSION:
        raise _feedback_error(path, "schema_version", "INVALID_FEEDBACK_REVIEW", "feedback review schema_version is unsupported")
    return payload


def _validate_review_bundle(path: Path, reviewed: dict[str, Any], expected: dict[str, Any]) -> None:
    missing = sorted(_REVIEW_ROOT_FIELDS.difference(reviewed.keys()))
    if missing:
        raise GenerationError(
            code="INVALID_FEEDBACK_REVIEW",
            message="feedback review is missing required fields",
            details={"path": str(path), "missing": missing},
        )
    if reviewed.get("category") != expected["category"]:
        raise _feedback_error(path, "category", "INVALID_FEEDBACK_REVIEW", "feedback review category is unsupported")
    if reviewed.get("decision") not in _DECISION_DELTAS:
        raise _feedback_error(path, "decision", "INVALID_FEEDBACK_REVIEW", "feedback review decision must be keep or reject")
    if not isinstance(reviewed.get("notes"), str):
        raise _feedback_error(path, "notes", "INVALID_FEEDBACK_REVIEW", "feedback review notes must be a string")
    _validate_feedback_target(path, reviewed.get("feedback_target"), expected["feedback_target"])


def _validate_feedback_target(path: Path, reviewed_target: Any, expected_target: dict[str, Any]) -> None:
    if not isinstance(reviewed_target, dict):
        raise _feedback_error(path, "feedback_target", "INVALID_FEEDBACK_REVIEW", "feedback review target must be an object")
    missing = sorted(_TARGET_FIELDS.difference(reviewed_target.keys()))
    if missing:
        raise GenerationError(
            code="INVALID_FEEDBACK_REVIEW",
            message="feedback review target is missing required fields",
            details={"path": str(path), "missing": missing},
        )
    for field in sorted(_TARGET_FIELDS):
        if reviewed_target.get(field) != expected_target.get(field):
            raise _feedback_error(path, field, "INVALID_FEEDBACK_REVIEW", f"feedback review field '{field}' must match the generated template")


def _ensure_selected_targets_exist(
    path: Path,
    feedback_target: dict[str, Any],
    active_elements: list[dict[str, Any]],
) -> None:
    active_ids = {
        str(element["element_id"])
        for element in active_elements
        if element.get("status") == "active"
    }
    target_ids = feedback_target["selected_element_ids"]
    missing_ids = sorted(element_id for element_id in target_ids if element_id not in active_ids)
    if missing_ids:
        raise GenerationError(
            code="INVALID_FEEDBACK_REVIEW",
            message="feedback review references missing active element targets",
            details={"path": str(path), "field": "selected_element_ids", "values": missing_ids},
        )


def _apply_score_delta(
    active_elements: list[dict[str, Any]],
    reviewed: dict[str, Any],
    taxonomy: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    delta = _DECISION_DELTAS[reviewed["decision"]]
    target_ids = set(reviewed["feedback_target"]["selected_element_ids"])
    updated_elements: list[dict[str, Any]] = []
    affected_elements: list[dict[str, Any]] = []
    clamped_count = 0
    for element in active_elements:
        updated, affected, clamped = _apply_element_delta(element, target_ids, delta, taxonomy["base_score"])
        updated_elements.append(updated)
        if affected is not None:
            affected_elements.append(affected)
        if clamped:
            clamped_count += 1
    validate_element_records(updated_elements, taxonomy, path=Path("<feedback-apply>"))
    warnings = _feedback_warnings(clamped_count)
    return updated_elements, affected_elements, warnings


def _apply_element_delta(
    element: dict[str, Any],
    target_ids: set[str],
    delta: float,
    score_range: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any] | None, bool]:
    current = dict(element)
    element_id = str(current["element_id"])
    if element_id not in target_ids:
        return current, None, False
    old_score = round(float(current["base_score"]), 4)
    raw_score = round(old_score + delta, 4)
    new_score = _clamp_score(raw_score, score_range)
    current["base_score"] = new_score
    return current, _affected_element(current, old_score, new_score), new_score != raw_score


def _affected_element(element: dict[str, Any], old_score: float, new_score: float) -> dict[str, Any]:
    return {
        "element_id": str(element["element_id"]),
        "slot": str(element["slot"]),
        "value": str(element["value"]),
        "old_base_score": old_score,
        "new_base_score": new_score,
    }


def _clamp_score(score: float, score_range: dict[str, Any]) -> float:
    minimum = float(score_range["min"])
    maximum = float(score_range["max"])
    return round(min(max(score, minimum), maximum), 4)


def _feedback_warnings(clamped_count: int) -> list[str]:
    if not clamped_count:
        return []
    return [f"base_score clamped for {clamped_count} selected elements"]


def _append_ledger_record(
    ledger_path: Path,
    reviewed: dict[str, Any],
    feedback_target: dict[str, Any],
    recorded_at: str,
) -> dict[str, Any]:
    ledger = _load_ledger(ledger_path)
    records = list(ledger["records"])
    records.append(
        {
            "feedback_id": f"feedback-{len(records) + 1:03d}",
            "category": reviewed["category"],
            "decision": reviewed["decision"],
            "element_ids": list(feedback_target["selected_element_ids"]),
            "score_delta": _DECISION_DELTAS[reviewed["decision"]],
            "request_fingerprint": feedback_target["request_fingerprint"],
            "concept_fingerprint": feedback_target["concept_fingerprint"],
            "notes": reviewed["notes"],
            "recorded_at": recorded_at,
        }
    )
    return {"schema_version": _LEDGER_SCHEMA_VERSION, "records": records}


def _load_ledger(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": _LEDGER_SCHEMA_VERSION, "records": []}
    payload = _load_json_object(path, "INVALID_FEEDBACK_LEDGER", "feedback ledger root must be an object")
    if payload.get("schema_version") != _LEDGER_SCHEMA_VERSION:
        raise _feedback_error(path, "schema_version", "INVALID_FEEDBACK_LEDGER", "feedback ledger schema_version is unsupported")
    records = payload.get("records")
    if not isinstance(records, list):
        raise _feedback_error(path, "records", "INVALID_FEEDBACK_LEDGER", "feedback ledger must contain a records array")
    return {"schema_version": _LEDGER_SCHEMA_VERSION, "records": list(records)}


def _build_feedback_report(
    reviewed_path: Path,
    result_path: Path,
    reviewed: dict[str, Any],
    affected_elements: list[dict[str, Any]],
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": _REPORT_SCHEMA_VERSION,
        "category": "dress",
        "source_artifacts": {
            "result_payload": result_path.name,
            "reviewed_feedback": reviewed_path.name,
        },
        "summary": {
            "decision": reviewed["decision"],
            "affected_element_count": len(affected_elements),
            "applied_delta": _DECISION_DELTAS[reviewed["decision"]],
            "clamped_element_count": len(warnings) and _clamped_count_from_warning(warnings[0]) or 0,
        },
        "affected_elements": affected_elements,
        "warnings": warnings,
    }


def _clamped_count_from_warning(warning: str) -> int:
    parts = warning.split()
    return int(parts[3]) if len(parts) >= 4 and parts[3].isdigit() else 0


def _load_json_object(path: Path, code: str, root_message: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise GenerationError(
            code=code,
            message="file must contain valid JSON",
            details={"path": str(path), "line": error.lineno, "column": error.colno},
        ) from error
    if isinstance(payload, dict):
        return payload
    raise GenerationError(code=code, message=root_message, details={"path": str(path)})


def _write_output_files(*outputs: tuple[Path, dict[str, Any]]) -> None:
    rendered = [(path, json.dumps(payload, ensure_ascii=False, indent=2)) for path, payload in outputs]
    temp_paths = _stage_output_files(rendered)
    backups = _read_output_backups(outputs)
    replaced: list[Path] = []
    try:
        for target, temp_path in temp_paths:
            temp_path.replace(target)
            replaced.append(target)
    except OSError as error:
        _restore_output_backups(replaced, backups)
        raise _write_error(error) from error
    finally:
        _cleanup_temp_files(temp_paths)


def _stage_output_files(rendered: list[tuple[Path, str]]) -> list[tuple[Path, Path]]:
    temp_paths: list[tuple[Path, Path]] = []
    try:
        for target, content in rendered:
            temp_path = _temp_output_path(target)
            temp_path.write_text(content, encoding="utf-8")
            temp_paths.append((target, temp_path))
    except OSError as error:
        _cleanup_temp_files(temp_paths)
        raise _write_error(error) from error
    return temp_paths


def _read_output_backups(outputs: tuple[tuple[Path, dict[str, Any]], ...]) -> dict[Path, str | None]:
    backups: dict[Path, str | None] = {}
    for path, _ in outputs:
        backups[path] = path.read_text(encoding="utf-8") if path.exists() else None
    return backups


def _restore_output_backups(targets: list[Path], backups: dict[Path, str | None]) -> None:
    for target in targets:
        original = backups.get(target)
        if original is None:
            if target.exists():
                target.unlink()
            continue
        target.write_text(original, encoding="utf-8")


def _cleanup_temp_files(temp_paths: list[tuple[Path, Path]]) -> None:
    for _, temp_path in temp_paths:
        if temp_path.exists():
            temp_path.unlink()


def _temp_output_path(target: Path) -> Path:
    return target.with_name(f"{target.name}.tmp")


def _fingerprint(payload: Any) -> str:
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _current_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _feedback_error(path: Path, field: str, code: str, message: str) -> GenerationError:
    return GenerationError(code=code, message=message, details={"path": str(path), "field": field})


def _write_error(error: OSError) -> GenerationError:
    return GenerationError(
        code="FEEDBACK_WRITE_FAILED",
        message="failed to write feedback outputs",
        details={"path": str(getattr(error, "filename", ""))},
    )


def _io_error(error: OSError) -> GenerationError:
    return GenerationError(
        code="FEEDBACK_IO_FAILED",
        message="failed to read feedback inputs",
        details={"path": str(getattr(error, "filename", ""))},
    )
