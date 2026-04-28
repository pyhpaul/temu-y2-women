from __future__ import annotations

from temu_y2_women.models import ComposedConcept, ComposedElement, NormalizedRequest, SelectedStrategy

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
        return _opacity_phrase(value)
    return value


def _opacity_phrase(value: str) -> str:
    if value == "sheer":
        return "sheer overlay effect"
    if value == "opaque":
        return "full-opacity coverage"
    return f"{value} opacity effect"


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
                "prompt": _build_prompt(
                    request,
                    concept,
                    selected_strategies,
                    development_notes,
                    _hero_shot_line(request, angle),
                ),
                "render_strategy": _hero_render_strategy(prompt_id),
                "reference_prompt_id": _hero_reference_prompt_id(prompt_id),
            }
        )
    return jobs


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
    fabric = concept.selected_elements.get("fabric", None)
    pattern = concept.selected_elements.get("pattern", None)
    detail = concept.selected_elements.get("detail", None)
    fabric_text = fabric.value if fabric else "dress fabric"
    pattern_text = pattern.value if pattern else "surface print"
    detail_text = detail.value if detail else "construction detail"
    return (
        f"crisp {fabric_text} texture; visible {detail_text}; visible seam lines; clean hem finish; "
        f"true-to-color {pattern_text}; natural drape; commercially realistic construction"
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
        "construction_closeup": _construction_prompt(concept),
        "fabric_print_closeup": _fabric_prompt(concept),
        "hem_and_drape_closeup": _hem_prompt(concept),
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


def _construction_prompt(concept: ComposedConcept) -> str:
    neckline = concept.selected_elements["neckline"].value
    detail = concept.selected_elements.get("detail", concept.selected_elements["fabric"]).value
    waistline = _waistline_phrase(concept)
    sleeve_opening = _sleeve_opening_phrase(concept)
    return (
        f"close-up ecommerce detail image of the {neckline}, {detail}, {waistline}, and {sleeve_opening}; "
        f"clearly show {waistline}, {sleeve_opening}, seam lines, neckline edge finish, and bodice construction; "
        "neutral studio background; no hands, no accessories, no text"
    )


def _fabric_prompt(concept: ComposedConcept) -> str:
    fabric = concept.selected_elements["fabric"].value
    pattern = _surface_phrase(concept)
    print_scale = _print_scale_phrase(concept)
    opacity = _opacity_phrase(concept.selected_elements.get("opacity_level", ComposedElement("", "opaque")).value)
    return (
        f"macro fabric detail image of {fabric} with {pattern} and {print_scale}; "
        f"clearly show {opacity}, print scale, weave texture, and color accuracy; "
        "soft studio lighting; no blur, no props, no text"
    )


def _hem_prompt(concept: ComposedConcept) -> str:
    dress_length = concept.selected_elements.get("dress_length", ComposedElement("", "balanced")).value
    silhouette = concept.selected_elements["silhouette"].value
    pattern = _surface_phrase(concept)
    return (
        f"close-up lower-skirt detail image of the {silhouette} dress with {dress_length} proportion; "
        f"clearly show hem finish, {dress_length} proportion, skirt volume, seam transitions, drape, "
        f"and {pattern} continuity; neutral background; no cropped hem edge, no props, no text"
    )


def _waistline_phrase(concept: ComposedConcept) -> str:
    waistline = concept.selected_elements.get("waistline")
    if waistline:
        return f"{waistline.value} waistline placement"
    return "waistline placement"


def _sleeve_opening_phrase(concept: ComposedConcept) -> str:
    sleeve = concept.selected_elements.get("sleeve")
    if sleeve:
        return f"{sleeve.value} opening finish"
    return "sleeve opening"


def _surface_phrase(concept: ComposedConcept) -> str:
    pattern = concept.selected_elements.get("pattern")
    if pattern:
        return pattern.value
    return "solid-color surface"


def _print_scale_phrase(concept: ComposedConcept) -> str:
    print_scale = concept.selected_elements.get("print_scale")
    if print_scale:
        return f"{print_scale.value} scale"
    return "commercial print scale"
