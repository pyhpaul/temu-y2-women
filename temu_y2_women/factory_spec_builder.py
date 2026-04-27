from __future__ import annotations

from typing import Any

from temu_y2_women.models import ComposedConcept, NormalizedRequest, SelectedStrategy

_SCHEMA_VERSION = "factory-spec-v1"
_UNRESOLVED_FIELDS = (
    "fiber_content",
    "fabric_weight_gsm",
    "lining",
    "closure_details",
    "measurements_pom",
    "seam_allowance",
    "tolerance",
    "bom_grade_trim",
)
_FABRIC_REVIEW_RULES = {
    "cotton poplin": (
        "confirm crisp texture, opacity, and print clarity for cotton poplin",
        "check drape stays light and controlled rather than clingy",
    ),
}
_DETAIL_REVIEW_RULES = {
    "smocked bodice": (
        "verify smocking stitch consistency, recovery, and clean attachment",
        "confirm bodice tension stays even without distorting print placement",
    ),
}


def build_factory_spec(
    request: NormalizedRequest,
    concept: ComposedConcept,
    selected_strategies: tuple[SelectedStrategy, ...],
) -> dict[str, Any]:
    return {
        "schema_version": _SCHEMA_VERSION,
        "known": _known_section(request, concept, selected_strategies),
        "inferred": _inferred_section(request, concept, selected_strategies),
        "unresolved": list(_UNRESOLVED_FIELDS),
    }


def _known_section(
    request: NormalizedRequest,
    concept: ComposedConcept,
    selected_strategies: tuple[SelectedStrategy, ...],
) -> dict[str, Any]:
    return {
        "category": concept.category,
        "target_market": request.target_market,
        "target_launch_date": request.target_launch_date.isoformat(),
        "price_band": request.price_band,
        "occasion_tags": list(request.occasion_tags),
        "must_have_tags": list(request.must_have_tags),
        "avoid_tags": list(request.avoid_tags),
        "selected_strategy_ids": [item.strategy.strategy_id for item in selected_strategies],
        "selected_elements": {
            slot: {"element_id": element.element_id, "value": element.value}
            for slot, element in concept.selected_elements.items()
        },
    }


def _inferred_section(
    request: NormalizedRequest,
    concept: ComposedConcept,
    selected_strategies: tuple[SelectedStrategy, ...],
) -> dict[str, list[str]]:
    return {
        "fit_intent": _fit_intent_notes(request, concept),
        "fabric_review_focus": _fabric_review_focus(concept),
        "detail_review_focus": _detail_review_focus(concept),
        "visible_construction_priorities": _visible_construction_priorities(concept),
        "commercial_review_context": _commercial_review_context(request, selected_strategies),
    }


def _fit_intent_notes(
    request: NormalizedRequest,
    concept: ComposedConcept,
) -> list[str]:
    notes: list[str] = []
    if "bodycon" in request.avoid_tags:
        notes.append("non-bodycon fit requested by avoid_tags")
    if _selected_value(concept, "silhouette") == "a-line":
        notes.append("a-line silhouette supports easy skirt volume and commercial mobility")
    if _selected_value(concept, "detail") == "smocked bodice":
        notes.append("smocked bodice should keep waist shaping flexible rather than restrictive")
    if notes:
        return notes
    return ["fit intent should stay commercially wearable for the selected market"]


def _fabric_review_focus(concept: ComposedConcept) -> list[str]:
    fabric = _selected_value(concept, "fabric")
    if fabric in _FABRIC_REVIEW_RULES:
        return list(_FABRIC_REVIEW_RULES[fabric])
    return [
        "confirm the selected fabric keeps visible texture and stable color clarity",
        "check drape and opacity stay commercially realistic for the concept category",
    ]


def _detail_review_focus(concept: ComposedConcept) -> list[str]:
    detail = _selected_value(concept, "detail")
    if detail in _DETAIL_REVIEW_RULES:
        return list(_DETAIL_REVIEW_RULES[detail])
    return [
        "verify the visible construction detail is cleanly attached and repeatable in production",
        "confirm detail placement does not distort the garment balance or print layout",
    ]


def _visible_construction_priorities(concept: ComposedConcept) -> list[str]:
    priorities = [
        "neckline edge finish",
        "bodice construction consistency",
        "sleeve opening clean finish",
        "waist seam position",
        "hem clean finish",
    ]
    if _selected_value(concept, "pattern"):
        priorities.append("print continuity across seams")
    if _selected_value(concept, "detail"):
        priorities.append("detail placement symmetry")
    return priorities


def _commercial_review_context(
    request: NormalizedRequest,
    selected_strategies: tuple[SelectedStrategy, ...],
) -> list[str]:
    context: list[str] = []
    if selected_strategies:
        context.append(f"seasonal review context: {selected_strategies[0].reason}")
    if request.occasion_tags:
        context.append(
            f"occasion review context: align construction readability to {'/'.join(request.occasion_tags)} use"
        )
    if request.price_band:
        context.append(
            f"price-band review context: keep construction commercially realistic for {request.price_band} pricing"
        )
    return context


def _selected_value(concept: ComposedConcept, slot: str) -> str:
    element = concept.selected_elements.get(slot)
    return "" if element is None else element.value
