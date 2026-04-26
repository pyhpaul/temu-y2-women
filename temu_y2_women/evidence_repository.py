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
    return list(payload.get("elements", []))


def load_strategy_templates(path: Path = _DEFAULT_STRATEGIES_PATH) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return list(payload.get("strategy_templates", []))


def retrieve_candidates(
    request: NormalizedRequest,
    elements: list[dict[str, Any]],
    selected_strategies: tuple[SelectedStrategy, ...],
) -> dict[str, list[dict[str, Any]]]:
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
    for element in elements:
        if element.get("status") != "active" or element.get("category") != request.category:
            continue
        if not _matches_price_band(request, element):
            continue
        if not _matches_occasion(request, element):
            continue

        tags = set(element.get("tags", []))
        if request.avoid_tags and tags.intersection(request.avoid_tags):
            continue
        if strategy_suppress_tags and tags.intersection(strategy_suppress_tags):
            continue

        effective_score = float(element["base_score"])
        if tags.intersection(strategy_boost_tags):
            effective_score += max((item.strategy.score_boost for item in selected_strategies), default=0.0)
        if element.get("value") in slot_preferences.get(element.get("slot"), set()):
            effective_score += 0.03
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

    return grouped


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


def _matches_occasion(request: NormalizedRequest, element: dict[str, Any]) -> bool:
    if not request.occasion_tags:
        return True
    element_tags = set(element.get("occasion_tags", []))
    return bool(element_tags.intersection(request.occasion_tags))
