from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from temu_y2_women.errors import GenerationError
from temu_y2_women.evidence_repository import (
    build_active_values_by_slot,
    load_elements,
    load_evidence_taxonomy,
    load_strategy_templates,
    validate_element_records,
    validate_strategy_template_records,
)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_ELEMENTS_PATH = _PROJECT_ROOT / "data/mvp/dress/elements.json"
_DEFAULT_STRATEGIES_PATH = _PROJECT_ROOT / "data/mvp/dress/strategy_templates.json"
_DEFAULT_TAXONOMY_PATH = _PROJECT_ROOT / "data/mvp/dress/evidence_taxonomy.json"
_DRAFT_ELEMENT_REQUIRED_FIELDS = {
    "draft_id",
    "category",
    "slot",
    "value",
    "tags",
    "price_bands",
    "occasion_tags",
    "season_tags",
    "risk_flags",
    "suggested_base_score",
    "evidence_summary",
    "source_signal_ids",
    "extraction_provenance",
    "status",
}
_DRAFT_STRATEGY_REQUIRED_FIELDS = {
    "hint_id",
    "category",
    "target_market",
    "season_tags",
    "occasion_tags",
    "boost_tags",
    "slot_preferences",
    "priority_signal",
    "source_signal_ids",
    "reason_summary",
    "extraction_provenance",
    "status",
}
_REVIEW_ROOT_FIELDS = {"schema_version", "category", "elements", "strategy_hints"}


def prepare_dress_promotion_review(
    draft_elements_path: Path,
    draft_strategy_hints_path: Path,
    active_elements_path: Path = _DEFAULT_ELEMENTS_PATH,
    active_strategies_path: Path = _DEFAULT_STRATEGIES_PATH,
    taxonomy_path: Path = _DEFAULT_TAXONOMY_PATH,
) -> dict[str, Any]:
    try:
        context = _load_promotion_context(
            draft_elements_path,
            draft_strategy_hints_path,
            active_elements_path,
            active_strategies_path,
            taxonomy_path,
        )
        return _build_review_template(context)
    except GenerationError as error:
        return error.to_dict()
    except OSError as error:
        return _io_error(error).to_dict()


def validate_reviewed_dress_promotion(
    reviewed_path: Path,
    draft_elements_path: Path,
    draft_strategy_hints_path: Path,
    active_elements_path: Path = _DEFAULT_ELEMENTS_PATH,
    active_strategies_path: Path = _DEFAULT_STRATEGIES_PATH,
    taxonomy_path: Path = _DEFAULT_TAXONOMY_PATH,
) -> dict[str, Any]:
    try:
        reviewed, _, _, _ = _prepare_validated_promotion(
            reviewed_path=reviewed_path,
            draft_elements_path=draft_elements_path,
            draft_strategy_hints_path=draft_strategy_hints_path,
            active_elements_path=active_elements_path,
            active_strategies_path=active_strategies_path,
            taxonomy_path=taxonomy_path,
        )
        return reviewed
    except GenerationError as error:
        return error.to_dict()
    except OSError as error:
        return _io_error(error).to_dict()


def apply_reviewed_dress_promotion(
    reviewed_path: Path,
    draft_elements_path: Path,
    draft_strategy_hints_path: Path,
    active_elements_path: Path,
    active_strategies_path: Path,
    report_path: Path,
    taxonomy_path: Path = _DEFAULT_TAXONOMY_PATH,
) -> dict[str, Any]:
    try:
        reviewed, _, post_elements, post_strategies = _prepare_validated_promotion(
            reviewed_path=reviewed_path,
            draft_elements_path=draft_elements_path,
            draft_strategy_hints_path=draft_strategy_hints_path,
            active_elements_path=active_elements_path,
            active_strategies_path=active_strategies_path,
            taxonomy_path=taxonomy_path,
        )
        report = _build_promotion_report(
            reviewed=reviewed,
            draft_elements_path=draft_elements_path,
            draft_strategy_hints_path=draft_strategy_hints_path,
            reviewed_path=reviewed_path,
        )
        _write_output_files(
            (active_elements_path, {"schema_version": "mvp-v1", "elements": post_elements}),
            (active_strategies_path, {"schema_version": "mvp-v1", "strategy_templates": post_strategies}),
            (report_path, report),
        )
        return report
    except GenerationError as error:
        return error.to_dict()
    except OSError as error:
        return _io_error(error).to_dict()


def _load_promotion_context(
    draft_elements_path: Path,
    draft_strategy_hints_path: Path,
    active_elements_path: Path,
    active_strategies_path: Path,
    taxonomy_path: Path,
) -> dict[str, Any]:
    taxonomy = load_evidence_taxonomy(taxonomy_path)
    active_elements = load_elements(active_elements_path, taxonomy_path=taxonomy_path)
    draft_elements = _load_draft_elements(draft_elements_path, taxonomy)
    draft_strategy_hints = _load_draft_strategy_hints(draft_strategy_hints_path, taxonomy)
    active_strategies = load_strategy_templates(
        active_strategies_path,
        taxonomy_path=taxonomy_path,
        elements_path=active_elements_path,
    )
    return {
        "taxonomy": taxonomy,
        "draft_elements": draft_elements,
        "draft_strategy_hints": draft_strategy_hints,
        "active_elements": active_elements,
        "active_strategies": active_strategies,
    }


def _prepare_validated_promotion(
    reviewed_path: Path,
    draft_elements_path: Path,
    draft_strategy_hints_path: Path,
    active_elements_path: Path,
    active_strategies_path: Path,
    taxonomy_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    context = _load_promotion_context(
        draft_elements_path,
        draft_strategy_hints_path,
        active_elements_path,
        active_strategies_path,
        taxonomy_path,
    )
    reviewed = _load_review_bundle(reviewed_path)
    expected = _build_review_template(context)
    _validate_review_bundle(reviewed_path, reviewed, expected)
    post_elements = _build_post_promotion_elements(context["active_elements"], reviewed["elements"])
    _validate_promotion_elements(reviewed_path, context["taxonomy"], post_elements)
    post_values = build_active_values_by_slot(post_elements)
    post_strategies = _build_post_promotion_strategies(context["active_strategies"], reviewed["strategy_hints"])
    _validate_reviewed_strategies(reviewed_path, context["taxonomy"], post_strategies, post_values)
    return reviewed, context, post_elements, post_strategies


def _load_draft_elements(path: Path, taxonomy: dict[str, Any]) -> list[dict[str, Any]]:
    payload = _load_json_object(path, "INVALID_PROMOTION_INPUT", "draft elements root must be an object")
    if payload.get("schema_version") != "signal-ingestion-v1":
        raise _promotion_error(path, "schema_version", "INVALID_PROMOTION_INPUT", "draft elements schema_version is unsupported")
    elements = _require_list_field(path, payload, "elements", "INVALID_PROMOTION_INPUT")
    transformed: list[dict[str, Any]] = []
    seen_draft_ids: set[str] = set()
    for index, element in enumerate(elements):
        _validate_draft_element_record(path, index, element, seen_draft_ids, taxonomy)
        transformed.append(_draft_element_to_active_shape(element))
    _validate_promotion_elements(path, taxonomy, transformed, "INVALID_PROMOTION_INPUT")
    return [dict(element) for element in elements]


def _load_draft_strategy_hints(path: Path, taxonomy: dict[str, Any]) -> list[dict[str, Any]]:
    payload = _load_json_object(path, "INVALID_PROMOTION_INPUT", "draft strategy hints root must be an object")
    if payload.get("schema_version") != "signal-ingestion-v1":
        raise _promotion_error(path, "schema_version", "INVALID_PROMOTION_INPUT", "draft strategy hints schema_version is unsupported")
    strategy_hints = _require_list_field(path, payload, "strategy_hints", "INVALID_PROMOTION_INPUT")
    seen_hint_ids: set[str] = set()
    for index, strategy_hint in enumerate(strategy_hints):
        _validate_draft_strategy_record(path, index, strategy_hint, seen_hint_ids, taxonomy)
    return [dict(strategy_hint) for strategy_hint in strategy_hints]


def _load_review_bundle(path: Path) -> dict[str, Any]:
    payload = _load_json_object(path, "INVALID_PROMOTION_REVIEW", "promotion review root must be an object")
    if payload.get("schema_version") != "promotion-review-v1":
        raise _promotion_error(path, "schema_version", "INVALID_PROMOTION_REVIEW", "promotion review schema_version is unsupported")
    return payload


def _build_review_template(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "promotion-review-v1",
        "category": "dress",
        "elements": _build_element_review_entries(context["draft_elements"], context["active_elements"]),
        "strategy_hints": _build_strategy_review_entries(
            context["draft_strategy_hints"],
            context["active_strategies"],
        ),
    }


def _build_element_review_entries(
    draft_elements: list[dict[str, Any]],
    active_elements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    active_by_identity = {
        _canonical_identity(str(element["slot"]), str(element["value"])): element
        for element in active_elements
        if element.get("status") == "active"
    }
    entries = [_build_element_review_entry(element, active_by_identity) for element in draft_elements]
    return sorted(entries, key=lambda item: str(item["draft_id"]))


def _build_element_review_entry(
    draft_element: dict[str, Any],
    active_by_identity: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    identity = _canonical_identity(str(draft_element["slot"]), str(draft_element["value"]))
    matched = active_by_identity.get(identity)
    canonical_identity = {"slot": draft_element["slot"], "value": draft_element["value"]}
    entry = {
        "draft_id": draft_element["draft_id"],
        "merge_action": "update" if matched else "create",
        "matched_active_element_id": matched["element_id"] if matched else None,
        "canonical_identity": canonical_identity,
        "merge_rationale": _build_element_merge_rationale(draft_element, matched),
        "source_signal_ids": list(draft_element["source_signal_ids"]),
        "decision": "pending",
        "proposed_element": {
            "element_id": matched["element_id"] if matched else _draft_element_id(draft_element),
            "category": draft_element["category"],
            "slot": draft_element["slot"],
            "value": draft_element["value"],
            "tags": list(draft_element["tags"]),
            "base_score": draft_element["suggested_base_score"],
            "price_bands": list(draft_element["price_bands"]),
            "occasion_tags": list(draft_element["occasion_tags"]),
            "season_tags": list(draft_element["season_tags"]),
            "risk_flags": list(draft_element["risk_flags"]),
            "evidence_summary": draft_element["evidence_summary"],
            "status": "active",
        },
    }
    review_context = _build_structured_review_context(draft_element)
    if review_context is not None:
        entry["review_context"] = review_context
    return entry


def _build_structured_review_context(draft_element: dict[str, Any]) -> dict[str, Any] | None:
    provenance = draft_element.get("extraction_provenance")
    if not isinstance(provenance, dict):
        return None
    structured_matches = provenance.get("structured_matches")
    if not isinstance(structured_matches, list) or not structured_matches:
        structured_matches = provenance.get("structured_candidate_matches")
    if not isinstance(structured_matches, list) or not structured_matches:
        return None
    context = {
        "matched_channels": list(provenance.get("matched_channels", [])),
        "structured_matches": [_structured_review_match(match) for match in structured_matches if isinstance(match, dict)],
    }
    rule_matches = provenance.get("rule_matches")
    if isinstance(rule_matches, list) and rule_matches:
        context["rule_matches"] = [_rule_review_match(match) for match in rule_matches if isinstance(match, dict)]
    return context


def _structured_review_match(match: dict[str, Any]) -> dict[str, Any]:
    return {
        "signal_id": match["signal_id"],
        "slot": match["slot"],
        "value": match["value"],
        "candidate_source": match["candidate_source"],
        "supporting_card_ids": list(match["supporting_card_ids"]),
        "supporting_card_count": match["supporting_card_count"],
        "aggregation_threshold": match["aggregation_threshold"],
        "observation_model": match["observation_model"],
        "evidence_summary": match["evidence_summary"],
    }


def _rule_review_match(match: dict[str, Any]) -> dict[str, Any]:
    return {
        "signal_id": match["signal_id"],
        "rule_slot": match["rule_slot"],
        "rule_value": match["rule_value"],
        "matched_phrases": list(match["matched_phrases"]),
    }


def _build_strategy_review_entries(
    draft_strategy_hints: list[dict[str, Any]],
    active_strategies: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    active_by_id = {
        str(strategy["strategy_id"]): strategy
        for strategy in active_strategies
        if strategy.get("status") == "active"
    }
    entries = [_build_strategy_review_entry(hint, active_by_id) for hint in draft_strategy_hints]
    return sorted(entries, key=lambda item: str(item["hint_id"]))


def _build_strategy_review_entry(
    draft_strategy_hint: dict[str, Any],
    active_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    strategy_id, matched_id = _resolve_strategy_identity(draft_strategy_hint, active_by_id)
    canonical_identity = {
        "target_market": draft_strategy_hint["target_market"],
        "resolved_strategy_id": strategy_id,
    }
    score_boost, score_cap = _default_strategy_scoring(draft_strategy_hint)
    return {
        "hint_id": draft_strategy_hint["hint_id"],
        "merge_action": "update" if matched_id else "create",
        "matched_active_strategy_id": matched_id,
        "canonical_identity": canonical_identity,
        "merge_rationale": _build_strategy_merge_rationale(strategy_id, matched_id),
        "source_signal_ids": list(draft_strategy_hint["source_signal_ids"]),
        "decision": "pending",
        "proposed_strategy_template": {
            "strategy_id": strategy_id,
            "category": draft_strategy_hint["category"],
            "target_market": draft_strategy_hint["target_market"],
            "priority": draft_strategy_hint["priority_signal"],
            "date_window": {"start": "01-01", "end": "12-31"},
            "occasion_tags": list(draft_strategy_hint["occasion_tags"]),
            "boost_tags": list(draft_strategy_hint["boost_tags"]),
            "suppress_tags": [],
            "slot_preferences": dict(draft_strategy_hint["slot_preferences"]),
            "score_boost": score_boost,
            "score_cap": score_cap,
            "prompt_hints": [draft_strategy_hint["reason_summary"]],
            "reason_template": draft_strategy_hint["reason_summary"],
            "status": "active",
        },
    }


def _default_strategy_scoring(draft_strategy_hint: dict[str, Any]) -> tuple[float, float]:
    if _is_product_image_strategy_hint(draft_strategy_hint):
        return 0.08, 0.12
    return 0.0, 0.0


def _validate_review_bundle(path: Path, reviewed: dict[str, Any], expected: dict[str, Any]) -> None:
    missing = sorted(_REVIEW_ROOT_FIELDS.difference(reviewed.keys()))
    if missing:
        raise GenerationError(
            code="INVALID_PROMOTION_REVIEW",
            message="promotion review is missing required fields",
            details={"path": str(path), "missing": missing},
        )
    if reviewed.get("category") != "dress":
        raise _promotion_error(path, "category", "INVALID_PROMOTION_REVIEW", "promotion review category is unsupported")
    _validate_review_elements(path, reviewed["elements"], expected["elements"])
    _validate_review_strategies(path, reviewed["strategy_hints"], expected["strategy_hints"])


def _validate_review_elements(
    path: Path,
    reviewed_elements: Any,
    expected_elements: list[dict[str, Any]],
) -> None:
    _validate_review_record_collection(
        path,
        reviewed_elements,
        expected_elements,
        "elements",
        "draft_id",
        "matched_active_element_id",
        "proposed_element",
    )


def _validate_review_strategies(
    path: Path,
    reviewed_strategies: Any,
    expected_strategies: list[dict[str, Any]],
) -> None:
    _validate_review_record_collection(
        path,
        reviewed_strategies,
        expected_strategies,
        "strategy_hints",
        "hint_id",
        "matched_active_strategy_id",
        "proposed_strategy_template",
    )


def _validate_review_record_collection(
    path: Path,
    reviewed_records: Any,
    expected_records: list[dict[str, Any]],
    field: str,
    id_field: str,
    matched_field: str,
    proposed_field: str,
) -> None:
    if not isinstance(reviewed_records, list):
        raise _promotion_error(path, field, "INVALID_PROMOTION_REVIEW", f"promotion review field '{field}' must be a list")
    expected_by_id = {str(record[id_field]): record for record in expected_records}
    seen_ids: set[str] = set()
    for index, reviewed_record in enumerate(reviewed_records):
        expected = _match_expected_review_record(path, index, reviewed_record, expected_by_id, id_field)
        reviewed_id = str(reviewed_record[id_field])
        if reviewed_id in seen_ids:
            raise _promotion_error(path, id_field, "INVALID_PROMOTION_REVIEW", f"promotion review field '{id_field}' must be unique", index)
        seen_ids.add(reviewed_id)
        _validate_review_record_shape(path, index, reviewed_record, id_field, matched_field, proposed_field)
        _validate_review_record_details(path, index, reviewed_record, expected, matched_field, proposed_field)
    if seen_ids != set(expected_by_id):
        raise _promotion_error(path, field, "INVALID_PROMOTION_REVIEW", f"promotion review field '{field}' does not match staged draft count")


def _match_expected_review_record(
    path: Path,
    index: int,
    reviewed_record: Any,
    expected_by_id: dict[str, dict[str, Any]],
    id_field: str,
) -> dict[str, Any]:
    if not isinstance(reviewed_record, dict) or not isinstance(reviewed_record.get(id_field), str):
        raise _promotion_error(path, id_field, "INVALID_PROMOTION_REVIEW", "promotion review record is missing a stable source identifier")
    expected = expected_by_id.get(str(reviewed_record[id_field]))
    if expected is None:
        raise GenerationError(
            code="INVALID_PROMOTION_REVIEW",
            message="promotion review references an unknown staged draft",
            details={"path": str(path), "index": index, "field": id_field, "value": reviewed_record[id_field]},
        )
    return expected


def _validate_review_record_shape(
    path: Path,
    index: int,
    reviewed_record: dict[str, Any],
    id_field: str,
    matched_field: str,
    proposed_field: str,
) -> None:
    required_fields = {
        id_field,
        "merge_action",
        matched_field,
        "canonical_identity",
        "merge_rationale",
        "source_signal_ids",
        "decision",
        proposed_field,
    }
    missing = sorted(required_fields.difference(reviewed_record.keys()))
    if missing:
        raise GenerationError(
            code="INVALID_PROMOTION_REVIEW",
            message="promotion review record is missing required fields",
            details={"path": str(path), "index": index, "missing": missing},
        )
    _require_object_value(path, index, reviewed_record, "canonical_identity", "INVALID_PROMOTION_REVIEW")
    _require_object_value(path, index, reviewed_record, "merge_rationale", "INVALID_PROMOTION_REVIEW")
    if reviewed_record["decision"] not in {"accept", "reject"}:
        raise _promotion_error(path, "decision", "INVALID_PROMOTION_REVIEW", "promotion review decision must be 'accept' or 'reject'")
    proposed = reviewed_record.get(proposed_field)
    if reviewed_record["decision"] == "accept" and not isinstance(proposed, dict):
        raise _promotion_error(path, proposed_field, "INVALID_PROMOTION_REVIEW", "promotion review curated record must be an object")
    if reviewed_record["decision"] == "reject" and proposed is not None and not isinstance(proposed, dict):
        raise _promotion_error(path, proposed_field, "INVALID_PROMOTION_REVIEW", "promotion review rejected payload must be null or an object")


def _validate_review_record_details(
    path: Path,
    index: int,
    reviewed_record: dict[str, Any],
    expected: dict[str, Any],
    matched_field: str,
    proposed_field: str,
) -> None:
    for field in ("merge_action", matched_field, "canonical_identity", "merge_rationale", "source_signal_ids"):
        if reviewed_record[field] != expected[field]:
            raise GenerationError(
                code="INVALID_PROMOTION_REVIEW",
                message=f"promotion review field '{field}' must match the staged template",
                details={"path": str(path), "index": index, "field": field},
            )
    if reviewed_record["decision"] == "accept":
        _validate_curated_identity(path, index, reviewed_record, expected, proposed_field)


def _validate_curated_identity(
    path: Path,
    index: int,
    reviewed_record: dict[str, Any],
    expected: dict[str, Any],
    proposed_field: str,
) -> None:
    proposed = reviewed_record[proposed_field]
    expected_proposed = expected[proposed_field]
    identity_fields = ["category"]
    if proposed_field == "proposed_element":
        identity_fields.extend(["slot", "value", "status"])
    else:
        identity_fields.extend(["target_market", "status"])
    for field in identity_fields:
        if proposed.get(field) != expected_proposed.get(field):
            raise GenerationError(
                code="INVALID_PROMOTION_REVIEW",
                message=f"promotion review field '{field}' must preserve staged identity",
                details={"path": str(path), "index": index, "field": field},
            )
    _validate_update_stable_id(path, index, reviewed_record, expected_proposed, proposed_field)


def _validate_update_stable_id(
    path: Path,
    index: int,
    reviewed_record: dict[str, Any],
    expected_proposed: dict[str, Any],
    proposed_field: str,
) -> None:
    if reviewed_record["merge_action"] != "update":
        return
    proposed = reviewed_record[proposed_field]
    field = "element_id" if proposed_field == "proposed_element" else "strategy_id"
    if proposed.get(field) == expected_proposed.get(field):
        return
    raise GenerationError(
        code="INVALID_PROMOTION_REVIEW",
        message=f"promotion review field '{field}' must preserve update identity",
        details={"path": str(path), "index": index, "field": field},
    )


def _build_post_promotion_elements(
    active_elements: list[dict[str, Any]],
    reviewed_elements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    snapshot = [dict(element) for element in active_elements]
    identity_to_index = {
        _canonical_identity(str(element["slot"]), str(element["value"])): index
        for index, element in enumerate(snapshot)
        if element.get("status") == "active"
    }
    for record in reviewed_elements:
        if record["decision"] != "accept":
            continue
        proposed = dict(record["proposed_element"])
        identity = _canonical_identity(str(proposed["slot"]), str(proposed["value"]))
        if record["merge_action"] == "update" and identity in identity_to_index:
            active = snapshot[identity_to_index[identity]]
            snapshot[identity_to_index[identity]] = _merge_updated_element(active, proposed)
            continue
        snapshot.append(proposed)
    return snapshot


def _merge_updated_element(active: dict[str, Any], proposed: dict[str, Any]) -> dict[str, Any]:
    merged = dict(active)
    merged.update(proposed)
    merged["tags"] = _merge_string_lists(active.get("tags"), proposed.get("tags"))
    merged["price_bands"] = _merge_string_lists(active.get("price_bands"), proposed.get("price_bands"))
    merged["occasion_tags"] = _merge_string_lists(active.get("occasion_tags"), proposed.get("occasion_tags"))
    merged["season_tags"] = _merge_string_lists(active.get("season_tags"), proposed.get("season_tags"))
    merged["risk_flags"] = _merge_string_lists(active.get("risk_flags"), proposed.get("risk_flags"))
    merged["base_score"] = max(float(active["base_score"]), float(proposed["base_score"]))
    return merged


def _merge_string_lists(active_values: Any, proposed_values: Any) -> list[str]:
    merged: list[str] = []
    for values in (active_values, proposed_values):
        if not isinstance(values, list):
            continue
        for value in values:
            if isinstance(value, str) and value not in merged:
                merged.append(value)
    return merged


def _build_post_promotion_strategies(
    active_strategies: list[dict[str, Any]],
    reviewed_strategies: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    snapshot = [dict(strategy) for strategy in active_strategies]
    strategy_to_index = {
        str(strategy["strategy_id"]): index
        for index, strategy in enumerate(snapshot)
        if strategy.get("status") == "active"
    }
    for record in reviewed_strategies:
        if record["decision"] != "accept":
            continue
        matched_id = record["matched_active_strategy_id"]
        proposed = dict(record["proposed_strategy_template"])
        if record["merge_action"] == "update" and isinstance(matched_id, str) and matched_id in strategy_to_index:
            snapshot[strategy_to_index[matched_id]] = proposed
            continue
        snapshot.append(proposed)
    return snapshot


def _build_promotion_report(
    reviewed: dict[str, Any],
    draft_elements_path: Path,
    draft_strategy_hints_path: Path,
    reviewed_path: Path,
) -> dict[str, Any]:
    return {
        "schema_version": "promotion-report-v1",
        "category": "dress",
        "source_artifacts": {
            "draft_elements": draft_elements_path.name,
            "draft_strategy_hints": draft_strategy_hints_path.name,
            "reviewed_decisions": reviewed_path.name,
        },
        "summary": {
            "elements": _build_report_summary(reviewed["elements"]),
            "strategy_hints": _build_report_summary(reviewed["strategy_hints"]),
        },
        "elements": _build_element_report_items(reviewed["elements"]),
        "strategy_hints": _build_strategy_report_items(reviewed["strategy_hints"]),
        "warnings": [],
    }


def _build_report_summary(records: list[dict[str, Any]]) -> dict[str, int]:
    accepted = sum(1 for record in records if record["decision"] == "accept")
    rejected = sum(1 for record in records if record["decision"] == "reject")
    created = sum(1 for record in records if record["decision"] == "accept" and record["merge_action"] == "create")
    updated = sum(1 for record in records if record["decision"] == "accept" and record["merge_action"] == "update")
    return {
        "accepted": accepted,
        "rejected": rejected,
        "created": created,
        "updated": updated,
    }


def _build_element_report_items(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "draft_id": record["draft_id"],
            "decision": record["decision"],
            "merge_action": record["merge_action"],
            "element_id": _report_record_id(record.get("proposed_element"), "element_id"),
            "source_signal_ids": list(record["source_signal_ids"]),
        }
        for record in records
    ]


def _build_strategy_report_items(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "hint_id": record["hint_id"],
            "decision": record["decision"],
            "merge_action": record["merge_action"],
            "strategy_id": _report_record_id(record.get("proposed_strategy_template"), "strategy_id"),
            "source_signal_ids": list(record["source_signal_ids"]),
        }
        for record in records
    ]


def _validate_promotion_elements(
    path: Path,
    taxonomy: dict[str, Any],
    elements: list[dict[str, Any]],
    code: str = "INVALID_PROMOTION_REVIEW",
) -> None:
    try:
        validate_element_records(elements, taxonomy, path=path)
    except GenerationError as error:
        raise _rewrap_error(error, code) from error


def _validate_reviewed_strategies(
    path: Path,
    taxonomy: dict[str, Any],
    strategies: list[dict[str, Any]],
    active_values_by_slot: dict[str, set[str]],
) -> None:
    try:
        validate_strategy_template_records(
            strategies,
            taxonomy,
            active_values_by_slot,
            path=path,
        )
    except GenerationError as error:
        raise _rewrap_error(error, "INVALID_PROMOTION_REVIEW") from error


def _validate_draft_element_record(
    path: Path,
    index: int,
    element: Any,
    seen_draft_ids: set[str],
    taxonomy: dict[str, Any],
) -> None:
    _require_record_fields(path, index, element, _DRAFT_ELEMENT_REQUIRED_FIELDS, "INVALID_PROMOTION_INPUT", "draft element")
    _require_string_value(path, index, element, "draft_id", "INVALID_PROMOTION_INPUT", seen_draft_ids)
    _require_string_value(path, index, element, "category", "INVALID_PROMOTION_INPUT")
    _require_object_value(path, index, element, "extraction_provenance", "INVALID_PROMOTION_INPUT")
    _require_string_list_value(path, index, element, "price_bands", "INVALID_PROMOTION_INPUT")
    _require_string_list_value(path, index, element, "source_signal_ids", "INVALID_PROMOTION_INPUT")
    _validate_allowed_list(path, index, element, "tags", taxonomy["allowed_tags"])
    _validate_allowed_list(path, index, element, "occasion_tags", taxonomy["allowed_occasions"])
    _validate_allowed_list(path, index, element, "season_tags", taxonomy["allowed_seasons"])
    _validate_allowed_list(path, index, element, "risk_flags", taxonomy["allowed_risk_flags"])
    if element["category"] != "dress":
        raise _promotion_error(path, "category", "INVALID_PROMOTION_INPUT", "draft element category is unsupported", index)
    if element["status"] != "draft":
        raise _promotion_error(path, "status", "INVALID_PROMOTION_INPUT", "draft element status must be 'draft'", index)


def _validate_draft_strategy_record(
    path: Path,
    index: int,
    strategy_hint: Any,
    seen_hint_ids: set[str],
    taxonomy: dict[str, Any],
) -> None:
    _require_record_fields(path, index, strategy_hint, _DRAFT_STRATEGY_REQUIRED_FIELDS, "INVALID_PROMOTION_INPUT", "draft strategy")
    _require_string_value(path, index, strategy_hint, "hint_id", "INVALID_PROMOTION_INPUT", seen_hint_ids)
    _require_string_value(path, index, strategy_hint, "category", "INVALID_PROMOTION_INPUT")
    _require_string_value(path, index, strategy_hint, "target_market", "INVALID_PROMOTION_INPUT")
    _require_string_value(path, index, strategy_hint, "reason_summary", "INVALID_PROMOTION_INPUT")
    _require_object_value(path, index, strategy_hint, "extraction_provenance", "INVALID_PROMOTION_INPUT")
    _require_string_list_value(path, index, strategy_hint, "source_signal_ids", "INVALID_PROMOTION_INPUT")
    _validate_allowed_list(path, index, strategy_hint, "season_tags", taxonomy["allowed_seasons"])
    _validate_allowed_list(path, index, strategy_hint, "occasion_tags", taxonomy["allowed_occasions"])
    _validate_allowed_list(path, index, strategy_hint, "boost_tags", taxonomy["allowed_tags"])
    _validate_slot_preferences(path, index, strategy_hint, taxonomy)
    if not isinstance(strategy_hint.get("priority_signal"), int):
        raise _promotion_error(path, "priority_signal", "INVALID_PROMOTION_INPUT", "draft strategy priority_signal must be an integer", index)
    if strategy_hint["category"] != "dress":
        raise _promotion_error(path, "category", "INVALID_PROMOTION_INPUT", "draft strategy category is unsupported", index)
    if strategy_hint["target_market"] != "US":
        raise _promotion_error(path, "target_market", "INVALID_PROMOTION_INPUT", "draft strategy target_market is unsupported", index)
    if strategy_hint["status"] != "draft":
        raise _promotion_error(path, "status", "INVALID_PROMOTION_INPUT", "draft strategy status must be 'draft'", index)


def _draft_element_to_active_shape(draft_element: dict[str, Any]) -> dict[str, Any]:
    return {
        "element_id": _draft_element_id(draft_element),
        "category": draft_element["category"],
        "slot": draft_element["slot"],
        "value": draft_element["value"],
        "tags": list(draft_element["tags"]),
        "base_score": draft_element["suggested_base_score"],
        "price_bands": list(draft_element["price_bands"]),
        "occasion_tags": list(draft_element["occasion_tags"]),
        "season_tags": list(draft_element["season_tags"]),
        "risk_flags": list(draft_element["risk_flags"]),
        "evidence_summary": draft_element["evidence_summary"],
        "status": "active",
    }


def _draft_element_id(draft_element: dict[str, Any]) -> str:
    return f"{draft_element['category']}-{draft_element['slot']}-{_slug(str(draft_element['value']))}-001"


def _resolve_strategy_identity(
    draft_strategy_hint: dict[str, Any],
    active_by_id: dict[str, dict[str, Any]],
) -> tuple[str, str | None]:
    hint_id = str(draft_strategy_hint["hint_id"])
    base_id = f"dress-{hint_id.removeprefix('draft-strategy-')}"
    if _is_product_image_strategy_hint(draft_strategy_hint):
        return f"{base_id}-product-image", None
    if base_id in active_by_id:
        return base_id, base_id
    stripped_id = base_id.removesuffix("-refresh")
    if stripped_id in active_by_id:
        return stripped_id, stripped_id
    return base_id, None


def _is_product_image_strategy_hint(draft_strategy_hint: dict[str, Any]) -> bool:
    source_signal_ids = draft_strategy_hint.get("source_signal_ids")
    if not isinstance(source_signal_ids, list) or not source_signal_ids:
        return False
    return all(isinstance(item, str) and item.startswith("product-image-") for item in source_signal_ids)


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


def _require_list_field(path: Path, payload: dict[str, Any], field: str, code: str) -> list[dict[str, Any]]:
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


def _require_string_list_value(
    path: Path,
    index: int,
    record: dict[str, Any],
    field: str,
    code: str,
) -> None:
    value = record.get(field)
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return
    raise _promotion_error(path, field, code, f"field '{field}' must be a list of strings", index)


def _require_object_value(
    path: Path,
    index: int,
    record: dict[str, Any],
    field: str,
    code: str,
) -> None:
    if isinstance(record.get(field), dict):
        return
    raise _promotion_error(path, field, code, f"field '{field}' must be an object", index)


def _validate_allowed_list(
    path: Path,
    index: int,
    record: dict[str, Any],
    field: str,
    allowed_values: list[str],
) -> None:
    _require_string_list_value(path, index, record, field, "INVALID_PROMOTION_INPUT")
    unknown = sorted(value for value in record[field] if value not in allowed_values)
    if unknown:
        raise GenerationError(
            code="INVALID_PROMOTION_INPUT",
            message=f"field '{field}' contains unsupported values",
            details={"path": str(path), "index": index, "field": field, "values": unknown},
        )


def _validate_slot_preferences(
    path: Path,
    index: int,
    strategy_hint: dict[str, Any],
    taxonomy: dict[str, Any],
) -> None:
    slot_preferences = strategy_hint.get("slot_preferences")
    if not isinstance(slot_preferences, dict):
        raise _promotion_error(path, "slot_preferences", "INVALID_PROMOTION_INPUT", "field 'slot_preferences' must be an object", index)
    for slot, values in slot_preferences.items():
        if not isinstance(slot, str) or slot not in taxonomy["allowed_slots"]:
            raise _promotion_error(path, "slot_preferences", "INVALID_PROMOTION_INPUT", "slot_preferences references an unknown slot", index)
        if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
            raise _promotion_error(path, "slot_preferences", "INVALID_PROMOTION_INPUT", "slot_preferences values must be arrays of strings", index)


def _promotion_error(
    path: Path,
    field: str,
    code: str,
    message: str,
    index: int | None = None,
) -> GenerationError:
    details: dict[str, Any] = {"path": str(path), "field": field}
    if index is not None:
        details["index"] = index
    return GenerationError(code=code, message=message, details=details)


def _rewrap_error(error: GenerationError, code: str) -> GenerationError:
    return GenerationError(code=code, message=error.message, details=dict(error.details))


def _canonical_identity(slot: str, value: str) -> tuple[str, str]:
    return slot.strip().casefold(), value.strip().casefold()


def _build_element_merge_rationale(
    draft_element: dict[str, Any],
    matched: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "rule": "canonical-slot-value",
        "resolved_element_id": matched["element_id"] if matched else _draft_element_id(draft_element),
        "matched_active_element_id": matched["element_id"] if matched else None,
    }


def _build_strategy_merge_rationale(strategy_id: str, matched_id: str | None) -> dict[str, Any]:
    return {
        "rule": "resolved-strategy-id",
        "resolved_strategy_id": strategy_id,
        "matched_active_strategy_id": matched_id,
    }


def _slug(value: str) -> str:
    return "-".join(segment for segment in value.strip().casefold().replace("/", " ").split() if segment)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


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


def _write_error(error: OSError) -> GenerationError:
    return GenerationError(
        code="PROMOTION_WRITE_FAILED",
        message="failed to write promotion outputs",
        details={"path": str(getattr(error, "filename", ""))},
    )


def _io_error(error: OSError) -> GenerationError:
    return GenerationError(
        code="PROMOTION_IO_FAILED",
        message="failed to read promotion inputs",
        details={"path": str(getattr(error, "filename", ""))},
    )


def _report_record_id(record: Any, field: str) -> Any:
    if isinstance(record, dict):
        return record.get(field)
    return None
