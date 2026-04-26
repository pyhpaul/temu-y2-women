from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date
from typing import Any

from temu_y2_women.models import ComposedConcept, NormalizedRequest, SelectedStrategy


def package_success_result(
    request: NormalizedRequest,
    selected_strategies: tuple[SelectedStrategy, ...],
    retrieved_elements: list[dict[str, Any]],
    composed_concept: ComposedConcept,
    prompt_bundle: dict[str, Any],
    warnings: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "request_normalized": _request_to_dict(request),
        "selected_strategies": [
            {
                "strategy_id": item.strategy.strategy_id,
                "reason": item.reason,
                "prompt_hints": list(item.strategy.prompt_hints),
            }
            for item in selected_strategies
        ],
        "retrieved_elements": retrieved_elements,
        "composed_concept": _concept_to_dict(composed_concept),
        "prompt_bundle": prompt_bundle,
        "warnings": list(warnings),
    }


def _request_to_dict(request: NormalizedRequest) -> dict[str, Any]:
    return {
        "category": request.category,
        "target_market": request.target_market,
        "target_launch_date": request.target_launch_date.isoformat(),
        "mode": request.mode,
        "price_band": request.price_band,
        "occasion_tags": list(request.occasion_tags),
        "must_have_tags": list(request.must_have_tags),
        "avoid_tags": list(request.avoid_tags),
    }


def _concept_to_dict(concept: ComposedConcept) -> dict[str, Any]:
    return {
        "category": concept.category,
        "concept_score": concept.concept_score,
        "selected_elements": {
            slot: {"element_id": element.element_id, "value": element.value}
            for slot, element in concept.selected_elements.items()
        },
        "style_summary": list(concept.style_summary),
        "constraint_notes": list(concept.constraint_notes),
    }
