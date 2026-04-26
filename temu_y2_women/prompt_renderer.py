from __future__ import annotations

from temu_y2_women.models import ComposedConcept, NormalizedRequest, SelectedStrategy


def render_prompt_bundle(
    request: NormalizedRequest,
    concept: ComposedConcept,
    selected_strategies: tuple[SelectedStrategy, ...],
    warnings: tuple[str, ...],
) -> dict[str, object]:
    subject = f"women's {request.target_market} market {concept.category}"
    structure = ", ".join(
        element.value for element in concept.selected_elements.values()
    )
    style_hints = ", ".join(
        hint
        for selected in selected_strategies
        for hint in selected.strategy.prompt_hints
    )
    avoid_clause = ", ".join(request.avoid_tags) if request.avoid_tags else "no excluded styling"
    prompt = (
        f"{subject}; core structure: {structure}; "
        f"seasonal direction: {style_hints}; "
        f"avoid: {avoid_clause}"
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
        "development_notes": list(concept.style_summary or warnings or ("dress MVP development guidance",)),
    }
