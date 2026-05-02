from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence


_SCHEMA_VERSION = "style-family-visual-feedback-proposal-v1"
_DRY_RUN_SCHEMA_VERSION = "style-family-visual-feedback-dry-run-v1"


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


def _read_json_object(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def _string_value(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key, "")
    return value if isinstance(value, str) else ""


def _number_value(payload: Mapping[str, Any], key: str) -> float:
    value = payload.get(key, 0.0)
    return round(float(value), 4) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0
