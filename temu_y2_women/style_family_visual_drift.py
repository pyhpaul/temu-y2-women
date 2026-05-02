from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from temu_y2_women.evidence_paths import EvidencePaths
from temu_y2_women.orchestrator import generate_dress_concept


_SCHEMA_VERSION = "style-family-visual-drift-check-v1"
_MANIFEST_SCHEMA_VERSION = "style-family-anchor-validation-v1"


def build_style_family_visual_drift_check(
    *,
    manifest_path: Path,
    evidence_paths: EvidencePaths | None = None,
) -> dict[str, Any]:
    manifest = _read_manifest(manifest_path)
    cases = [
        _case_report(manifest_path, case, evidence_paths)
        for case in _manifest_cases(manifest)
    ]
    return {
        "schema_version": _SCHEMA_VERSION,
        "status": _overall_status(cases),
        "manifest_path": str(manifest_path),
        "summary": _summary(cases),
        "cases": cases,
    }


def write_style_family_visual_drift_check(report: Mapping[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def _case_report(
    manifest_path: Path,
    manifest_case: Mapping[str, Any],
    evidence_paths: EvidencePaths | None,
) -> dict[str, Any]:
    request_path = _resolved_path(manifest_path, _string_value(manifest_case, "request_path"))
    result = generate_dress_concept(_read_json_object(request_path), evidence_paths=evidence_paths)
    if "error" in result:
        return _error_case(manifest_case, request_path, result)
    actual_family = _actual_family_id(result)
    expected_elements = _expected_selected_elements(manifest_case)
    actual_elements = _actual_selected_elements(result)
    changed_slots = _changed_slots(expected_elements, actual_elements)
    family_id = _string_value(manifest_case, "style_family_id")
    passed = actual_family == family_id and not changed_slots
    return {
        "style_family_id": family_id,
        "request_path": str(request_path),
        "status": "passed" if passed else "failed",
        "expected_style_family_id": family_id,
        "actual_style_family_id": actual_family,
        "family_match": actual_family == family_id,
        "expected_selected_elements": expected_elements,
        "actual_selected_elements": actual_elements,
        "changed_slots": changed_slots,
        "concept_score": _concept_score(result),
        "hero_front_prompt_fingerprint": _hero_front_prompt_fingerprint(result),
    }


def _error_case(
    manifest_case: Mapping[str, Any],
    request_path: Path,
    result: Mapping[str, Any],
) -> dict[str, Any]:
    error = result.get("error", {})
    return {
        "style_family_id": _string_value(manifest_case, "style_family_id"),
        "request_path": str(request_path),
        "status": "error",
        "error": error if isinstance(error, dict) else {},
        "expected_selected_elements": _expected_selected_elements(manifest_case),
        "actual_selected_elements": {},
        "changed_slots": [],
    }


def _changed_slots(
    expected: Mapping[str, str],
    actual: Mapping[str, str],
) -> list[dict[str, str]]:
    return [
        {"slot": slot, "expected": expected_value, "actual": actual.get(slot, "")}
        for slot, expected_value in sorted(expected.items())
        if actual.get(slot, "") != expected_value
    ]


def _summary(cases: list[Mapping[str, Any]]) -> dict[str, int]:
    return {
        "total": len(cases),
        "passed": sum(1 for case in cases if case.get("status") == "passed"),
        "failed": sum(1 for case in cases if case.get("status") == "failed"),
        "errors": sum(1 for case in cases if case.get("status") == "error"),
        "family_mismatches": sum(1 for case in cases if case.get("family_match") is False),
        "selected_element_drifts": sum(1 for case in cases if case.get("changed_slots")),
    }


def _overall_status(cases: list[Mapping[str, Any]]) -> str:
    if any(case.get("status") != "passed" for case in cases):
        return "failed"
    return "passed"


def _read_manifest(path: Path) -> Mapping[str, Any]:
    payload = _read_json_object(path)
    if payload.get("schema_version") != _MANIFEST_SCHEMA_VERSION:
        raise ValueError("style-family manifest schema_version is not supported.")
    return payload


def _manifest_cases(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    cases = payload.get("cases", [])
    if isinstance(cases, list):
        return [case for case in cases if isinstance(case, dict)]
    return []


def _expected_selected_elements(case: Mapping[str, Any]) -> dict[str, str]:
    selected = case.get("selected_elements", {})
    if not isinstance(selected, dict):
        return {}
    return {
        str(slot): str(value)
        for slot, value in selected.items()
        if isinstance(slot, str) and isinstance(value, str)
    }


def _actual_selected_elements(result: Mapping[str, Any]) -> dict[str, str]:
    concept = result.get("composed_concept", {})
    selected = concept.get("selected_elements", {}) if isinstance(concept, dict) else {}
    if not isinstance(selected, dict):
        return {}
    return {
        str(slot): _string_value(element, "value")
        for slot, element in selected.items()
        if isinstance(slot, str) and isinstance(element, dict)
    }


def _actual_family_id(result: Mapping[str, Any]) -> str:
    selected = result.get("selected_style_family", {})
    return _string_value(selected, "style_family_id") if isinstance(selected, dict) else ""


def _concept_score(result: Mapping[str, Any]) -> float:
    concept = result.get("composed_concept", {})
    value = concept.get("concept_score") if isinstance(concept, dict) else 0.0
    return round(float(value), 4) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0


def _hero_front_prompt_fingerprint(result: Mapping[str, Any]) -> str:
    prompt = _hero_front_prompt(result)
    if not prompt:
        return ""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def _hero_front_prompt(result: Mapping[str, Any]) -> str:
    bundle = result.get("prompt_bundle", {})
    jobs = bundle.get("render_jobs", []) if isinstance(bundle, dict) else []
    if not isinstance(jobs, list):
        return ""
    for job in jobs:
        if isinstance(job, dict) and job.get("prompt_id") == "hero_front":
            return _string_value(job, "prompt")
    return ""


def _resolved_path(anchor_path: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute() or candidate.exists():
        return candidate
    return anchor_path.parent / candidate


def _read_json_object(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def _string_value(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key, "")
    return value if isinstance(value, str) else ""
