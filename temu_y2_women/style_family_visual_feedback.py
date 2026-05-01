from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from temu_y2_women.feedback_loop import prepare_dress_concept_feedback


_SCHEMA_VERSION = "style-family-visual-feedback-batch-v1"
_QUALITY_SCHEMA_VERSION = "style-family-visual-quality-review-v1"
_BATCH_FILENAME = "visual_feedback_batch.json"


def prepare_visual_feedback_reviews(
    *,
    manifest_path: Path,
    quality_review_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    manifest = _read_json_object(manifest_path)
    quality_review = _read_quality_review(quality_review_path)
    manifest_cases = _manifest_cases_by_family(manifest)
    artifacts = [
        _feedback_artifact(manifest_path, manifest_cases, quality_case, output_dir)
        for quality_case in _quality_cases(quality_review)
    ]
    output_dir.mkdir(parents=True, exist_ok=True)
    for artifact in artifacts:
        _write_json(artifact["path"], artifact["review"])
    report = _batch_report(manifest_path, quality_review_path, artifacts)
    _write_json(output_dir / _BATCH_FILENAME, report)
    return report


def _feedback_artifact(
    manifest_path: Path,
    manifest_cases: Mapping[str, Mapping[str, Any]],
    quality_case: Mapping[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    family_id = _family_id(quality_case)
    manifest_case = _manifest_case(family_id, manifest_cases)
    concept_path = _existing_path(manifest_path, _string_value(manifest_case, "concept_path"))
    review = _review_payload(family_id, concept_path, quality_case)
    review_path = output_dir / f"{family_id}-feedback_review.json"
    return {
        "path": review_path,
        "review": review,
        "case": _case_report(family_id, quality_case, concept_path, review_path),
    }


def _review_payload(
    family_id: str,
    concept_path: Path,
    quality_case: Mapping[str, Any],
) -> dict[str, Any]:
    review = prepare_dress_concept_feedback(concept_path)
    if "error" in review:
        code = review.get("error", {}).get("code", "unknown")
        raise ValueError(f"Feedback template failed for {family_id}: {code}")
    review["decision"] = _feedback_decision(_string_value(quality_case, "decision"))
    review["notes"] = _feedback_notes(family_id, quality_case)
    return review


def _case_report(
    family_id: str,
    quality_case: Mapping[str, Any],
    concept_path: Path,
    review_path: Path,
) -> dict[str, Any]:
    quality_decision = _string_value(quality_case, "decision")
    return {
        "style_family_id": family_id,
        "quality_decision": quality_decision,
        "feedback_decision": _feedback_decision(quality_decision),
        "quality_average_score": _number_value(quality_case, "average_score"),
        "concept_path": str(concept_path),
        "feedback_review_path": str(review_path),
        "status": "written",
    }


def _batch_report(
    manifest_path: Path,
    quality_review_path: Path,
    artifacts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    cases = [artifact["case"] for artifact in artifacts]
    return {
        "schema_version": _SCHEMA_VERSION,
        "status": "ready",
        "source_artifacts": {
            "manifest": str(manifest_path),
            "visual_quality_review": str(quality_review_path),
        },
        "summary": _summary(cases),
        "cases": cases,
    }


def _summary(cases: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    keep = sum(1 for case in cases if case.get("feedback_decision") == "keep")
    reject = sum(1 for case in cases if case.get("feedback_decision") == "reject")
    written = sum(1 for case in cases if case.get("status") == "written")
    return {"total": len(cases), "keep": keep, "reject": reject, "written": written}


def _feedback_notes(family_id: str, quality_case: Mapping[str, Any]) -> str:
    parts = [
        f"style_family={family_id}",
        f"quality_decision={_string_value(quality_case, 'decision')}",
        f"average_score={_number_value(quality_case, 'average_score')}",
        f"scores={_score_summary(quality_case.get('scores', {}))}",
    ]
    note = _string_value(quality_case, "note")
    if note:
        parts.append(f"note={note}")
    reasons = _revision_reasons(quality_case.get("revision_reasons", []))
    if reasons:
        parts.append(f"revision_reasons={' | '.join(reasons)}")
    return "; ".join(parts)


def _score_summary(scores: Any) -> str:
    if not isinstance(scores, dict):
        return ""
    return ",".join(f"{key}:{scores[key]}" for key in sorted(scores))


def _revision_reasons(raw_reasons: Any) -> list[str]:
    if isinstance(raw_reasons, str):
        return [raw_reasons] if raw_reasons else []
    if isinstance(raw_reasons, list):
        return [str(reason) for reason in raw_reasons if str(reason)]
    return []


def _feedback_decision(quality_decision: str) -> str:
    if quality_decision == "accepted":
        return "keep"
    if quality_decision == "needs_revision":
        return "reject"
    raise ValueError(f"Unsupported visual quality decision: {quality_decision}")


def _read_quality_review(path: Path) -> Mapping[str, Any]:
    payload = _read_json_object(path)
    if payload.get("schema_version") != _QUALITY_SCHEMA_VERSION:
        raise ValueError("Visual quality review schema_version is not supported.")
    return payload


def _manifest_cases_by_family(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for case in _cases(payload):
        family_id = _family_id(case)
        if family_id:
            result[family_id] = case
    return result


def _quality_cases(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return _cases(payload)


def _cases(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    cases = payload.get("cases", [])
    if isinstance(cases, list):
        return [case for case in cases if isinstance(case, dict)]
    return []


def _manifest_case(
    family_id: str,
    manifest_cases: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any]:
    if family_id not in manifest_cases:
        raise ValueError(f"Missing manifest case for {family_id}.")
    return manifest_cases[family_id]


def _existing_path(manifest_path: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    if candidate.exists() or candidate.is_absolute():
        return candidate
    return manifest_path.parent / candidate


def _family_id(payload: Mapping[str, Any]) -> str:
    return _string_value(payload, "style_family_id")


def _string_value(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key, "")
    return value if isinstance(value, str) else ""


def _number_value(payload: Mapping[str, Any], key: str) -> float:
    value = payload.get(key, 0.0)
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0


def _read_json_object(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
