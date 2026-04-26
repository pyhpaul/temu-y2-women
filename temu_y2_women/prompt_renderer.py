from __future__ import annotations

from temu_y2_women.models import ComposedConcept, NormalizedRequest, SelectedStrategy


def render_prompt_bundle(
    request: NormalizedRequest,
    concept: ComposedConcept,
    selected_strategies: tuple[SelectedStrategy, ...],
    warnings: tuple[str, ...],
) -> dict[str, object]:
    development_notes = list(
        concept.style_summary or warnings or ("dress MVP development guidance",)
    )
    prompt = _build_prompt(
        request=request,
        concept=concept,
        selected_strategies=selected_strategies,
        development_notes=development_notes,
    )

    if request.mode == "A":
        return {
            "mode": "A",
            "prompt": prompt,
            "render_notes": [
                "focus on product appeal",
                "keep summer seasonal styling",
            ],
        }

    return {
            "mode": "B",
            "prompt": prompt,
            "render_notes": [
                "emphasize garment construction clarity",
                "make silhouette and neckline explicit",
            ],
            "development_notes": development_notes,
        }


def _build_prompt(
    request: NormalizedRequest,
    concept: ComposedConcept,
    selected_strategies: tuple[SelectedStrategy, ...],
    development_notes: list[str],
) -> str:
    subject_line = (
        f"women's {request.target_market} market {concept.category}, "
        f"launch-aligned concept for {request.target_launch_date.isoformat()}"
    )
    structure_line = "; ".join(
        f"{slot}: {element.value}"
        for slot, element in concept.selected_elements.items()
    )
    style_line = "; ".join(_style_items(request, concept, selected_strategies))
    display_line = _display_line(request, development_notes)
    constraints_line = "; ".join(_constraint_items(request, concept))

    return "\n".join(
        (
            f"[商品主体] {subject_line}",
            f"[核心结构] {structure_line}",
            f"[风格与时效] {style_line}",
            f"[展示方式] {display_line}",
            f"[约束与避免项] {constraints_line}",
        )
    )


def _style_items(
    request: NormalizedRequest,
    concept: ComposedConcept,
    selected_strategies: tuple[SelectedStrategy, ...],
) -> list[str]:
    style_items: list[str] = []
    if request.price_band:
        style_items.append(f"price band: {request.price_band}")
    if request.occasion_tags:
        style_items.append(f"occasion focus: {', '.join(request.occasion_tags)}")
    for selected in selected_strategies:
        for hint in selected.strategy.prompt_hints:
            if hint not in style_items:
                style_items.append(hint)
    for summary in concept.style_summary:
        if summary not in style_items:
            style_items.append(summary)
    return style_items or ["stable seasonal direction"]


def _display_line(request: NormalizedRequest, development_notes: list[str]) -> str:
    if request.mode == "A":
        return (
            "hero ecommerce concept image; emphasize shopper appeal, outfit desirability, "
            "and clean product storytelling"
        )
    return (
        "development reference image; emphasize silhouette, neckline, sleeve, fabric, and finish clarity; "
        f"development notes: {'; '.join(development_notes)}"
    )


def _constraint_items(
    request: NormalizedRequest,
    concept: ComposedConcept,
) -> list[str]:
    constraint_items = list(concept.constraint_notes)
    if request.avoid_tags:
        constraint_items.append(f"avoid: {', '.join(request.avoid_tags)}")
    else:
        constraint_items.append("avoid: none")
    constraint_items.append("avoid off-brief styling drift")
    return constraint_items
