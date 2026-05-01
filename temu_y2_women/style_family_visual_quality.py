from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


_SCHEMA_VERSION = "style-family-visual-quality-review-v1"
_ACCEPTANCE_SCHEMA_VERSION = "style-family-visual-acceptance-v1"
QUALITY_CRITERIA = (
    "family_differentiation",
    "prompt_adherence",
    "garment_fidelity",
    "commercial_realism",
    "artifact_control",
)
_DECISIONS = ("accepted", "needs_revision")


def build_visual_quality_review(
    *,
    acceptance_path: Path,
    decisions: Mapping[str, str],
    scores: Mapping[str, Mapping[str, int]],
    notes: Mapping[str, str] | None = None,
    revision_reasons: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, Any]:
    acceptance = _read_acceptance_report(acceptance_path)
    cases = [
        _case_review(case, decisions, scores, notes or {}, revision_reasons or {})
        for case in _acceptance_cases(acceptance)
    ]
    return {
        "schema_version": _SCHEMA_VERSION,
        "reviewed_at": _current_date(),
        "status": _overall_status(cases),
        "summary": _summary(cases),
        "criteria": list(QUALITY_CRITERIA),
        "acceptance_path": str(acceptance_path),
        "cases": cases,
    }


def write_visual_quality_review(report: Mapping[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def _case_review(
    acceptance_case: Mapping[str, Any],
    decisions: Mapping[str, str],
    scores: Mapping[str, Mapping[str, int]],
    notes: Mapping[str, str],
    revision_reasons: Mapping[str, Sequence[str]],
) -> dict[str, Any]:
    family_id = str(acceptance_case.get("style_family_id", ""))
    family_scores = _validated_scores(family_id, scores)
    return {
        "style_family_id": family_id,
        "decision": _validated_decision(family_id, decisions),
        "scores": family_scores,
        "average_score": _average(family_scores.values()),
        "revision_reasons": _revision_reasons(family_id, revision_reasons),
        "note": notes.get(family_id, ""),
        "acceptance_note": _string_value(acceptance_case, "note"),
        "image_path": _string_value(acceptance_case, "image_path"),
        "prompt_fingerprint": _string_value(acceptance_case, "prompt_fingerprint"),
        "selected_elements": _mapping_value(acceptance_case, "selected_elements"),
    }


def _read_acceptance_report(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Acceptance report must be a JSON object.")
    if payload.get("schema_version") != _ACCEPTANCE_SCHEMA_VERSION:
        raise ValueError("Acceptance report schema_version is not supported.")
    if payload.get("status") != "accepted":
        raise ValueError("Acceptance report status must be accepted.")
    return payload


def _acceptance_cases(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    cases = payload.get("cases", [])
    if isinstance(cases, list):
        return [case for case in cases if isinstance(case, dict)]
    return []


def _validated_decision(family_id: str, decisions: Mapping[str, str]) -> str:
    if family_id not in decisions:
        raise ValueError(f"Missing decision for {family_id}.")
    decision = decisions[family_id]
    if decision not in _DECISIONS:
        raise ValueError(f"Decision for {family_id} must be accepted or needs_revision.")
    return decision


def _validated_scores(
    family_id: str,
    scores: Mapping[str, Mapping[str, int]],
) -> dict[str, int]:
    family_scores = scores.get(family_id, {})
    return {
        criterion: _validated_score(family_id, criterion, family_scores)
        for criterion in QUALITY_CRITERIA
    }


def _validated_score(
    family_id: str,
    criterion: str,
    family_scores: Mapping[str, int],
) -> int:
    if criterion not in family_scores:
        raise ValueError(f"Missing score for {family_id}:{criterion}.")
    score = family_scores[criterion]
    if not isinstance(score, int) or isinstance(score, bool) or score < 1 or score > 5:
        raise ValueError(f"Score for {family_id}:{criterion} must be 1-5.")
    return score


def _summary(cases: Sequence[Mapping[str, Any]]) -> dict[str, int | float]:
    accepted = sum(1 for case in cases if case.get("decision") == "accepted")
    needs_revision = sum(1 for case in cases if case.get("decision") == "needs_revision")
    scores = [score for case in cases for score in _case_scores(case)]
    return {
        "total": len(cases),
        "accepted": accepted,
        "needs_revision": needs_revision,
        "average_score": _average(scores),
    }


def _case_scores(case: Mapping[str, Any]) -> list[int]:
    scores = case.get("scores", {})
    if not isinstance(scores, dict):
        return []
    return [score for score in scores.values() if isinstance(score, int)]


def _overall_status(cases: Sequence[Mapping[str, Any]]) -> str:
    if any(case.get("decision") == "needs_revision" for case in cases):
        return "needs_revision"
    return "accepted"


def _revision_reasons(
    family_id: str,
    revision_reasons: Mapping[str, Sequence[str]],
) -> list[str]:
    raw_reasons = revision_reasons.get(family_id, [])
    if isinstance(raw_reasons, str):
        return [raw_reasons] if raw_reasons else []
    return [str(reason) for reason in raw_reasons if str(reason)]


def _average(values: Iterable[int]) -> float:
    value_list = list(values)
    if not value_list:
        return 0.0
    return round(sum(value_list) / len(value_list), 2)


def _string_value(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key, "")
    return value if isinstance(value, str) else ""


def _mapping_value(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key, {})
    return value if isinstance(value, dict) else {}


def _current_date() -> str:
    return datetime.now(timezone.utc).date().isoformat()
