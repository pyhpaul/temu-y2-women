from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from temu_y2_women.errors import GenerationError
from temu_y2_women.models import CandidateElement, NormalizedRequest, SelectedStrategy

_DEFAULT_ELEMENTS_PATH = Path("data/mvp/dress/elements.json")
_DEFAULT_STRATEGIES_PATH = Path("data/mvp/dress/strategy_templates.json")


def load_elements(path: Path = _DEFAULT_ELEMENTS_PATH) -> list[dict[str, Any]]:
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
    for index, element in enumerate(elements):
        missing = sorted(required_fields.difference(element.keys()))
        if missing:
            raise GenerationError(
                code="INVALID_EVIDENCE_STORE",
                message="element record is missing required fields",
                details={"path": str(path), "index": index, "missing": missing},
            )
    return list(elements)


def load_strategy_templates(path: Path = _DEFAULT_STRATEGIES_PATH) -> list[dict[str, Any]]:
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
        missing = sorted(required_fields.difference(strategy.keys()))
        if missing:
            raise GenerationError(
                code="INVALID_EVIDENCE_STORE",
                message="strategy record is missing required fields",
                details={"path": str(path), "index": index, "missing": missing},
            )
        _validate_strategy_record(path=path, index=index, strategy=strategy)
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
    slot_preferences = {
        slot: {
            value
            for selected in selected_strategies
            for value in selected.strategy.slot_preferences.get(slot, ())
        }
        for slot in ("silhouette", "fabric", "neckline", "sleeve", "pattern", "detail")
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
            or element.get("value") in item.strategy.slot_preferences.get(element.get("slot"), ())
        ]
        matching_caps = [
            item.strategy.score_cap
            for item in selected_strategies
            if tags.intersection(item.strategy.boost_tags)
            or element.get("value") in item.strategy.slot_preferences.get(element.get("slot"), ())
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


def _validate_strategy_record(path: Path, index: int, strategy: dict[str, Any]) -> None:
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
        value = strategy.get(list_field)
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise GenerationError(
                code="INVALID_EVIDENCE_STORE",
                message=f"strategy field '{list_field}' must be a list of strings",
                details={"path": str(path), "index": index, "field": list_field},
            )

    slot_preferences = strategy.get("slot_preferences")
    if not isinstance(slot_preferences, dict):
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message="strategy slot_preferences must be an object",
            details={"path": str(path), "index": index, "field": "slot_preferences"},
        )
    for key, value in slot_preferences.items():
        if not isinstance(key, str) or not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise GenerationError(
                code="INVALID_EVIDENCE_STORE",
                message="strategy slot_preferences values must be arrays of strings",
                details={"path": str(path), "index": index, "field": "slot_preferences"},
            )
