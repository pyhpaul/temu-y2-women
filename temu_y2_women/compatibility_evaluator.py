from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from temu_y2_women.errors import GenerationError
from temu_y2_women.evidence_repository import load_elements
from temu_y2_women.models import CandidateElement

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_RULES_PATH = _PROJECT_ROOT / "data" / "mvp" / "dress" / "compatibility_rules.json"
_DEFAULT_ELEMENTS_PATH = _PROJECT_ROOT / "data" / "mvp" / "dress" / "elements.json"
_DEFAULT_TAXONOMY_PATH = _PROJECT_ROOT / "data" / "mvp" / "dress" / "evidence_taxonomy.json"
_RULES_FIELD = "rules"
_ALLOWED_PAIR = ("pattern", "detail")
_VALID_SEVERITIES = {"weak", "strong"}
_VALID_SCHEMA_VERSIONS = {"mvp-v1", "compatibility-rules-v2"}
_VALID_RULE_STATUSES = {"active", "inactive"}
_SCOPE_TEXT_FIELDS = ("category", "target_market")
_SCOPE_LIST_FIELDS = ("season_tags", "occasion_tags", "price_bands")


@dataclass(slots=True, frozen=True)
class CompatibilityRule:
    left_slot: str
    left_value: str
    right_slot: str
    right_value: str
    severity: str
    penalty: float
    reason: str
    rule_id: str | None = None
    scope: dict[str, Any] | None = None
    evidence_summary: str | None = None
    evidence: dict[str, Any] | None = None
    confidence: float | None = None
    decision_source: str | None = None
    status: str = "active"


@dataclass(slots=True, frozen=True)
class CompatibilityEvaluation:
    hard_conflicts: tuple[str, ...]
    soft_conflicts: tuple[str, ...]
    compatibility_penalty: float
    compatibility_notes: tuple[str, ...]


def evaluate_selection_compatibility(
    selected: dict[str, CandidateElement],
    rules: list[CompatibilityRule] | tuple[CompatibilityRule, ...],
) -> CompatibilityEvaluation:
    if "pattern" not in selected or "detail" not in selected:
        return CompatibilityEvaluation((), (), 0.0, ())

    hard_conflicts: list[str] = []
    soft_conflicts: list[str] = []
    notes: list[str] = []
    penalty = 0.0
    for rule in rules:
        match = _rule_matches(selected, rule)
        if match is None:
            continue
        label = _rule_label(match)
        if rule.severity == "strong":
            hard_conflicts.append(label)
            notes.append(f"style conflict avoided: {label}")
            continue
        soft_conflicts.append(label)
        penalty += rule.penalty
        notes.append(f"style compatibility penalty applied: {label} ({rule.penalty:.2f})")
    return CompatibilityEvaluation(
        tuple(hard_conflicts),
        tuple(soft_conflicts),
        round(penalty, 4),
        tuple(notes),
    )


def load_compatibility_rules(
    path: Path = _DEFAULT_RULES_PATH,
    elements_path: Path = _DEFAULT_ELEMENTS_PATH,
    taxonomy_path: Path = _DEFAULT_TAXONOMY_PATH,
) -> list[CompatibilityRule]:
    payload = _load_rules_payload(path)
    active_values_by_slot = _build_active_values_by_slot(
        load_elements(elements_path, taxonomy_path=taxonomy_path)
    )
    rules = payload[_RULES_FIELD]
    parsed_rules = [
        _parse_rule(path=path, index=index, record=record, active_values_by_slot=active_values_by_slot)
        for index, record in enumerate(rules)
    ]
    return [rule for rule in parsed_rules if rule.status == "active"]


def _load_rules_payload(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message="compatibility rule store contains invalid JSON",
            details={"path": str(path)},
        ) from exc
    if not isinstance(payload, dict):
        raise GenerationError(code="INVALID_EVIDENCE_STORE", message="compatibility rule root must be an object", details={"path": str(path)})
    if _RULES_FIELD not in payload or not isinstance(payload[_RULES_FIELD], list):
        raise GenerationError(code="INVALID_EVIDENCE_STORE", message="compatibility rule store must contain a 'rules' array", details={"path": str(path)})
    _parse_schema_version(path=path, payload=payload)
    return payload


def _parse_schema_version(path: Path, payload: dict[str, Any]) -> str:
    value = payload.get("schema_version")
    if not isinstance(value, str):
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message="compatibility rule store field 'schema_version' must be a string",
            details={"path": str(path), "field": "schema_version"},
        )
    schema_version = value.strip()
    if schema_version in _VALID_SCHEMA_VERSIONS:
        return schema_version
    raise GenerationError(
        code="INVALID_EVIDENCE_STORE",
        message="compatibility rule store field 'schema_version' is unsupported",
        details={"path": str(path), "field": "schema_version", "value": schema_version},
    )


def _build_active_values_by_slot(elements: list[dict[str, Any]]) -> dict[str, set[str]]:
    active_values_by_slot: dict[str, set[str]] = {}
    for element in elements:
        if element.get("status") != "active":
            continue
        slot, value = _canonicalize_slot_value(slot=str(element["slot"]), value=str(element["value"]))
        active_values_by_slot.setdefault(slot, set()).add(value)
    return active_values_by_slot


def _parse_rule(
    path: Path,
    index: int,
    record: Any,
    active_values_by_slot: dict[str, set[str]],
) -> CompatibilityRule:
    _require_fields(path=path, index=index, record=record)
    left_slot, left_value, right_slot, right_value = _parse_rule_pair(record)
    severity = _parse_severity(path=path, index=index, record=record)
    penalty = _parse_penalty(path=path, index=index, record=record, severity=severity)
    reason = _require_text_field(path=path, index=index, record=record, field="reason")
    metadata = _parse_rule_metadata(path=path, index=index, record=record)
    _validate_allowed_pair(path=path, index=index, left_slot=left_slot, right_slot=right_slot)
    _require_active_value(path=path, index=index, field="left_value", slot=left_slot, value=left_value, active_values_by_slot=active_values_by_slot)
    _require_active_value(path=path, index=index, field="right_value", slot=right_slot, value=right_value, active_values_by_slot=active_values_by_slot)
    return CompatibilityRule(
        left_slot=left_slot,
        left_value=left_value,
        right_slot=right_slot,
        right_value=right_value,
        severity=severity,
        penalty=penalty,
        reason=reason,
        **metadata,
    )


def _parse_rule_pair(record: dict[str, Any]) -> tuple[str, str, str, str]:
    left_slot, left_value = _canonicalize_slot_value(
        slot=str(record["left_slot"]),
        value=str(record["left_value"]),
    )
    right_slot, right_value = _canonicalize_slot_value(
        slot=str(record["right_slot"]),
        value=str(record["right_value"]),
    )
    return left_slot, left_value, right_slot, right_value


def _parse_rule_metadata(path: Path, index: int, record: dict[str, Any]) -> dict[str, Any]:
    return {
        "rule_id": _parse_optional_text_field(path=path, index=index, record=record, field="rule_id"),
        "scope": _parse_scope(path=path, index=index, record=record),
        "evidence_summary": _parse_optional_text_field(path=path, index=index, record=record, field="evidence_summary"),
        "evidence": _parse_optional_object_field(path=path, index=index, record=record, field="evidence"),
        "confidence": _parse_confidence(path=path, index=index, record=record),
        "decision_source": _parse_optional_text_field(path=path, index=index, record=record, field="decision_source"),
        "status": _parse_status(path=path, index=index, record=record),
    }


def _validate_allowed_pair(path: Path, index: int, left_slot: str, right_slot: str) -> None:
    if (left_slot, right_slot) == _ALLOWED_PAIR:
        return
    raise GenerationError(
        code="INVALID_EVIDENCE_STORE",
        message="compatibility rules only support pattern -> detail",
        details={"path": str(path), "index": index, "left_slot": left_slot, "right_slot": right_slot},
    )


def _require_fields(path: Path, index: int, record: Any) -> None:
    if not isinstance(record, dict):
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message="compatibility rule record must be an object",
            details={"path": str(path), "index": index},
        )
    required = {"left_slot", "left_value", "right_slot", "right_value", "severity", "penalty", "reason"}
    missing = sorted(field for field in required if field not in record)
    if missing:
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message="compatibility rule is missing required fields",
            details={"path": str(path), "index": index, "missing": missing},
        )


def _require_active_value(
    path: Path,
    index: int,
    field: str,
    slot: str,
    value: str,
    active_values_by_slot: dict[str, set[str]],
) -> None:
    if value in active_values_by_slot.get(slot, set()):
        return
    raise GenerationError(
        code="INVALID_EVIDENCE_STORE",
        message="compatibility rule references unknown active element value",
        details={"path": str(path), "index": index, "field": field, "slot": slot, "value": value},
    )


def _require_text_field(
    path: Path,
    index: int,
    record: dict[str, Any],
    field: str,
    *,
    normalize: bool = False,
) -> str:
    value = record[field]
    if not isinstance(value, str):
        _raise_invalid_field(path=path, index=index, field=field, message="compatibility rule field must be a string")
    return value.strip().casefold() if normalize else value.strip()


def _parse_optional_text_field(
    path: Path,
    index: int,
    record: dict[str, Any],
    field: str,
    *,
    normalize: bool = False,
) -> str | None:
    if field not in record or record[field] is None:
        return None
    return _require_text_field(path=path, index=index, record=record, field=field, normalize=normalize)


def _parse_optional_object_field(
    path: Path,
    index: int,
    record: dict[str, Any],
    field: str,
) -> dict[str, Any] | None:
    value = record.get(field)
    if value is None and field not in record:
        return None
    if not isinstance(value, dict):
        _raise_invalid_field(path=path, index=index, field=field, message="compatibility rule field must be an object")
    return value


def _parse_scope(path: Path, index: int, record: dict[str, Any]) -> dict[str, Any] | None:
    scope = _parse_optional_object_field(path=path, index=index, record=record, field="scope")
    if scope is None:
        return None
    normalized_scope = dict(scope)
    for field in _SCOPE_TEXT_FIELDS:
        if field in normalized_scope:
            normalized_scope[field] = _require_scope_text(path=path, index=index, field=f"scope.{field}", value=normalized_scope[field])
    for field in _SCOPE_LIST_FIELDS:
        if field in normalized_scope:
            normalized_scope[field] = _require_scope_string_list(path=path, index=index, field=f"scope.{field}", value=normalized_scope[field])
    return normalized_scope


def _require_scope_text(path: Path, index: int, field: str, value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    _raise_invalid_field(path=path, index=index, field=field, message="compatibility rule scope field must be a string")


def _require_scope_string_list(path: Path, index: int, field: str, value: Any) -> list[str]:
    if not isinstance(value, list):
        _raise_invalid_field(path=path, index=index, field=field, message="compatibility rule scope field must be an array of strings")
    if all(isinstance(item, str) for item in value):
        return [item.strip() for item in value]
    _raise_invalid_field(path=path, index=index, field=field, message="compatibility rule scope field must be an array of strings")


def _parse_confidence(path: Path, index: int, record: dict[str, Any]) -> float | None:
    if "confidence" not in record or record["confidence"] is None:
        return None
    value = record["confidence"]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _raise_invalid_field(path=path, index=index, field="confidence", message="compatibility rule field 'confidence' must be numeric")
    confidence = float(value)
    if not math.isfinite(confidence) or confidence < 0.0 or confidence > 1.0:
        _raise_invalid_field(path=path, index=index, field="confidence", message="compatibility rule field 'confidence' must be between 0.0 and 1.0")
    return confidence


def _parse_status(path: Path, index: int, record: dict[str, Any]) -> str:
    status = _parse_optional_text_field(path=path, index=index, record=record, field="status", normalize=True)
    if status is None:
        return "active"
    if status in _VALID_RULE_STATUSES:
        return status
    _raise_invalid_field(path=path, index=index, field="status", message="compatibility rule field 'status' must be 'active' or 'inactive'")


def _raise_invalid_field(path: Path, index: int, field: str, message: str) -> None:
    raise GenerationError(
        code="INVALID_EVIDENCE_STORE",
        message=message,
        details={"path": str(path), "index": index, "field": field},
    )


def _parse_penalty(path: Path, index: int, record: dict[str, Any], severity: str) -> float:
    value = record["penalty"]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message="compatibility rule field 'penalty' must be numeric",
            details={"path": str(path), "index": index, "field": "penalty"},
        )
    penalty = float(value)
    if not math.isfinite(penalty):
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message="compatibility rule field 'penalty' must be finite",
            details={"path": str(path), "index": index, "field": "penalty"},
        )
    if penalty < 0.0:
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message="compatibility rule field 'penalty' must be non-negative",
            details={"path": str(path), "index": index, "field": "penalty"},
        )
    if severity == "strong" and penalty != 0.0:
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message="compatibility rule field 'penalty' must be 0.0 for strong rules",
            details={"path": str(path), "index": index, "field": "penalty", "severity": severity},
        )
    return penalty


def _parse_severity(path: Path, index: int, record: dict[str, Any]) -> str:
    severity = _require_text_field(path=path, index=index, record=record, field="severity", normalize=True)
    if severity in _VALID_SEVERITIES:
        return severity
    raise GenerationError(
        code="INVALID_EVIDENCE_STORE",
        message="compatibility rule field 'severity' must be 'weak' or 'strong'",
        details={"path": str(path), "index": index, "field": "severity", "value": severity},
    )


def _canonicalize_slot_value(slot: str, value: str) -> tuple[str, str]:
    return _canonicalize_text(slot), _canonicalize_text(value)


def _canonicalize_text(value: str) -> str:
    return value.strip().casefold()


def _rule_matches(
    selected: dict[str, CandidateElement],
    rule: CompatibilityRule,
) -> tuple[str, str] | None:
    left = selected.get(rule.left_slot)
    right = selected.get(rule.right_slot)
    if left is None or right is None:
        return None
    if _canonicalize_text(left.slot) != rule.left_slot:
        return None
    if _canonicalize_text(right.slot) != rule.right_slot:
        return None
    if _canonicalize_text(left.value) != rule.left_value:
        return None
    if _canonicalize_text(right.value) != rule.right_value:
        return None
    return left.value, right.value


def _rule_label(match: tuple[str, str]) -> str:
    return f"{match[0]} + {match[1]}"
