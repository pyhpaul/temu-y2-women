from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from temu_y2_women.evidence_repository import (
    load_elements,
    load_evidence_taxonomy,
    validate_element_records,
)


_SCHEMA_VERSION = "style-family-visual-feedback-proposal-v1"
_DRY_RUN_SCHEMA_VERSION = "style-family-visual-feedback-dry-run-v1"
_APPLY_REPORT_SCHEMA_VERSION = "style-family-visual-feedback-apply-report-v1"
_COMPACT_ELEMENT_ARRAY_FIELDS = {
    "tags",
    "price_bands",
    "occasion_tags",
    "season_tags",
    "risk_flags",
}


def build_visual_feedback_apply_proposal(
    *,
    dry_run_path: Path,
    minimum_delta: float = 0.04,
    minimum_family_count: int = 2,
) -> dict[str, Any]:
    dry_run = _read_dry_run(dry_run_path)
    family_index = _families_by_element(dry_run)
    candidates = [
        _candidate(change, family_index, minimum_delta, minimum_family_count)
        for change in _element_changes(dry_run)
    ]
    recommended = _recommended(candidates)
    held = _held(candidates)
    return {
        "schema_version": _SCHEMA_VERSION,
        "status": "ready",
        "source_artifacts": {"dry_run_report": str(dry_run_path)},
        "policy": {
            "minimum_delta": round(float(minimum_delta), 4),
            "minimum_family_count": int(minimum_family_count),
        },
        "summary": _summary(candidates, recommended, held),
        "recommended_changes": recommended,
        "held_changes": held,
        "candidates": candidates,
    }


def write_visual_feedback_apply_proposal(report: Mapping[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def apply_visual_feedback_proposal(
    *,
    proposal_path: Path,
    active_elements_path: Path,
    taxonomy_path: Path,
    report_path: Path,
) -> dict[str, Any]:
    proposal = _read_proposal(proposal_path)
    taxonomy = load_evidence_taxonomy(taxonomy_path)
    active_elements = load_elements(active_elements_path, taxonomy_path=taxonomy_path)
    updated_elements, applied_changes = _apply_recommended_changes(
        active_elements,
        _apply_changes(proposal),
    )
    validate_element_records(updated_elements, taxonomy, path=Path("<visual-feedback-proposal-apply>"))
    report = _apply_report(
        proposal_path=proposal_path,
        active_elements_path=active_elements_path,
        taxonomy_path=taxonomy_path,
        proposal=proposal,
        applied_changes=applied_changes,
    )
    _write_json_outputs(
        (active_elements_path, {"schema_version": "mvp-v1", "elements": updated_elements}),
        (report_path, report),
    )
    return report


def _candidate(
    change: Mapping[str, Any],
    family_index: Mapping[str, Sequence[str]],
    minimum_delta: float,
    minimum_family_count: int,
) -> dict[str, Any]:
    element_id = _string_value(change, "element_id")
    families = sorted(family_index.get(element_id, []))
    delta = _number_value(change, "delta")
    recommendation = _recommendation(delta, families, minimum_delta, minimum_family_count)
    original_score = _number_value(change, "original_base_score")
    dry_run_score = _number_value(change, "dry_run_base_score")
    candidate = _candidate_payload(change, families, delta, original_score, dry_run_score, recommendation)
    if recommendation == "apply":
        candidate["recommended_base_score"] = dry_run_score
        candidate["rationale"] = "shared visual feedback signal meets apply threshold"
    else:
        candidate["recommended_base_score"] = original_score
        candidate["hold_reason"] = "below minimum shared-signal threshold"
    return candidate


def _candidate_payload(
    change: Mapping[str, Any],
    families: Sequence[str],
    delta: float,
    original_score: float,
    dry_run_score: float,
    recommendation: str,
) -> dict[str, Any]:
    return {
        "element_id": _string_value(change, "element_id"),
        "slot": _string_value(change, "slot"),
        "value": _string_value(change, "value"),
        "original_base_score": original_score,
        "dry_run_base_score": dry_run_score,
        "delta": delta,
        "family_count": len(families),
        "families": list(families),
        "recommendation": recommendation,
        "direction": "increase" if delta > 0 else "decrease",
    }


def _recommendation(
    delta: float,
    families: Sequence[str],
    minimum_delta: float,
    minimum_family_count: int,
) -> str:
    if abs(delta) >= minimum_delta and len(families) >= minimum_family_count:
        return "apply"
    return "hold"


def _recommended(candidates: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return _sorted_candidates([dict(candidate) for candidate in candidates if candidate.get("recommendation") == "apply"])


def _held(candidates: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return _sorted_candidates([dict(candidate) for candidate in candidates if candidate.get("recommendation") == "hold"])


def _sorted_candidates(candidates: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        candidates,
        key=lambda item: (-abs(float(item["delta"])), -int(item["family_count"]), str(item["element_id"])),
    )


def _summary(
    candidates: Sequence[Mapping[str, Any]],
    recommended: Sequence[Mapping[str, Any]],
    held: Sequence[Mapping[str, Any]],
) -> dict[str, int | float]:
    return {
        "total_candidates": len(candidates),
        "recommended": len(recommended),
        "held": len(held),
        "net_recommended_delta": round(sum(_number_value(item, "delta") for item in recommended), 4),
    }


def _apply_recommended_changes(
    active_elements: Sequence[Mapping[str, Any]],
    changes: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    changes_by_id = _changes_by_id(changes)
    applied: list[dict[str, Any]] = []
    updated: list[dict[str, Any]] = []
    seen: set[str] = set()
    for element in active_elements:
        current = dict(element)
        element_id = _string_value(current, "element_id")
        change = changes_by_id.get(element_id)
        if change is not None:
            _validate_active_match(current, change)
            old_score = _number_value(current, "base_score")
            new_score = _required_number_value(change, "recommended_base_score")
            current["base_score"] = new_score
            applied.append(_applied_change(change, old_score, new_score))
            seen.add(element_id)
        updated.append(current)
    missing = sorted(set(changes_by_id).difference(seen))
    if missing:
        raise ValueError(f"proposal references missing active evidence: {', '.join(missing)}")
    return updated, applied


def _changes_by_id(changes: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for change in changes:
        element_id = _required_string_value(change, "element_id")
        if element_id in result:
            raise ValueError(f"proposal contains duplicate recommended change: {element_id}")
        result[element_id] = change
    return result


def _validate_active_match(element: Mapping[str, Any], change: Mapping[str, Any]) -> None:
    expected = {
        "element_id": _required_string_value(change, "element_id"),
        "slot": _required_string_value(change, "slot"),
        "value": _required_string_value(change, "value"),
        "base_score": _required_number_value(change, "original_base_score"),
    }
    actual = {
        "element_id": _string_value(element, "element_id"),
        "slot": _string_value(element, "slot"),
        "value": _string_value(element, "value"),
        "base_score": _number_value(element, "base_score"),
    }
    if actual != expected:
        raise ValueError("proposal does not match active evidence")


def _applied_change(change: Mapping[str, Any], old_score: float, new_score: float) -> dict[str, Any]:
    return {
        "element_id": _required_string_value(change, "element_id"),
        "slot": _required_string_value(change, "slot"),
        "value": _required_string_value(change, "value"),
        "old_base_score": old_score,
        "new_base_score": new_score,
        "delta": round(new_score - old_score, 4),
        "families": _string_list_value(change, "families"),
    }


def _apply_report(
    *,
    proposal_path: Path,
    active_elements_path: Path,
    taxonomy_path: Path,
    proposal: Mapping[str, Any],
    applied_changes: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": _APPLY_REPORT_SCHEMA_VERSION,
        "status": "applied",
        "source_artifacts": {
            "proposal": str(proposal_path),
            "active_elements": str(active_elements_path),
            "taxonomy": str(taxonomy_path),
        },
        "summary": _apply_summary(proposal, applied_changes),
        "applied_changes": list(applied_changes),
    }


def _apply_summary(
    proposal: Mapping[str, Any],
    applied_changes: Sequence[Mapping[str, Any]],
) -> dict[str, int | float]:
    return {
        "recommended": len(_apply_changes(proposal)),
        "applied": len(applied_changes),
        "held": len(_held_changes(proposal)),
        "net_applied_delta": round(sum(_number_value(change, "delta") for change in applied_changes), 4),
    }


def _families_by_element(dry_run: Mapping[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for case in _cases(dry_run):
        family_id = _string_value(case, "style_family_id")
        for element_id in _affected_element_ids(case):
            result.setdefault(element_id, []).append(family_id)
    return result


def _affected_element_ids(case: Mapping[str, Any]) -> list[str]:
    raw_ids = case.get("affected_element_ids", [])
    if not isinstance(raw_ids, list):
        return []
    return [str(element_id) for element_id in raw_ids if str(element_id)]


def _element_changes(dry_run: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    changes = dry_run.get("element_changes", [])
    if isinstance(changes, list):
        return [change for change in changes if isinstance(change, dict)]
    return []


def _cases(dry_run: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    cases = dry_run.get("cases", [])
    if isinstance(cases, list):
        return [case for case in cases if isinstance(case, dict)]
    return []


def _read_dry_run(path: Path) -> Mapping[str, Any]:
    payload = _read_json_object(path)
    if payload.get("schema_version") != _DRY_RUN_SCHEMA_VERSION:
        raise ValueError("dry-run schema_version is not supported.")
    return payload


def _read_proposal(path: Path) -> Mapping[str, Any]:
    payload = _read_json_object(path)
    if payload.get("schema_version") != _SCHEMA_VERSION:
        raise ValueError("proposal schema_version is not supported.")
    if payload.get("status") != "ready":
        raise ValueError("proposal status is not ready.")
    return payload


def _apply_changes(proposal: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [
        change
        for change in _list_of_objects(proposal, "recommended_changes")
        if change.get("recommendation") == "apply"
    ]


def _held_changes(proposal: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return _list_of_objects(proposal, "held_changes")


def _list_of_objects(payload: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    items = payload.get(key, [])
    if isinstance(items, list):
        return [item for item in items if isinstance(item, dict)]
    return []


def _read_json_object(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def _string_value(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key, "")
    return value if isinstance(value, str) else ""


def _required_string_value(payload: Mapping[str, Any], key: str) -> str:
    value = _string_value(payload, key)
    if not value:
        raise ValueError(f"proposal change field '{key}' must be a non-empty string")
    return value


def _string_list_value(payload: Mapping[str, Any], key: str) -> list[str]:
    value = payload.get(key, [])
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _number_value(payload: Mapping[str, Any], key: str) -> float:
    value = payload.get(key, 0.0)
    return round(float(value), 4) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0


def _required_number_value(payload: Mapping[str, Any], key: str) -> float:
    value = payload.get(key)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return round(float(value), 4)
    raise ValueError(f"proposal change field '{key}' must be numeric")


def _write_json_outputs(*outputs: tuple[Path, Mapping[str, Any]]) -> None:
    staged = []
    try:
        for path, payload in outputs:
            path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = path.with_name(f"{path.name}.tmp")
            temp_path.write_text(_render_json_output(path, payload), encoding="utf-8")
            staged.append((path, temp_path))
        for path, temp_path in staged:
            temp_path.replace(path)
    finally:
        for _, temp_path in staged:
            if temp_path.exists():
                temp_path.unlink()


def _render_json_output(path: Path, payload: Mapping[str, Any]) -> str:
    if path.name == "elements.json" and isinstance(payload.get("elements"), list):
        return _render_elements_store(payload)
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def _render_elements_store(payload: Mapping[str, Any]) -> str:
    lines = ["{", f'  "schema_version": {json.dumps(payload["schema_version"], ensure_ascii=False)},', '  "elements": [']
    elements = payload["elements"]
    for index, element in enumerate(elements):
        lines.extend(_render_element_record(element, index == len(elements) - 1))
    lines.extend(["  ]", "}"])
    return "\n".join(lines) + "\n"


def _render_element_record(element: Mapping[str, Any], is_last: bool) -> list[str]:
    lines = ["    {"]
    items = list(element.items())
    for index, (key, value) in enumerate(items):
        comma = "," if index < len(items) - 1 else ""
        lines.append(f'      "{key}": {_render_element_value(key, value)}{comma}')
    lines.append("    }" + ("" if is_last else ","))
    return lines


def _render_element_value(key: str, value: Any) -> str:
    if key in _COMPACT_ELEMENT_ARRAY_FIELDS and isinstance(value, list):
        return json.dumps(value, ensure_ascii=False, separators=(", ", ": "))
    return json.dumps(value, ensure_ascii=False)
