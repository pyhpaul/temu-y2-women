from __future__ import annotations

from temu_y2_women.models import ComposedConcept, NormalizedRequest, SelectedStrategy

_HERO_JOB_SPECS = (
    ("hero_front", "hero_front.png", "front view"),
    ("hero_three_quarter", "hero_three_quarter.png", "three-quarter view"),
    ("hero_back", "hero_back.png", "back view"),
)

_DETAIL_JOB_SPECS = (
    ("construction_closeup", "construction_closeup.png"),
    ("fabric_print_closeup", "fabric_print_closeup.png"),
    ("hem_and_drape_closeup", "hem_and_drape_closeup.png"),
)


def render_prompt_bundle(
    request: NormalizedRequest,
    concept: ComposedConcept,
    selected_strategies: tuple[SelectedStrategy, ...],
    warnings: tuple[str, ...],
) -> dict[str, object]:
    development_notes = list(concept.style_summary or warnings or ("dress MVP development guidance",))
    render_jobs = _render_jobs(request, concept, selected_strategies, development_notes)
    bundle: dict[str, object] = {
        "mode": request.mode,
        "prompt": render_jobs[0]["prompt"],
        "template_version": "visual-prompt-v2",
        "render_notes": _render_notes(request.mode),
        "render_jobs": render_jobs,
        "detail_prompts": _detail_prompts(render_jobs),
    }
    if request.mode == "B":
        bundle["development_notes"] = development_notes
    return bundle


def _render_notes(mode: str) -> list[str]:
    if mode == "A":
        return [
            "prioritize product-first presentation",
            "keep garment construction realistic",
        ]
    return [
        "prioritize construction review clarity",
        "make seam placement and fabric behavior explicit",
    ]


def _build_prompt(
    request: NormalizedRequest,
    concept: ComposedConcept,
    selected_strategies: tuple[SelectedStrategy, ...],
    development_notes: list[str],
    shot_line: str,
) -> str:
    return "\n".join(
        (
            f"[商品主体] {_subject_line(request, concept)}",
            f"[核心结构] {_structure_line(request, concept)}",
            f"[生产与细节展示要求] {_detail_requirements_line(request, selected_strategies, development_notes)}",
            f"[镜头与构图] {shot_line}",
            f"[面料与工艺表现] {_material_line(concept)}",
            f"[场景与光线] {_scene_line(request)}",
            f"[约束与避免项] {_constraint_line(request)}",
        )
    )


def _subject_line(request: NormalizedRequest, concept: ComposedConcept) -> str:
    if request.mode == "A":
        return (
            f"women's {_occasion_phrase(request)} {concept.category} for the {request.target_market} market, "
            "on-model ecommerce hero image, product-first presentation"
        )
    return (
        f"women's {concept.category} development reference image for the {request.target_market} market, "
        "production-review presentation"
    )


def _occasion_phrase(request: NormalizedRequest) -> str:
    if request.occasion_tags:
        return " ".join(request.occasion_tags)
    return "seasonal"


def _structure_line(request: NormalizedRequest, concept: ComposedConcept) -> str:
    items = [_element_phrase(slot, element.value) for slot, element in concept.selected_elements.items()]
    if "bodycon" in request.avoid_tags:
        items.append("non-bodycon fit")
    return "; ".join(items)


def _element_phrase(slot: str, value: str) -> str:
    if slot == "silhouette":
        return f"{value} silhouette"
    if slot == "fabric":
        return f"{value} fabric"
    if slot == "dress_length":
        return f"{value} length"
    if slot == "color_family":
        return f"{value} color story"
    if slot == "print_scale":
        return f"{value} scale"
    if slot == "opacity_level":
        return "sheer overlay effect" if value == "sheer" else f"{value} coverage"
    return value


def _detail_requirements_line(
    request: NormalizedRequest,
    selected_strategies: tuple[SelectedStrategy, ...],
    development_notes: list[str],
) -> str:
    items = [
        "clearly show neckline depth, bodice construction, sleeve opening, waist seam position, skirt volume, hem finish, floral print scale, and fabric texture",
        "keep the garment visually realistic and feasible for factory production",
    ]
    if request.mode == "B":
        items.append(f"development notes: {'; '.join(development_notes)}")
    elif selected_strategies:
        items.append(f"seasonal direction: {selected_strategies[0].reason}")
    return "; ".join(items)


def _render_jobs(
    request: NormalizedRequest,
    concept: ComposedConcept,
    selected_strategies: tuple[SelectedStrategy, ...],
    development_notes: list[str],
) -> list[dict[str, str]]:
    return _hero_jobs(request, concept, selected_strategies, development_notes) + _detail_jobs(concept)


def _hero_jobs(
    request: NormalizedRequest,
    concept: ComposedConcept,
    selected_strategies: tuple[SelectedStrategy, ...],
    development_notes: list[str],
) -> list[dict[str, str]]:
    jobs: list[dict[str, str]] = []
    for prompt_id, output_name, angle in _HERO_JOB_SPECS:
        jobs.append(
            {
                "prompt_id": prompt_id,
                "group": "hero",
                "output_name": output_name,
                "prompt": _hero_prompt(
                    request,
                    concept,
                    selected_strategies,
                    development_notes,
                    prompt_id,
                    angle,
                ),
                "render_strategy": _hero_render_strategy(prompt_id),
                "reference_prompt_id": _hero_reference_prompt_id(prompt_id),
            }
        )
    return jobs


def _hero_prompt(
    request: NormalizedRequest,
    concept: ComposedConcept,
    selected_strategies: tuple[SelectedStrategy, ...],
    development_notes: list[str],
    prompt_id: str,
    angle: str,
) -> str:
    if prompt_id == "hero_front":
        return _build_prompt(
            request,
            concept,
            selected_strategies,
            development_notes,
            _hero_shot_line(request, angle),
        )
    return _hero_edit_instruction(request, concept, angle)


def _hero_render_strategy(prompt_id: str) -> str:
    if prompt_id == "hero_front":
        return "generate"
    return "edit"


def _hero_reference_prompt_id(prompt_id: str) -> str | None:
    if prompt_id == "hero_front":
        return None
    return "hero_front"


def _hero_shot_line(request: NormalizedRequest, angle: str) -> str:
    if request.mode == "A":
        return (
            f"full-body; vertical 4:5; eye-level camera; {angle}; centered composition; "
            "full dress visible from shoulder to hem; clean negative space"
        )
    return (
        f"full-body; vertical 4:5; eye-level camera; {angle}; "
        "full dress visible from shoulder to hem; neutral review framing"
    )


def _material_line(concept: ComposedConcept) -> str:
    fabric_text = _selected_value(concept, "fabric", "dress fabric")
    pattern_text = _selected_value(concept, "pattern", "surface print")
    detail_text = _selected_value(concept, "detail", "construction detail")
    color_text = _selected_value(concept, "color_family", "commercial color")
    print_scale_text = _element_phrase("print_scale", _selected_value(concept, "print_scale", "commercial print"))
    opacity_text = _element_phrase("opacity_level", _selected_value(concept, "opacity_level", "opaque"))
    return (
        f"crisp {fabric_text} texture; visible {detail_text}; visible seam lines; clean hem finish; "
        f"true-to-color {color_text}; visible {pattern_text}; {print_scale_text}; {opacity_text}; natural drape; "
        "commercially realistic construction"
    )


def _scene_line(request: NormalizedRequest) -> str:
    if "vacation" in request.occasion_tags:
        return "clean sunlit resort-inspired studio; soft directional daylight; warm ivory and sand background; minimal props"
    if request.mode == "B":
        return "clean neutral studio; soft commercial lighting; background kept quiet for production review"
    return "clean studio; soft commercial lighting; quiet background that supports the garment without competing"


def _constraint_line(request: NormalizedRequest) -> str:
    items = ["no text", "no watermark", "no cluttered background", "no unrealistic garment construction"]
    if "bodycon" in request.avoid_tags:
        items.insert(0, "no bodycon fit")
    for tag in request.avoid_tags:
        if tag != "bodycon":
            items.append(f"avoid {tag} styling")
    items.extend(("no jacket", "no cardigan", "no bag covering the bodice", "no exaggerated editorial pose"))
    return "; ".join(items)


def _detail_jobs(concept: ComposedConcept) -> list[dict[str, str]]:
    prompts = {
        "construction_closeup": _construction_edit_instruction(concept),
        "fabric_print_closeup": _fabric_edit_instruction(concept),
        "hem_and_drape_closeup": _hem_edit_instruction(concept),
    }
    jobs: list[dict[str, str]] = []
    for prompt_id, output_name in _DETAIL_JOB_SPECS:
        jobs.append(
            {
                "prompt_id": prompt_id,
                "group": "detail",
                "output_name": output_name,
                "prompt": prompts[prompt_id],
                "render_strategy": "edit",
                "reference_prompt_id": "hero_front",
            }
        )
    return jobs


def _detail_prompts(render_jobs: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {
            "prompt_id": item["prompt_id"],
            "prompt": item["prompt"],
            "render_strategy": item["render_strategy"],
            "reference_prompt_id": item["reference_prompt_id"],
        }
        for item in render_jobs
        if item["group"] == "detail"
    ]


def _hero_edit_instruction(request: NormalizedRequest, concept: ComposedConcept, angle: str) -> str:
    framing = "Preserve full-body framing from shoulder to hem, realistic construction, and clean negative space."
    if request.mode != "A":
        framing = "Preserve full-body framing, realistic construction, and neutral review presentation."
    return " ".join(
        (
            "Edit the reference image.",
            _identity_lock_line(concept),
            f"Only change the camera angle to a {angle}.",
            framing,
        )
    )


def _identity_lock_line(concept: ComposedConcept) -> str:
    fabric = _selected_value(concept, "fabric", "dress fabric")
    pattern = _selected_value(concept, "pattern", "surface print")
    color = _selected_value(concept, "color_family", "commercial color")
    detail = _selected_value(concept, "detail", "construction detail")
    return (
        "Keep the exact same dress, same model, same silhouette, "
        f"same {fabric} texture, same {pattern} placement, same {color} story, and same {detail}."
    )


def _construction_edit_instruction(concept: ComposedConcept) -> str:
    neckline = concept.selected_elements["neckline"].value
    detail = concept.selected_elements.get("detail", concept.selected_elements["fabric"]).value
    waistline = concept.selected_elements.get("waistline", concept.selected_elements["silhouette"]).value
    return " ".join(
        (
            "Edit the reference image.",
            _identity_lock_line(concept),
            f"Zoom into the {neckline}, {detail}, and waistline placement.",
            f"Clearly show {waistline}, seam lines, neckline edge finish, and bodice construction.",
            "Keep neutral studio lighting; no hands, no accessories, no text.",
        )
    )


def _fabric_edit_instruction(concept: ComposedConcept) -> str:
    fabric = concept.selected_elements["fabric"].value
    pattern = _selected_value(concept, "pattern", "solid color")
    print_scale = _element_phrase("print_scale", _selected_value(concept, "print_scale", "commercial print"))
    opacity = _element_phrase("opacity_level", _selected_value(concept, "opacity_level", "opaque"))
    return " ".join(
        (
            "Edit the reference image.",
            _identity_lock_line(concept),
            f"Zoom into the {fabric} fabric surface.",
            f"Clearly show {pattern}, {print_scale}, {opacity}, weave texture, and color accuracy.",
            "Keep soft studio lighting and realistic surface detail; no blur, no props, no text.",
        )
    )


def _hem_edit_instruction(concept: ComposedConcept) -> str:
    silhouette = concept.selected_elements["silhouette"].value
    dress_length = _selected_value(concept, "dress_length", "balanced")
    pattern = _selected_value(concept, "pattern", "surface print")
    return " ".join(
        (
            "Edit the reference image.",
            _identity_lock_line(concept),
            "Zoom into the lower skirt and hem area.",
            f"Clearly show {dress_length} proportion, hem finish, {silhouette} skirt volume, seam transitions, drape, and {pattern} continuity.",
            "Keep the hem fully visible with a neutral background; no props, no text.",
        )
    )


def _selected_value(concept: ComposedConcept, slot: str, default: str) -> str:
    element = concept.selected_elements.get(slot)
    return default if element is None else element.value
