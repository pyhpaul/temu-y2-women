from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from temu_y2_women.errors import GenerationError
from temu_y2_women.evidence_repository import load_elements

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_RULES_PATH = _PROJECT_ROOT / "data/mvp/dress/compatibility_rules.json"
_DEFAULT_ELEMENTS_PATH = _PROJECT_ROOT / "data/mvp/dress/elements.json"
_DEFAULT_TAXONOMY_PATH = _PROJECT_ROOT / "data/mvp/dress/evidence_taxonomy.json"
_ALLOWED_PAIR = ("pattern", "detail")
_REVIEW_ROOT_FIELDS = {"schema_version", "category", "rules"}
_DRAFT_RULE_FIELDS = {
    "draft_rule_id",
    "category",
    "left_slot",
    "left_value",
    "right_slot",
    "right_value",
    "suggested_severity",
    "suggested_penalty",
    "reason",
    "scope",
    "evidence_summary",
    "evidence",
    "confidence",
    "decision_source",
    "status",
}
_ACTIVE_RULE_FIELDS = {
    "rule_id",
    "category",
    "left_slot",
    "left_value",
    "right_slot",
    "right_value",
    "severity",
    "penalty",
    "reason",
    "scope",
    "evidence_summary",
    "evidence",
    "confidence",
    "decision_source",
    "status",
}


def prepare_compatibility_rule_review(
    draft_rules_path: Path,
    active_rules_path: Path = _DEFAULT_RULES_PATH,
    elements_path: Path = _DEFAULT_ELEMENTS_PATH,
    taxonomy_path: Path = _DEFAULT_TAXONOMY_PATH,
) -> dict[str, Any]:
    try:
        context = _load_promotion_context(draft_rules_path, active_rules_path, elements_path, taxonomy_path)
        return _build_review_template(context["draft_rules"], context["active_rules"])
    except GenerationError as error:
        return error.to_dict()
    except OSError as error:
        return _io_error(error).to_dict()


def validate_reviewed_compatibility_rule_promotion(
    reviewed_path: Path,
    draft_rules_path: Path,
    active_rules_path: Path = _DEFAULT_RULES_PATH,
    elements_path: Path = _DEFAULT_ELEMENTS_PATH,
    taxonomy_path: Path = _DEFAULT_TAXONOMY_PATH,
) -> dict[str, Any]:
    try:
        reviewed, _ = _prepare_validated_promotion(
            reviewed_path,
            draft_rules_path,
            active_rules_path,
            elements_path,
            taxonomy_path,
        )
        return reviewed
    except GenerationError as error:
        return error.to_dict()
    except OSError as error:
        return _io_error(error).to_dict()


def apply_reviewed_compatibility_rule_promotion(
    reviewed_path: Path,
    draft_rules_path: Path,
    active_rules_path: Path,
    report_path: Path,
    elements_path: Path = _DEFAULT_ELEMENTS_PATH,
    taxonomy_path: Path = _DEFAULT_TAXONOMY_PATH,
) -> dict[str, Any]:
    try:
        reviewed, post_rules = _prepare_validated_promotion(
            reviewed_path,
            draft_rules_path,
            active_rules_path,
            elements_path,
            taxonomy_path,
        )
        report = _build_promotion_report(reviewed, draft_rules_path, reviewed_path)
        _write_output_files(
            (active_rules_path, {"schema_version": "compatibility-rules-v2", "rules": post_rules}),
            (report_path, report),
        )
        return report
    except GenerationError as error:
        return error.to_dict()
    except OSError as error:
        return _io_error(error).to_dict()


def _load_promotion_context(
    draft_rules_path: Path,
    active_rules_path: Path,
    elements_path: Path,
    taxonomy_path: Path,
) -> dict[str, Any]:
    active_values_by_slot = _build_active_values_by_slot(load_elements(elements_path, taxonomy_path=taxonomy_path))
    return {
        "active_values_by_slot": active_values_by_slot,
        "draft_rules": _load_draft_rules(draft_rules_path, active_values_by_slot),
        "active_rules": _load_active_rules(active_rules_path, active_values_by_slot),
    }


def _prepare_validated_promotion(
    reviewed_path: Path,
    draft_rules_path: Path,
    active_rules_path: Path,
    elements_path: Path,
    taxonomy_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    context = _load_promotion_context(draft_rules_path, active_rules_path, elements_path, taxonomy_path)
    reviewed = _load_review_bundle(reviewed_path)
    expected = _build_review_template(context["draft_rules"], context["active_rules"])
    _validate_review_bundle(reviewed_path, reviewed, expected, context["active_values_by_slot"])
    return reviewed, _build_post_promotion_rules(context["active_rules"], reviewed["rules"])


def _load_draft_rules(path: Path, active_values_by_slot: dict[str, set[str]]) -> list[dict[str, Any]]:
    payload = _load_json_object(path, "INVALID_PROMOTION_INPUT", "draft compatibility rule root must be an object")
    if payload.get("schema_version") != "draft-conflict-rules-v1":
        raise _promotion_error(path, "schema_version", "INVALID_PROMOTION_INPUT", "draft compatibility rule schema_version is unsupported")
    if payload.get("category") != "dress":
        raise _promotion_error(path, "category", "INVALID_PROMOTION_INPUT", "draft compatibility rule category is unsupported")
    rules = _require_list_field(path, payload, "rules", "INVALID_PROMOTION_INPUT")
    seen_ids: set[str] = set()
    for index, rule in enumerate(rules):
        _validate_draft_rule(path, index, rule, active_values_by_slot, seen_ids)
    return [dict(rule) for rule in rules]


def _load_active_rules(path: Path, active_values_by_slot: dict[str, set[str]]) -> list[dict[str, Any]]:
    payload = _load_json_object(path, "INVALID_EVIDENCE_STORE", "compatibility rule root must be an object")
    schema_version = payload.get("schema_version")
    if schema_version not in {"mvp-v1", "compatibility-rules-v2"}:
        raise _promotion_error(path, "schema_version", "INVALID_EVIDENCE_STORE", "compatibility rule schema_version is unsupported")
    rules = _require_list_field(path, payload, "rules", "INVALID_EVIDENCE_STORE")
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, rule in enumerate(rules):
        normalized_rule = _normalize_active_rule(rule)
        _validate_active_rule(path, index, normalized_rule, active_values_by_slot, seen_ids, "INVALID_EVIDENCE_STORE")
        normalized.append(normalized_rule)
    return normalized


def _load_review_bundle(path: Path) -> dict[str, Any]:
    payload = _load_json_object(path, "INVALID_PROMOTION_REVIEW", "compatibility rule review root must be an object")
    if payload.get("schema_version") != "compatibility-rule-review-v1":
        raise _promotion_error(path, "schema_version", "INVALID_PROMOTION_REVIEW", "compatibility rule review schema_version is unsupported")
    return payload


def _build_review_template(
    draft_rules: list[dict[str, Any]],
    active_rules: list[dict[str, Any]],
) -> dict[str, Any]:
    active_by_identity = {_canonical_identity(rule): rule for rule in active_rules if rule.get("status") == "active"}
    rules = [_build_review_entry(rule, active_by_identity.get(_canonical_identity(rule))) for rule in draft_rules]
    return {"schema_version": "compatibility-rule-review-v1", "category": "dress", "rules": sorted(rules, key=lambda item: str(item["draft_rule_id"]))}


def _build_review_entry(draft_rule: dict[str, Any], matched: dict[str, Any] | None) -> dict[str, Any]:
    proposed_rule = _draft_rule_to_active_rule(draft_rule, matched["rule_id"] if matched else None)
    return {
        "draft_rule_id": draft_rule["draft_rule_id"],
        "merge_action": "update" if matched else "create",
        "matched_active_rule_id": matched["rule_id"] if matched else None,
        "canonical_identity": _identity_payload(draft_rule),
        "merge_rationale": _build_merge_rationale(proposed_rule["rule_id"], matched["rule_id"] if matched else None),
        "source_feedback_ids": list(proposed_rule["evidence"]["source_feedback_ids"]),
        "decision": "pending",
        "proposed_rule": proposed_rule,
    }


def _validate_review_bundle(
    path: Path,
    reviewed: dict[str, Any],
    expected: dict[str, Any],
    active_values_by_slot: dict[str, set[str]],
) -> None:
    missing = sorted(_REVIEW_ROOT_FIELDS.difference(reviewed.keys()))
    if missing:
        raise GenerationError(code="INVALID_PROMOTION_REVIEW", message="compatibility rule review is missing required fields", details={"path": str(path), "missing": missing})
    if reviewed.get("category") != "dress":
        raise _promotion_error(path, "category", "INVALID_PROMOTION_REVIEW", "compatibility rule review category is unsupported")
    _validate_review_records(path, reviewed.get("rules"), expected["rules"], active_values_by_slot)


def _validate_review_records(
    path: Path,
    reviewed_records: Any,
    expected_records: list[dict[str, Any]],
    active_values_by_slot: dict[str, set[str]],
) -> None:
    if not isinstance(reviewed_records, list):
        raise _promotion_error(path, "rules", "INVALID_PROMOTION_REVIEW", "compatibility rule review field 'rules' must be a list")
    expected_by_id = {str(record["draft_rule_id"]): record for record in expected_records}
    seen_ids: set[str] = set()
    for index, reviewed_record in enumerate(reviewed_records):
        expected = _match_expected_review_record(path, index, reviewed_record, expected_by_id)
        _validate_review_record(path, index, reviewed_record, expected, active_values_by_slot, seen_ids)
    if seen_ids != set(expected_by_id):
        raise _promotion_error(path, "rules", "INVALID_PROMOTION_REVIEW", "compatibility rule review field 'rules' does not match staged draft count")


def _match_expected_review_record(
    path: Path,
    index: int,
    reviewed_record: Any,
    expected_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if not isinstance(reviewed_record, dict) or not isinstance(reviewed_record.get("draft_rule_id"), str):
        raise _promotion_error(path, "draft_rule_id", "INVALID_PROMOTION_REVIEW", "compatibility rule review record is missing a stable source identifier", index)
    expected = expected_by_id.get(str(reviewed_record["draft_rule_id"]))
    if expected is not None:
        return expected
    raise GenerationError(code="INVALID_PROMOTION_REVIEW", message="compatibility rule review references an unknown staged draft", details={"path": str(path), "index": index, "field": "draft_rule_id", "value": reviewed_record["draft_rule_id"]})


def _validate_review_record(
    path: Path,
    index: int,
    reviewed_record: dict[str, Any],
    expected: dict[str, Any],
    active_values_by_slot: dict[str, set[str]],
    seen_ids: set[str],
) -> None:
    _validate_review_record_shape(path, index, reviewed_record, seen_ids)
    _validate_review_record_details(path, index, reviewed_record, expected)
    if reviewed_record["decision"] != "accept":
        return
    _validate_curated_rule(path, index, reviewed_record["proposed_rule"], expected["proposed_rule"], active_values_by_slot)


def _validate_review_record_shape(
    path: Path,
    index: int,
    reviewed_record: dict[str, Any],
    seen_ids: set[str],
) -> None:
    required = {"draft_rule_id", "merge_action", "matched_active_rule_id", "canonical_identity", "merge_rationale", "source_feedback_ids", "decision", "proposed_rule"}
    missing = sorted(required.difference(reviewed_record.keys()))
    if missing:
        raise GenerationError(code="INVALID_PROMOTION_REVIEW", message="compatibility rule review record is missing required fields", details={"path": str(path), "index": index, "missing": missing})
    draft_rule_id = str(reviewed_record["draft_rule_id"])
    if draft_rule_id in seen_ids:
        raise _promotion_error(path, "draft_rule_id", "INVALID_PROMOTION_REVIEW", "compatibility rule review field 'draft_rule_id' must be unique", index)
    seen_ids.add(draft_rule_id)
    _require_object_value(path, index, reviewed_record, "canonical_identity", "INVALID_PROMOTION_REVIEW")
    _require_object_value(path, index, reviewed_record, "merge_rationale", "INVALID_PROMOTION_REVIEW")
    _require_string_list_value(path, index, reviewed_record, "source_feedback_ids", "INVALID_PROMOTION_REVIEW")
    if reviewed_record["decision"] not in {"accept", "reject"}:
        raise _promotion_error(path, "decision", "INVALID_PROMOTION_REVIEW", "compatibility rule review decision must be 'accept' or 'reject'", index)
    proposed_rule = reviewed_record.get("proposed_rule")
    if reviewed_record["decision"] == "accept" and not isinstance(proposed_rule, dict):
        raise _promotion_error(path, "proposed_rule", "INVALID_PROMOTION_REVIEW", "compatibility rule curated record must be an object", index)
    if reviewed_record["decision"] == "reject" and proposed_rule is not None and not isinstance(proposed_rule, dict):
        raise _promotion_error(path, "proposed_rule", "INVALID_PROMOTION_REVIEW", "compatibility rule rejected payload must be null or an object", index)


def _validate_review_record_details(
    path: Path,
    index: int,
    reviewed_record: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    for field in ("merge_action", "matched_active_rule_id", "canonical_identity", "merge_rationale", "source_feedback_ids"):
        if reviewed_record[field] != expected[field]:
            raise GenerationError(code="INVALID_PROMOTION_REVIEW", message=f"compatibility rule review field '{field}' must match the staged template", details={"path": str(path), "index": index, "field": field})


def _validate_curated_rule(
    path: Path,
    index: int,
    proposed_rule: dict[str, Any],
    expected_rule: dict[str, Any],
    active_values_by_slot: dict[str, set[str]],
) -> None:
    for field in ("rule_id", "category", "left_slot", "left_value", "right_slot", "right_value", "status"):
        if proposed_rule.get(field) != expected_rule.get(field):
            raise GenerationError(code="INVALID_PROMOTION_REVIEW", message=f"compatibility rule review field '{field}' must preserve staged identity", details={"path": str(path), "index": index, "field": field})
    _validate_active_rule(path, index, proposed_rule, active_values_by_slot, None, "INVALID_PROMOTION_REVIEW")


def _build_post_promotion_rules(
    active_rules: list[dict[str, Any]],
    reviewed_rules: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    snapshot = [dict(rule) for rule in active_rules]
    identity_to_index = {_canonical_identity(rule): index for index, rule in enumerate(snapshot) if rule.get("status") == "active"}
    for record in reviewed_rules:
        if record["decision"] != "accept":
            continue
        proposed_rule = dict(record["proposed_rule"])
        identity = _canonical_identity(proposed_rule)
        if record["merge_action"] == "update" and identity in identity_to_index:
            snapshot[identity_to_index[identity]] = proposed_rule
            continue
        snapshot.append(proposed_rule)
    return sorted(snapshot, key=lambda item: str(item["rule_id"]))


def _build_promotion_report(
    reviewed: dict[str, Any],
    draft_rules_path: Path,
    reviewed_path: Path,
) -> dict[str, Any]:
    return {
        "schema_version": "compatibility-rule-promotion-report-v1",
        "category": "dress",
        "source_artifacts": {"draft_rules": draft_rules_path.name, "reviewed_decisions": reviewed_path.name},
        "summary": _build_report_summary(reviewed["rules"]),
        "rules": _build_report_items(reviewed["rules"]),
        "warnings": [],
    }


def _build_report_summary(records: list[dict[str, Any]]) -> dict[str, int]:
    accepted = sum(1 for record in records if record["decision"] == "accept")
    rejected = sum(1 for record in records if record["decision"] == "reject")
    created = sum(1 for record in records if record["decision"] == "accept" and record["merge_action"] == "create")
    updated = sum(1 for record in records if record["decision"] == "accept" and record["merge_action"] == "update")
    return {"accepted": accepted, "rejected": rejected, "created": created, "updated": updated}


def _build_report_items(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items = []
    for record in records:
        proposed = record.get("proposed_rule")
        items.append(
            {
                "draft_rule_id": record["draft_rule_id"],
                "decision": record["decision"],
                "merge_action": record["merge_action"],
                "rule_id": proposed.get("rule_id") if isinstance(proposed, dict) and record["decision"] == "accept" else None,
                "source_feedback_ids": list(record["source_feedback_ids"]),
            }
        )
    return items


def _normalize_active_rule(record: Any) -> dict[str, Any]:
    base = dict(record) if isinstance(record, dict) else {"_invalid_record": record}
    if "rule_id" not in base and {"left_slot", "left_value", "right_slot", "right_value"} <= set(base):
        base["rule_id"] = _rule_id_from_identity(base)
        base.setdefault("category", "dress")
        base.setdefault("scope", {"category": "dress", "target_market": "US", "season_tags": [], "occasion_tags": [], "price_bands": []})
        base.setdefault("evidence_summary", base.get("reason", ""))
        base.setdefault("evidence", {"source_feedback_ids": []})
        base.setdefault("confidence", 1.0)
        base.setdefault("decision_source", "legacy_curated")
        base.setdefault("status", "active")
    return base


def _draft_rule_to_active_rule(draft_rule: dict[str, Any], matched_rule_id: str | None) -> dict[str, Any]:
    return {
        "rule_id": matched_rule_id or _rule_id_from_identity(draft_rule),
        "category": draft_rule["category"],
        "left_slot": draft_rule["left_slot"],
        "left_value": draft_rule["left_value"],
        "right_slot": draft_rule["right_slot"],
        "right_value": draft_rule["right_value"],
        "severity": draft_rule["suggested_severity"],
        "penalty": draft_rule["suggested_penalty"],
        "reason": draft_rule["reason"],
        "scope": dict(draft_rule["scope"]),
        "evidence_summary": draft_rule["evidence_summary"],
        "evidence": dict(draft_rule["evidence"]),
        "confidence": draft_rule["confidence"],
        "decision_source": draft_rule["decision_source"],
        "status": "active",
    }


def _validate_draft_rule(
    path: Path,
    index: int,
    rule: Any,
    active_values_by_slot: dict[str, set[str]],
    seen_ids: set[str],
) -> None:
    _require_record_fields(path, index, rule, _DRAFT_RULE_FIELDS, "INVALID_PROMOTION_INPUT", "draft compatibility rule")
    _require_string_value(path, index, rule, "draft_rule_id", "INVALID_PROMOTION_INPUT", seen_ids)
    _require_string_value(path, index, rule, "category", "INVALID_PROMOTION_INPUT")
    _require_string_value(path, index, rule, "reason", "INVALID_PROMOTION_INPUT")
    _require_string_value(path, index, rule, "evidence_summary", "INVALID_PROMOTION_INPUT")
    _require_string_value(path, index, rule, "decision_source", "INVALID_PROMOTION_INPUT")
    _validate_rule_core(path, index, rule, active_values_by_slot, "suggested_severity", "suggested_penalty", "INVALID_PROMOTION_INPUT")
    _validate_metadata_fields(path, index, rule, "INVALID_PROMOTION_INPUT")
    if rule["category"] != "dress":
        raise _promotion_error(path, "category", "INVALID_PROMOTION_INPUT", "draft compatibility rule category is unsupported", index)
    if rule["status"] != "draft":
        raise _promotion_error(path, "status", "INVALID_PROMOTION_INPUT", "draft compatibility rule status must be 'draft'", index)


def _validate_active_rule(
    path: Path,
    index: int,
    rule: Any,
    active_values_by_slot: dict[str, set[str]],
    seen_ids: set[str] | None,
    code: str,
) -> None:
    _require_record_fields(path, index, rule, _ACTIVE_RULE_FIELDS, code, "compatibility rule")
    _require_string_value(path, index, rule, "rule_id", code, seen_ids)
    _require_string_value(path, index, rule, "category", code)
    _require_string_value(path, index, rule, "reason", code)
    _require_string_value(path, index, rule, "evidence_summary", code)
    _require_string_value(path, index, rule, "decision_source", code)
    _validate_rule_core(path, index, rule, active_values_by_slot, "severity", "penalty", code)
    _validate_metadata_fields(path, index, rule, code)
    if rule["category"] != "dress":
        raise _promotion_error(path, "category", code, "compatibility rule category is unsupported", index)
    if rule["status"] not in {"active", "inactive"}:
        raise _promotion_error(path, "status", code, "compatibility rule status must be 'active' or 'inactive'", index)


def _validate_rule_core(
    path: Path,
    index: int,
    rule: dict[str, Any],
    active_values_by_slot: dict[str, set[str]],
    severity_field: str,
    penalty_field: str,
    code: str,
) -> None:
    left_slot, left_value = _canonicalize_slot_value(str(rule["left_slot"]), str(rule["left_value"]))
    right_slot, right_value = _canonicalize_slot_value(str(rule["right_slot"]), str(rule["right_value"]))
    severity = _parse_severity(path, index, rule, severity_field, code)
    _parse_penalty(path, index, rule, penalty_field, severity, code)
    if (left_slot, right_slot) != _ALLOWED_PAIR:
        raise GenerationError(code=code, message="compatibility rules only support pattern -> detail", details={"path": str(path), "index": index, "left_slot": left_slot, "right_slot": right_slot})
    _require_active_value(path, index, severity_field, "left_value", left_slot, left_value, active_values_by_slot, code)
    _require_active_value(path, index, severity_field, "right_value", right_slot, right_value, active_values_by_slot, code)


def _validate_metadata_fields(
    path: Path,
    index: int,
    rule: dict[str, Any],
    code: str,
) -> None:
    _require_object_value(path, index, rule, "scope", code)
    _require_object_value(path, index, rule, "evidence", code)
    _validate_scope(path, index, rule["scope"], code)
    _validate_evidence(path, index, rule["evidence"], code)
    _parse_confidence(path, index, rule, code)


def _validate_scope(path: Path, index: int, scope: dict[str, Any], code: str) -> None:
    if scope.get("category") != "dress":
        raise _promotion_error(path, "scope", code, "compatibility rule scope category is unsupported", index)
    if not isinstance(scope.get("target_market"), str) or not scope["target_market"].strip():
        raise _promotion_error(path, "scope", code, "compatibility rule scope target_market must be a non-empty string", index)
    for field in ("season_tags", "occasion_tags", "price_bands"):
        _require_string_list_field(path, index, scope, field, code)


def _validate_evidence(path: Path, index: int, evidence: dict[str, Any], code: str) -> None:
    _require_string_list_field(path, index, evidence, "source_feedback_ids", code)
    for field in ("review_reject_rate", "pair_presence_count"):
        if field in evidence:
            _parse_number(path, index, evidence, field, code)


def _build_active_values_by_slot(elements: list[dict[str, Any]]) -> dict[str, set[str]]:
    active_values_by_slot: dict[str, set[str]] = {}
    for element in elements:
        if element.get("status") != "active":
            continue
        slot, value = _canonicalize_slot_value(str(element["slot"]), str(element["value"]))
        active_values_by_slot.setdefault(slot, set()).add(value)
    return active_values_by_slot


def _load_json_object(path: Path, code: str, root_message: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise GenerationError(code=code, message="file must contain valid JSON", details={"path": str(path), "line": error.lineno, "column": error.colno}) from error
    if isinstance(payload, dict):
        return payload
    raise GenerationError(code=code, message=root_message, details={"path": str(path)})


def _require_list_field(path: Path, payload: dict[str, Any], field: str, code: str) -> list[Any]:
    value = payload.get(field)
    if isinstance(value, list):
        return list(value)
    raise GenerationError(code=code, message=f"payload must contain a '{field}' array", details={"path": str(path), "field": field})


def _require_record_fields(
    path: Path,
    index: int,
    record: Any,
    required_fields: set[str],
    code: str,
    record_type: str,
) -> None:
    if not isinstance(record, dict):
        raise GenerationError(code=code, message=f"{record_type} record must be an object", details={"path": str(path), "index": index})
    missing = sorted(required_fields.difference(record.keys()))
    if missing:
        raise GenerationError(code=code, message=f"{record_type} record is missing required fields", details={"path": str(path), "index": index, "missing": missing})


def _require_string_value(
    path: Path,
    index: int,
    record: dict[str, Any],
    field: str,
    code: str,
    seen_values: set[str] | None = None,
) -> None:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise _promotion_error(path, field, code, f"field '{field}' must be a non-empty string", index)
    if seen_values is not None and value in seen_values:
        raise _promotion_error(path, field, code, f"field '{field}' must be unique", index)
    if seen_values is not None:
        seen_values.add(value)


def _require_object_value(path: Path, index: int, record: dict[str, Any], field: str, code: str) -> None:
    if isinstance(record.get(field), dict):
        return
    raise _promotion_error(path, field, code, f"field '{field}' must be an object", index)


def _require_string_list_value(path: Path, index: int, record: dict[str, Any], field: str, code: str) -> None:
    value = record.get(field)
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return
    raise _promotion_error(path, field, code, f"field '{field}' must be a list of strings", index)


def _require_string_list_field(path: Path, index: int, record: dict[str, Any], field: str, code: str) -> None:
    if field in record:
        _require_string_list_value(path, index, record, field, code)
        return
    raise _promotion_error(path, field, code, f"field '{field}' must be a list of strings", index)


def _parse_severity(path: Path, index: int, record: dict[str, Any], field: str, code: str) -> str:
    value = record.get(field)
    if isinstance(value, str) and value.strip().casefold() in {"weak", "strong"}:
        return value.strip().casefold()
    raise _promotion_error(path, field, code, f"field '{field}' must be 'weak' or 'strong'", index)


def _parse_penalty(
    path: Path,
    index: int,
    record: dict[str, Any],
    field: str,
    severity: str,
    code: str,
) -> float:
    penalty = _parse_number(path, index, record, field, code)
    if penalty < 0.0:
        raise _promotion_error(path, field, code, f"field '{field}' must be non-negative", index)
    if severity == "strong" and penalty != 0.0:
        raise _promotion_error(path, field, code, f"field '{field}' must be 0.0 for strong rules", index)
    return penalty


def _parse_confidence(path: Path, index: int, record: dict[str, Any], code: str) -> float:
    confidence = _parse_number(path, index, record, "confidence", code)
    if 0.0 <= confidence <= 1.0:
        return confidence
    raise _promotion_error(path, "confidence", code, "field 'confidence' must be between 0.0 and 1.0", index)


def _parse_number(path: Path, index: int, record: dict[str, Any], field: str, code: str) -> float:
    value = record.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _promotion_error(path, field, code, f"field '{field}' must be numeric", index)
    number = float(value)
    if math.isfinite(number):
        return number
    raise _promotion_error(path, field, code, f"field '{field}' must be finite", index)


def _require_active_value(
    path: Path,
    index: int,
    severity_field: str,
    field: str,
    slot: str,
    value: str,
    active_values_by_slot: dict[str, set[str]],
    code: str,
) -> None:
    if value in active_values_by_slot.get(slot, set()):
        return
    details = {"path": str(path), "index": index, "field": field, "slot": slot, "value": value}
    if severity_field.startswith("suggested_"):
        details["severity_field"] = severity_field
    raise GenerationError(code=code, message="compatibility rule references unknown active element value", details=details)


def _canonical_identity(rule: dict[str, Any]) -> tuple[str, str, str, str]:
    left_slot, left_value = _canonicalize_slot_value(str(rule["left_slot"]), str(rule["left_value"]))
    right_slot, right_value = _canonicalize_slot_value(str(rule["right_slot"]), str(rule["right_value"]))
    return left_slot, left_value, right_slot, right_value


def _canonicalize_slot_value(slot: str, value: str) -> tuple[str, str]:
    return slot.strip().casefold(), value.strip().casefold()


def _identity_payload(rule: dict[str, Any]) -> dict[str, str]:
    return {
        "left_slot": str(rule["left_slot"]).strip(),
        "left_value": str(rule["left_value"]).strip(),
        "right_slot": str(rule["right_slot"]).strip(),
        "right_value": str(rule["right_value"]).strip(),
    }


def _rule_id_from_identity(rule: dict[str, Any]) -> str:
    return f"dress-{_canonicalize_text(str(rule['left_slot']))}-{_slug(str(rule['left_value']))}__{_canonicalize_text(str(rule['right_slot']))}-{_slug(str(rule['right_value']))}"


def _build_merge_rationale(rule_id: str, matched_rule_id: str | None) -> dict[str, Any]:
    return {"rule": "canonical-pair", "resolved_rule_id": rule_id, "matched_active_rule_id": matched_rule_id}


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
            temp_path = target.with_name(f"{target.name}.tmp")
            temp_path.write_text(content, encoding="utf-8")
            temp_paths.append((target, temp_path))
    except OSError as error:
        _cleanup_temp_files(temp_paths)
        raise _write_error(error) from error
    return temp_paths


def _read_output_backups(outputs: tuple[tuple[Path, dict[str, Any]], ...]) -> dict[Path, str | None]:
    return {path: path.read_text(encoding="utf-8") if path.exists() else None for path, _ in outputs}


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


def _promotion_error(path: Path, field: str, code: str, message: str, index: int | None = None) -> GenerationError:
    details: dict[str, Any] = {"path": str(path), "field": field}
    if index is not None:
        details["index"] = index
    return GenerationError(code=code, message=message, details=details)


def _write_error(error: OSError) -> GenerationError:
    return GenerationError(code="PROMOTION_WRITE_FAILED", message="failed to write promotion outputs", details={"path": str(getattr(error, "filename", ""))})


def _io_error(error: OSError) -> GenerationError:
    return GenerationError(code="PROMOTION_IO_FAILED", message="failed to read promotion inputs", details={"path": str(getattr(error, "filename", ""))})


def _canonicalize_text(value: str) -> str:
    return value.strip().casefold()


def _slug(value: str) -> str:
    return "-".join(segment for segment in _canonicalize_text(value).replace("/", " ").split() if segment)
