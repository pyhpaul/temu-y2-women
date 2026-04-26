from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from temu_y2_women.errors import GenerationError
from temu_y2_women.models import CandidateElement, NormalizedRequest, SelectedStrategy

_DEFAULT_ELEMENTS_PATH = Path("data/mvp/dress/elements.json")
_DEFAULT_STRATEGIES_PATH = Path("data/mvp/dress/strategy_templates.json")
_DEFAULT_TAXONOMY_PATH = Path("data/mvp/dress/evidence_taxonomy.json")


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
    payload = json.loads(path.read_text(encoding="utf-8"))
    elements = payload.get("elements")
    if not isinstance(elements, list):
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message="elements evidence store must contain an 'elements' array",
            details={"path": str(path)},
        )
    required_fields = {
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
    seen_active_element_ids: set[str] = set()
    seen_active_slot_values: set[tuple[str, str]] = set()
    for index, element in enumerate(elements):
        if not isinstance(element, dict):
            raise GenerationError(
                code="INVALID_EVIDENCE_STORE",
                message="element record must be an object",
                details={"path": str(path), "index": index},
            )
        missing = sorted(required_fields.difference(element.keys()))
        if missing:
            raise GenerationError(
                code="INVALID_EVIDENCE_STORE",
                message="element record is missing required fields",
                details={"path": str(path), "index": index, "missing": missing},
            )
        _validate_element_record(path=path, taxonomy=taxonomy, index=index, element=element)
        if element.get("status") != "active":
            continue
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
                details={
                    "path": str(path),
                    "index": index,
                    "slot": str(element["slot"]),
                    "value": str(element["value"]),
                },
            )
        seen_active_slot_values.add(slot_value)
    return list(elements)


def load_strategy_templates(
    path: Path = _DEFAULT_STRATEGIES_PATH,
    taxonomy_path: Path = _DEFAULT_TAXONOMY_PATH,
    elements_path: Path = _DEFAULT_ELEMENTS_PATH,
) -> list[dict[str, Any]]:
    taxonomy = load_evidence_taxonomy(taxonomy_path)
    active_values_by_slot = _build_active_values_by_slot(
        load_elements(elements_path, taxonomy_path=taxonomy_path)
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    strategies = payload.get("strategy_templates")
    if not isinstance(strategies, list):
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message="strategy evidence store must contain a 'strategy_templates' array",
            details={"path": str(path)},
        )
    required_fields = {
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
    for index, strategy in enumerate(strategies):
        if not isinstance(strategy, dict):
            raise GenerationError(
                code="INVALID_EVIDENCE_STORE",
                message="strategy record must be an object",
                details={"path": str(path), "index": index},
            )
        missing = sorted(required_fields.difference(strategy.keys()))
        if missing:
            raise GenerationError(
                code="INVALID_EVIDENCE_STORE",
                message="strategy record is missing required fields",
                details={"path": str(path), "index": index, "missing": missing},
            )
        _validate_strategy_record(
            path=path,
            index=index,
            strategy=strategy,
            taxonomy=taxonomy,
            active_values_by_slot=active_values_by_slot,
        )
    return list(strategies)


def retrieve_candidates(
    request: NormalizedRequest,
    elements: list[dict[str, Any]],
    selected_strategies: tuple[SelectedStrategy, ...],
) -> tuple[dict[str, list[dict[str, Any]]], tuple[str, ...]]:
    strategy_boost_tags = {
        tag
        for selected in selected_strategies
        for tag in selected.strategy.boost_tags
    }
    strategy_suppress_tags = {
        tag
        for selected in selected_strategies
        for tag in selected.strategy.suppress_tags
    }
    grouped: dict[str, list[dict[str, Any]]] = {}
    avoid_filtered_count = 0
    avoid_matched_tags: set[str] = set()
    for element in elements:
        if element.get("status") != "active" or element.get("category") != request.category:
            continue
        if not _matches_price_band(request, element):
            continue
        tags = set(element.get("tags", []))
        if request.avoid_tags and tags.intersection(request.avoid_tags):
            avoid_filtered_count += 1
            avoid_matched_tags.update(tags.intersection(request.avoid_tags))
            continue
        if strategy_suppress_tags and tags.intersection(strategy_suppress_tags):
            continue

        effective_score = float(element["base_score"])
        matching_boosts = [
            item.strategy.score_boost
            for item in selected_strategies
            if tags.intersection(item.strategy.boost_tags)
            or _strategy_matches_element_value(item, element)
        ]
        matching_caps = [
            item.strategy.score_cap
            for item in selected_strategies
            if tags.intersection(item.strategy.boost_tags)
            or _strategy_matches_element_value(item, element)
        ]
        if matching_boosts:
            averaged_boost = sum(matching_boosts) / len(selected_strategies)
            effective_score += min(
                averaged_boost,
                sum(matching_caps) / len(matching_caps),
            )
        if request.must_have_tags and tags.intersection(request.must_have_tags):
            effective_score += 0.02

        candidate = dict(element)
        candidate["effective_score"] = round(effective_score, 4)
        grouped.setdefault(str(element["slot"]), []).append(candidate)

    if not any(grouped.values()):
        raise GenerationError(
            code="NO_CANDIDATES",
            message="no eligible dress elements found after filtering",
            details={"category": request.category, "avoid_tags": list(request.avoid_tags)},
        )

    warnings: list[str] = []
    if avoid_filtered_count:
        sorted_tags = ", ".join(sorted(avoid_matched_tags))
        warnings.append(f"avoid_tags removed: {sorted_tags} ({avoid_filtered_count} candidates)")

    return grouped, tuple(warnings)


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
    _validate_string_list_field(path=path, index=index, field="tags", value=element.get("tags"), record_type="element")
    _validate_allowed_strings(
        path=path,
        index=index,
        field="tags",
        values=element["tags"],
        allowed_values=set(taxonomy["allowed_tags"]),
        record_type="element",
    )
    _validate_string_list_field(
        path=path,
        index=index,
        field="occasion_tags",
        value=element.get("occasion_tags"),
        record_type="element",
    )
    _validate_allowed_strings(
        path=path,
        index=index,
        field="occasion_tags",
        values=element["occasion_tags"],
        allowed_values=set(taxonomy["allowed_occasions"]),
        record_type="element",
    )
    _validate_string_list_field(
        path=path,
        index=index,
        field="season_tags",
        value=element.get("season_tags"),
        record_type="element",
    )
    _validate_allowed_strings(
        path=path,
        index=index,
        field="season_tags",
        values=element["season_tags"],
        allowed_values=set(taxonomy["allowed_seasons"]),
        record_type="element",
    )
    _validate_string_list_field(
        path=path,
        index=index,
        field="risk_flags",
        value=element.get("risk_flags"),
        record_type="element",
    )
    _validate_allowed_strings(
        path=path,
        index=index,
        field="risk_flags",
        values=element["risk_flags"],
        allowed_values=set(taxonomy["allowed_risk_flags"]),
        record_type="element",
    )
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


def _validate_strategy_record(
    path: Path,
    index: int,
    strategy: dict[str, Any],
    taxonomy: dict[str, Any],
    active_values_by_slot: dict[str, set[str]],
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

    for list_field in ("occasion_tags", "boost_tags", "suppress_tags", "prompt_hints"):
        _validate_string_list_field(
            path=path,
            index=index,
            field=list_field,
            value=strategy.get(list_field),
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
    for list_field in ("boost_tags", "suppress_tags"):
        _validate_allowed_strings(
            path=path,
            index=index,
            field=list_field,
            values=strategy[list_field],
            allowed_values=set(taxonomy["allowed_tags"]),
            record_type="strategy",
        )

    slot_preferences = strategy.get("slot_preferences")
    if not isinstance(slot_preferences, dict):
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message="strategy slot_preferences must be an object",
            details={"path": str(path), "index": index, "field": "slot_preferences"},
        )
    for key, value in slot_preferences.items():
        if not isinstance(key, str):
            raise GenerationError(
                code="INVALID_EVIDENCE_STORE",
                message="strategy slot_preferences keys must be strings",
                details={"path": str(path), "index": index, "field": "slot_preferences"},
            )
        if key not in taxonomy["allowed_slots"]:
            raise GenerationError(
                code="INVALID_EVIDENCE_STORE",
                message="strategy slot_preferences references an unknown slot",
                details={"path": str(path), "index": index, "field": "slot_preferences", "slot": key},
            )
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise GenerationError(
                code="INVALID_EVIDENCE_STORE",
                message="strategy slot_preferences values must be arrays of strings",
                details={"path": str(path), "index": index, "field": "slot_preferences"},
            )
        canonical_slot = _canonicalize_value(key)
        unknown_values = sorted(
            item
            for item in value
            if _canonicalize_value(item) not in active_values_by_slot.get(canonical_slot, set())
        )
        if unknown_values:
            raise GenerationError(
                code="INVALID_EVIDENCE_STORE",
                message="strategy slot_preferences references unknown active element values",
                details={
                    "path": str(path),
                    "index": index,
                    "field": "slot_preferences",
                    "slot": key,
                    "values": unknown_values,
                },
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
