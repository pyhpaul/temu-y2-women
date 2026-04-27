from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from temu_y2_women.errors import GenerationError
from temu_y2_women.models import CandidateElement, NormalizedRequest, SelectedStrategy

_DEFAULT_ELEMENTS_PATH = Path("data/mvp/dress/elements.json")
_DEFAULT_STRATEGIES_PATH = Path("data/mvp/dress/strategy_templates.json")
_DEFAULT_TAXONOMY_PATH = Path("data/mvp/dress/evidence_taxonomy.json")
_ELEMENT_REQUIRED_FIELDS = {
    "element_id",
    "category",
    "slot",
    "value",
    "tags",
    "base_score",
    "price_bands",
    "occasion_tags",
    "season_tags",
    "risk_flags",
    "evidence_summary",
    "status",
}
_STRATEGY_REQUIRED_FIELDS = {
    "strategy_id",
    "category",
    "target_market",
    "priority",
    "date_window",
    "occasion_tags",
    "boost_tags",
    "suppress_tags",
    "slot_preferences",
    "score_boost",
    "score_cap",
    "prompt_hints",
    "reason_template",
    "status",
}


def load_evidence_taxonomy(path: Path = _DEFAULT_TAXONOMY_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message="evidence taxonomy root must be an object",
            details={"path": str(path)},
        )
    required_fields = {
        "allowed_slots",
        "allowed_tags",
        "allowed_occasions",
        "allowed_seasons",
        "allowed_risk_flags",
        "summary",
        "base_score",
    }
    missing = sorted(required_fields.difference(payload.keys()))
    if missing:
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message="evidence taxonomy is missing required fields",
            details={"path": str(path), "missing": missing},
        )

    for field in (
        "allowed_slots",
        "allowed_tags",
        "allowed_occasions",
        "allowed_seasons",
        "allowed_risk_flags",
    ):
        _validate_taxonomy_string_list(path=path, taxonomy=payload, field=field)

    _validate_taxonomy_bounds(
        path=path,
        taxonomy=payload,
        field="summary",
        min_key="min_length",
        max_key="max_length",
    )
    _validate_taxonomy_bounds(
        path=path,
        taxonomy=payload,
        field="base_score",
        min_key="min",
        max_key="max",
    )
    return payload


def load_elements(
    path: Path = _DEFAULT_ELEMENTS_PATH,
    taxonomy_path: Path = _DEFAULT_TAXONOMY_PATH,
) -> list[dict[str, Any]]:
    taxonomy = load_evidence_taxonomy(taxonomy_path)
    elements = _load_record_array(
        path=path,
        root_message="elements evidence store root must be an object",
        array_field="elements",
        array_message="elements evidence store must contain an 'elements' array",
    )
    _validate_element_records(path=path, taxonomy=taxonomy, elements=elements)
    return list(elements)


def load_strategy_templates(
    path: Path = _DEFAULT_STRATEGIES_PATH,
    taxonomy_path: Path = _DEFAULT_TAXONOMY_PATH,
    elements_path: Path = _DEFAULT_ELEMENTS_PATH,
) -> list[dict[str, Any]]:
    taxonomy = load_evidence_taxonomy(taxonomy_path)
    active_values_by_slot = build_active_values_by_slot(load_elements(elements_path, taxonomy_path=taxonomy_path))
    strategies = _load_record_array(
        path=path,
        root_message="strategy evidence store root must be an object",
        array_field="strategy_templates",
        array_message="strategy evidence store must contain a 'strategy_templates' array",
    )
    _validate_strategy_template_records(
        path=path,
        taxonomy=taxonomy,
        active_values_by_slot=active_values_by_slot,
        strategies=strategies,
    )
    return list(strategies)


def validate_element_records(
    elements: list[dict[str, Any]],
    taxonomy: dict[str, Any],
    path: Path | None = None,
) -> list[dict[str, Any]]:
    _validate_element_records(
        path=path or Path("<memory>"),
        taxonomy=taxonomy,
        elements=elements,
    )
    return list(elements)


def validate_strategy_template_records(
    strategies: list[dict[str, Any]],
    taxonomy: dict[str, Any],
    active_values_by_slot: dict[str, set[str]],
    path: Path | None = None,
) -> list[dict[str, Any]]:
    _validate_strategy_template_records(
        path=path or Path("<memory>"),
        taxonomy=taxonomy,
        active_values_by_slot=active_values_by_slot,
        strategies=strategies,
    )
    return list(strategies)


def build_active_values_by_slot(elements: list[dict[str, Any]]) -> dict[str, set[str]]:
    return _build_active_values_by_slot(elements)


def retrieve_candidates(
    request: NormalizedRequest,
    elements: list[dict[str, Any]],
    selected_strategies: tuple[SelectedStrategy, ...],
) -> tuple[dict[str, list[dict[str, Any]]], tuple[str, ...]]:
    strategy_suppress_tags = _collect_strategy_suppress_tags(selected_strategies)
    grouped: dict[str, list[dict[str, Any]]] = {}
    avoid_filtered_count = 0
    avoid_matched_tags: set[str] = set()
    for element in elements:
        include_element, matched_avoid_tags = _is_candidate_element_eligible(
            request=request,
            element=element,
            strategy_suppress_tags=strategy_suppress_tags,
        )
        if matched_avoid_tags:
            avoid_filtered_count += 1
            avoid_matched_tags.update(matched_avoid_tags)
        if not include_element:
            continue
        candidate = _build_scored_candidate(
            request=request,
            element=element,
            selected_strategies=selected_strategies,
        )
        grouped.setdefault(str(element["slot"]), []).append(candidate)
    _raise_if_no_candidates(request=request, grouped=grouped)
    return grouped, _build_retrieval_warnings(avoid_filtered_count, avoid_matched_tags)


def flatten_candidates(grouped_candidates: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for candidates in grouped_candidates.values():
        flattened.extend(
            {
                "element_id": candidate["element_id"],
                "slot": candidate["slot"],
                "value": candidate["value"],
                "effective_score": candidate["effective_score"],
                "evidence_summary": candidate.get("evidence_summary", ""),
            }
            for candidate in sorted(
                candidates,
                key=lambda item: (float(item["effective_score"]), str(item["element_id"])),
                reverse=True,
            )
        )
    return flattened


def _matches_price_band(request: NormalizedRequest, element: dict[str, Any]) -> bool:
    if request.price_band is None:
        return True
    return request.price_band in element.get("price_bands", [])


def _canonicalize_slot_value(slot: str, value: str) -> tuple[str, str]:
    return slot.strip().casefold(), value.strip().casefold()


def _validate_taxonomy_string_list(path: Path, taxonomy: dict[str, Any], field: str) -> None:
    value = taxonomy.get(field)
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message=f"taxonomy field '{field}' must be a list of strings",
            details={"path": str(path), "field": field},
        )


def _validate_taxonomy_bounds(
    path: Path,
    taxonomy: dict[str, Any],
    field: str,
    min_key: str,
    max_key: str,
) -> None:
    value = taxonomy.get(field)
    if not isinstance(value, dict):
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message=f"taxonomy field '{field}' must be an object",
            details={"path": str(path), "field": field},
        )
    if not isinstance(value.get(min_key), (int, float)) or not isinstance(value.get(max_key), (int, float)):
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message=f"taxonomy field '{field}' must include numeric {min_key}/{max_key} values",
            details={"path": str(path), "field": field},
        )


def _validate_element_record(
    path: Path,
    taxonomy: dict[str, Any],
    index: int,
    element: dict[str, Any],
) -> None:
    _validate_allowed_string(
        path=path,
        index=index,
        field="slot",
        value=element.get("slot"),
        allowed_values=set(taxonomy["allowed_slots"]),
        record_type="element",
    )
    _validate_string_list_field(
        path=path,
        index=index,
        field="price_bands",
        value=element.get("price_bands"),
        record_type="element",
    )
    _validate_element_taxonomy_lists(path=path, taxonomy=taxonomy, index=index, element=element)
    _validate_element_score(path=path, taxonomy=taxonomy, index=index, element=element)
    _validate_element_summary(path=path, taxonomy=taxonomy, index=index, element=element)


def _validate_strategy_record(
    path: Path,
    index: int,
    strategy: dict[str, Any],
    taxonomy: dict[str, Any],
    active_values_by_slot: dict[str, set[str]],
) -> None:
    _validate_strategy_numeric_fields(path=path, index=index, strategy=strategy)
    _validate_strategy_reason_template(path=path, index=index, strategy=strategy)
    _validate_strategy_date_window(path=path, index=index, strategy=strategy)
    _validate_strategy_list_fields(path=path, taxonomy=taxonomy, index=index, strategy=strategy)
    _validate_strategy_slot_preferences(
        path=path,
        taxonomy=taxonomy,
        index=index,
        strategy=strategy,
        active_values_by_slot=active_values_by_slot,
    )


def _validate_element_records(
    path: Path,
    taxonomy: dict[str, Any],
    elements: list[dict[str, Any]],
) -> None:
    seen_active_element_ids: set[str] = set()
    seen_active_slot_values: set[tuple[str, str]] = set()
    for index, element in enumerate(elements):
        _validate_record_shape(path, index, element, _ELEMENT_REQUIRED_FIELDS, "element")
        if element.get("status") != "active":
            continue
        _validate_element_record(path=path, taxonomy=taxonomy, index=index, element=element)
        _validate_active_element_uniqueness(
            path=path,
            index=index,
            element=element,
            seen_active_element_ids=seen_active_element_ids,
            seen_active_slot_values=seen_active_slot_values,
        )


def _validate_strategy_template_records(
    path: Path,
    taxonomy: dict[str, Any],
    active_values_by_slot: dict[str, set[str]],
    strategies: list[dict[str, Any]],
) -> None:
    seen_active_strategy_ids: set[str] = set()
    for index, strategy in enumerate(strategies):
        _validate_record_shape(path, index, strategy, _STRATEGY_REQUIRED_FIELDS, "strategy")
        if strategy.get("status") != "active":
            continue
        _validate_active_strategy_uniqueness(
            path=path,
            index=index,
            strategy=strategy,
            seen_active_strategy_ids=seen_active_strategy_ids,
        )
        _validate_strategy_record(
            path=path,
            index=index,
            strategy=strategy,
            taxonomy=taxonomy,
            active_values_by_slot=active_values_by_slot,
        )


def _load_record_array(
    path: Path,
    root_message: str,
    array_field: str,
    array_message: str,
) -> list[dict[str, Any]]:
    payload = _load_json_object(path=path, root_message=root_message)
    values = payload.get(array_field)
    if not isinstance(values, list):
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message=array_message,
            details={"path": str(path)},
        )
    return list(values)


def _load_json_object(path: Path, root_message: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message=root_message,
            details={"path": str(path)},
        )
    return payload


def _validate_record_shape(
    path: Path,
    index: int,
    record: Any,
    required_fields: set[str],
    record_type: str,
) -> None:
    if not isinstance(record, dict):
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message=f"{record_type} record must be an object",
            details={"path": str(path), "index": index},
        )
    missing = sorted(required_fields.difference(record.keys()))
    if missing:
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message=f"{record_type} record is missing required fields",
            details={"path": str(path), "index": index, "missing": missing},
        )


def _validate_active_element_uniqueness(
    path: Path,
    index: int,
    element: dict[str, Any],
    seen_active_element_ids: set[str],
    seen_active_slot_values: set[tuple[str, str]],
) -> None:
    element_id = str(element["element_id"])
    if element_id in seen_active_element_ids:
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message="active element duplicates an existing element_id record",
            details={"path": str(path), "index": index, "element_id": element_id},
        )
    seen_active_element_ids.add(element_id)
    slot_value = _canonicalize_slot_value(
        slot=str(element["slot"]),
        value=str(element["value"]),
    )
    if slot_value in seen_active_slot_values:
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message="active element duplicates an existing slot/value record",
            details={"path": str(path), "index": index, "slot": str(element["slot"]), "value": str(element["value"])},
        )
    seen_active_slot_values.add(slot_value)


def _validate_active_strategy_uniqueness(
    path: Path,
    index: int,
    strategy: dict[str, Any],
    seen_active_strategy_ids: set[str],
) -> None:
    strategy_id = str(strategy["strategy_id"])
    if strategy_id in seen_active_strategy_ids:
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message="active strategy duplicates an existing strategy_id record",
            details={"path": str(path), "index": index, "field": "strategy_id", "strategy_id": strategy_id},
        )
    seen_active_strategy_ids.add(strategy_id)


def _collect_strategy_suppress_tags(selected_strategies: tuple[SelectedStrategy, ...]) -> set[str]:
    return {
        tag
        for selected in selected_strategies
        for tag in selected.strategy.suppress_tags
    }


def _is_candidate_element_eligible(
    request: NormalizedRequest,
    element: dict[str, Any],
    strategy_suppress_tags: set[str],
) -> tuple[bool, set[str]]:
    if element.get("status") != "active" or element.get("category") != request.category:
        return False, set()
    if not _matches_price_band(request, element):
        return False, set()
    tags = set(element.get("tags", []))
    matched_avoid_tags = tags.intersection(request.avoid_tags) if request.avoid_tags else set()
    if matched_avoid_tags:
        return False, matched_avoid_tags
    if strategy_suppress_tags and tags.intersection(strategy_suppress_tags):
        return False, set()
    return True, set()


def _build_scored_candidate(
    request: NormalizedRequest,
    element: dict[str, Any],
    selected_strategies: tuple[SelectedStrategy, ...],
) -> dict[str, Any]:
    candidate = dict(element)
    candidate["effective_score"] = round(
        _calculate_effective_score(
            request=request,
            element=element,
            selected_strategies=selected_strategies,
        ),
        4,
    )
    return candidate


def _calculate_effective_score(
    request: NormalizedRequest,
    element: dict[str, Any],
    selected_strategies: tuple[SelectedStrategy, ...],
) -> float:
    effective_score = float(element["base_score"])
    tags = set(element.get("tags", []))
    matching_strategies = _matching_strategies_for_element(selected_strategies, element, tags)
    if matching_strategies:
        effective_score += min(
            sum(item.strategy.score_boost for item in matching_strategies) / len(selected_strategies),
            sum(item.strategy.score_cap for item in matching_strategies) / len(matching_strategies),
        )
    if request.must_have_tags and tags.intersection(request.must_have_tags):
        effective_score += 0.02
    return effective_score


def _matching_strategies_for_element(
    selected_strategies: tuple[SelectedStrategy, ...],
    element: dict[str, Any],
    tags: set[str],
) -> list[SelectedStrategy]:
    return [
        item
        for item in selected_strategies
        if tags.intersection(item.strategy.boost_tags)
        or _strategy_matches_element_value(item, element)
    ]


def _raise_if_no_candidates(
    request: NormalizedRequest,
    grouped: dict[str, list[dict[str, Any]]],
) -> None:
    if any(grouped.values()):
        return
    raise GenerationError(
        code="NO_CANDIDATES",
        message="no eligible dress elements found after filtering",
        details={"category": request.category, "avoid_tags": list(request.avoid_tags)},
    )


def _build_retrieval_warnings(
    avoid_filtered_count: int,
    avoid_matched_tags: set[str],
) -> tuple[str, ...]:
    if not avoid_filtered_count:
        return ()
    sorted_tags = ", ".join(sorted(avoid_matched_tags))
    return (f"avoid_tags removed: {sorted_tags} ({avoid_filtered_count} candidates)",)


def _validate_element_taxonomy_lists(
    path: Path,
    taxonomy: dict[str, Any],
    index: int,
    element: dict[str, Any],
) -> None:
    for field, taxonomy_field in (
        ("tags", "allowed_tags"),
        ("occasion_tags", "allowed_occasions"),
        ("season_tags", "allowed_seasons"),
        ("risk_flags", "allowed_risk_flags"),
    ):
        _validate_string_list_against_taxonomy(
            path=path,
            index=index,
            field=field,
            value=element.get(field),
            allowed_values=set(taxonomy[taxonomy_field]),
            record_type="element",
        )


def _validate_element_score(
    path: Path,
    taxonomy: dict[str, Any],
    index: int,
    element: dict[str, Any],
) -> None:
    base_score = element.get("base_score")
    if not isinstance(base_score, (int, float)):
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message="element field 'base_score' must be numeric",
            details={"path": str(path), "index": index, "field": "base_score"},
        )
    score_range = taxonomy["base_score"]
    if not score_range["min"] <= float(base_score) <= score_range["max"]:
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message="element base_score is outside the allowed taxonomy range",
            details={"path": str(path), "index": index, "field": "base_score", "value": base_score},
        )


def _validate_element_summary(
    path: Path,
    taxonomy: dict[str, Any],
    index: int,
    element: dict[str, Any],
) -> None:
    summary = element.get("evidence_summary")
    if not isinstance(summary, str):
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message="element evidence_summary must be a string",
            details={"path": str(path), "index": index, "field": "evidence_summary"},
        )
    summary_range = taxonomy["summary"]
    if not summary_range["min_length"] <= len(summary) <= summary_range["max_length"]:
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message="element evidence_summary is outside the allowed taxonomy range",
            details={"path": str(path), "index": index, "field": "evidence_summary", "length": len(summary)},
        )


def _validate_strategy_date_window(
    path: Path,
    index: int,
    strategy: dict[str, Any],
) -> None:
    date_window = strategy.get("date_window")
    if not isinstance(date_window, dict):
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message="strategy date_window must be an object",
            details={"path": str(path), "index": index, "field": "date_window"},
        )
    if not isinstance(date_window.get("start"), str) or not isinstance(date_window.get("end"), str):
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message="strategy date_window must include string start/end values",
            details={"path": str(path), "index": index, "field": "date_window"},
        )


def _validate_strategy_numeric_fields(
    path: Path,
    index: int,
    strategy: dict[str, Any],
) -> None:
    if not isinstance(strategy.get("priority"), int):
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message="strategy priority must be an integer",
            details={"path": str(path), "index": index, "field": "priority"},
        )
    for field in ("score_boost", "score_cap"):
        if not isinstance(strategy.get(field), (int, float)):
            raise GenerationError(
                code="INVALID_EVIDENCE_STORE",
                message=f"strategy {field} must be numeric",
                details={"path": str(path), "index": index, "field": field},
            )


def _validate_strategy_reason_template(
    path: Path,
    index: int,
    strategy: dict[str, Any],
) -> None:
    if isinstance(strategy.get("reason_template"), str):
        return
    raise GenerationError(
        code="INVALID_EVIDENCE_STORE",
        message="strategy reason_template must be a string",
        details={"path": str(path), "index": index, "field": "reason_template"},
    )


def _validate_strategy_list_fields(
    path: Path,
    taxonomy: dict[str, Any],
    index: int,
    strategy: dict[str, Any],
) -> None:
    for field in ("occasion_tags", "boost_tags", "suppress_tags", "prompt_hints"):
        _validate_string_list_field(
            path=path,
            index=index,
            field=field,
            value=strategy.get(field),
            record_type="strategy",
        )
    _validate_allowed_strings(
        path=path,
        index=index,
        field="occasion_tags",
        values=strategy["occasion_tags"],
        allowed_values=set(taxonomy["allowed_occasions"]),
        record_type="strategy",
    )
    for field in ("boost_tags", "suppress_tags"):
        _validate_allowed_strings(
            path=path,
            index=index,
            field=field,
            values=strategy[field],
            allowed_values=set(taxonomy["allowed_tags"]),
            record_type="strategy",
        )


def _validate_strategy_slot_preferences(
    path: Path,
    taxonomy: dict[str, Any],
    index: int,
    strategy: dict[str, Any],
    active_values_by_slot: dict[str, set[str]],
) -> None:
    slot_preferences = strategy.get("slot_preferences")
    if not isinstance(slot_preferences, dict):
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message="strategy slot_preferences must be an object",
            details={"path": str(path), "index": index, "field": "slot_preferences"},
        )
    for slot, values in slot_preferences.items():
        _validate_strategy_slot_preference_entry(
            path=path,
            taxonomy=taxonomy,
            index=index,
            slot=slot,
            values=values,
            active_values_by_slot=active_values_by_slot,
        )


def _validate_strategy_slot_preference_entry(
    path: Path,
    taxonomy: dict[str, Any],
    index: int,
    slot: Any,
    values: Any,
    active_values_by_slot: dict[str, set[str]],
) -> None:
    if not isinstance(slot, str):
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message="strategy slot_preferences keys must be strings",
            details={"path": str(path), "index": index, "field": "slot_preferences"},
        )
    if slot not in taxonomy["allowed_slots"]:
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message="strategy slot_preferences references an unknown slot",
            details={"path": str(path), "index": index, "field": "slot_preferences", "slot": slot},
        )
    if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message="strategy slot_preferences values must be arrays of strings",
            details={"path": str(path), "index": index, "field": "slot_preferences"},
        )
    unknown_values = _unknown_slot_preference_values(slot, values, active_values_by_slot)
    if unknown_values:
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message="strategy slot_preferences references unknown active element values",
            details={"path": str(path), "index": index, "field": "slot_preferences", "slot": slot, "values": unknown_values},
        )


def _unknown_slot_preference_values(
    slot: str,
    values: list[str],
    active_values_by_slot: dict[str, set[str]],
) -> list[str]:
    canonical_slot = _canonicalize_value(slot)
    return sorted(
        value
        for value in values
        if _canonicalize_value(value) not in active_values_by_slot.get(canonical_slot, set())
    )


def _validate_string_list_against_taxonomy(
    path: Path,
    index: int,
    field: str,
    value: Any,
    allowed_values: set[str],
    record_type: str,
) -> None:
    _validate_string_list_field(
        path=path,
        index=index,
        field=field,
        value=value,
        record_type=record_type,
    )
    _validate_allowed_strings(
        path=path,
        index=index,
        field=field,
        values=value,
        allowed_values=allowed_values,
        record_type=record_type,
    )


def _validate_string_list_field(
    path: Path,
    index: int,
    field: str,
    value: Any,
    record_type: str,
) -> None:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message=f"{record_type} field '{field}' must be a list of strings",
            details={"path": str(path), "index": index, "field": field},
        )


def _validate_allowed_string(
    path: Path,
    index: int,
    field: str,
    value: Any,
    allowed_values: set[str],
    record_type: str,
) -> None:
    if not isinstance(value, str) or value not in allowed_values:
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message=f"{record_type} field '{field}' contains an unknown taxonomy value",
            details={"path": str(path), "index": index, "field": field, "value": value},
        )


def _validate_allowed_strings(
    path: Path,
    index: int,
    field: str,
    values: list[str],
    allowed_values: set[str],
    record_type: str,
) -> None:
    unknown_values = sorted(value for value in values if value not in allowed_values)
    if unknown_values:
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message=f"{record_type} field '{field}' contains unknown taxonomy values",
            details={"path": str(path), "index": index, "field": field, "values": unknown_values},
        )


def _build_active_values_by_slot(elements: list[dict[str, Any]]) -> dict[str, set[str]]:
    active_values_by_slot: dict[str, set[str]] = {}
    for element in elements:
        if element.get("status") != "active":
            continue
        slot, value = _canonicalize_slot_value(
            slot=str(element["slot"]),
            value=str(element["value"]),
        )
        active_values_by_slot.setdefault(slot, set()).add(value)
    return active_values_by_slot


def _strategy_matches_element_value(selected: SelectedStrategy, element: dict[str, Any]) -> bool:
    slot, value = _canonicalize_slot_value(
        slot=str(element.get("slot")),
        value=str(element.get("value")),
    )
    return value in {
        _canonicalize_value(candidate)
        for preference_slot, candidates in selected.strategy.slot_preferences.items()
        if _canonicalize_value(preference_slot) == slot
        for candidate in candidates
    }


def _canonicalize_value(value: str) -> str:
    return value.strip().casefold()
