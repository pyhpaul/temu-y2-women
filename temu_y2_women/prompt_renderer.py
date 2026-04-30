from __future__ import annotations

from temu_y2_women.models import (
    ComposedConcept,
    NormalizedRequest,
    SelectedStrategy,
    SelectedStyleFamily,
)

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
_ELEMENT_PHRASE_OVERRIDES = {
    ("silhouette", "babydoll"): "babydoll silhouette with easy high-waist volume",
    ("fabric", "linen blend"): "linen-blend fabric",
    ("neckline", "bandeau neckline"): "strapless bandeau neckline",
    ("neckline", "halter neckline"): "halter neckline with open shoulders",
    ("pattern", "stripe print"): "directional stripe print",
    ("pattern", "gingham check"): "two-tone gingham check",
    ("detail", "bubble hem"): "bubble hem finish",
    ("detail", "slip dress"): "slip-dress drape",
    ("color_family", "brown"): "brown neutral color story",
}


def render_prompt_bundle(
    request: NormalizedRequest,
    concept: ComposedConcept,
    selected_strategies: tuple[SelectedStrategy, ...],
    selected_style_family: SelectedStyleFamily | None,
    warnings: tuple[str, ...],
) -> dict[str, object]:
    development_notes = list(concept.style_summary or warnings or ("dress MVP development guidance",))
    render_jobs = _render_jobs(
        request,
        concept,
        selected_strategies,
        selected_style_family,
        development_notes,
    )
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
    selected_style_family: SelectedStyleFamily | None,
    development_notes: list[str],
    shot_line: str,
) -> str:
    return "\n".join(
        (
            f"[商品主体] {_subject_line(request, concept, selected_style_family)}",
            f"[核心结构] {_structure_line(request, concept)}",
            f"[关键视觉差异点] {_critical_visual_line(concept, selected_style_family)}",
            f"[生产与细节展示要求] {_detail_requirements_line(request, concept, selected_strategies, development_notes)}",
            f"[镜头与构图] {_shot_line(shot_line, selected_style_family)}",
            f"[面料与工艺表现] {_material_line(concept)}",
            f"[场景与光线] {_scene_line(request, selected_style_family)}",
            f"[约束与避免项] {_constraint_line(request, selected_style_family)}",
        )
    )


def _subject_line(
    request: NormalizedRequest,
    concept: ComposedConcept,
    selected_style_family: SelectedStyleFamily | None,
) -> str:
    family_hint = _family_hint(selected_style_family, "subject_hint")
    if request.mode == "A":
        if family_hint:
            return (
                f"women's {concept.category} for the {request.target_market} market; "
                f"{family_hint}; on-model ecommerce hero image; product-first presentation"
            )
        return (
            f"women's {_occasion_phrase(request)} {concept.category} for the {request.target_market} market, "
            "on-model ecommerce hero image, product-first presentation"
        )
    if family_hint:
        return (
            f"women's {concept.category} development reference image for the {request.target_market} market; "
            f"{family_hint}; production-review presentation"
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
    override = _ELEMENT_PHRASE_OVERRIDES.get((slot, value))
    if override:
        return override
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
    concept: ComposedConcept,
    selected_strategies: tuple[SelectedStrategy, ...],
    development_notes: list[str],
) -> str:
    items = [
        f"clearly show {_detail_visibility_targets(concept)}",
        "keep the garment visually realistic and feasible for factory production",
    ]
    if request.mode == "B":
        items.append(f"development notes: {'; '.join(development_notes)}")
        if selected_strategies:
            items.append(f"seasonal direction: {_strategy_reason_summary(selected_strategies)}")
    elif selected_strategies:
        items.append(f"seasonal direction: {_strategy_reason_summary(selected_strategies)}")
    return "; ".join(items)


def _critical_visual_line(
    concept: ComposedConcept,
    selected_style_family: SelectedStyleFamily | None,
) -> str:
    family_id = _selected_style_family_id(selected_style_family)
    if family_id == "clean-minimal":
        return _clean_minimal_visual_line(concept)
    if family_id == "city-polished":
        return _city_polished_visual_line(concept)
    if family_id == "party-fitted":
        return _party_fitted_visual_line(concept)
    if family_id == "vacation-romantic":
        return _vacation_romantic_visual_line(concept)
    return _generic_visual_line(concept)


def _render_jobs(
    request: NormalizedRequest,
    concept: ComposedConcept,
    selected_strategies: tuple[SelectedStrategy, ...],
    selected_style_family: SelectedStyleFamily | None,
    development_notes: list[str],
) -> list[dict[str, str]]:
    return _hero_jobs(
        request,
        concept,
        selected_strategies,
        selected_style_family,
        development_notes,
    ) + _detail_jobs(concept)


def _hero_jobs(
    request: NormalizedRequest,
    concept: ComposedConcept,
    selected_strategies: tuple[SelectedStrategy, ...],
    selected_style_family: SelectedStyleFamily | None,
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
                    selected_style_family,
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
    selected_style_family: SelectedStyleFamily | None,
    development_notes: list[str],
    prompt_id: str,
    angle: str,
) -> str:
    if prompt_id == "hero_front":
        return _build_prompt(
            request,
            concept,
            selected_strategies,
            selected_style_family,
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
    fabric_text = _selected_phrase(concept, "fabric", "dress fabric")
    color_text = _selected_phrase(concept, "color_family", "commercial color")
    items = [f"crisp {fabric_text} texture"]
    detail_text = _selected_optional_value(concept, "detail")
    if detail_text:
        items.append(f"visible {_element_phrase('detail', detail_text)}")
    items.extend(("visible seam lines", "clean hem finish", f"true-to-color {color_text}"))
    pattern_text = _selected_optional_value(concept, "pattern")
    if pattern_text:
        items.append(f"visible {_element_phrase('pattern', pattern_text)}")
    print_scale = _selected_optional_value(concept, "print_scale")
    if print_scale:
        items.append(_element_phrase("print_scale", print_scale))
    opacity = _selected_optional_value(concept, "opacity_level")
    if opacity:
        items.append(_element_phrase("opacity_level", opacity))
    items.extend(("natural drape", "commercially realistic construction"))
    return "; ".join(items)


def _scene_line(
    request: NormalizedRequest,
    selected_style_family: SelectedStyleFamily | None,
) -> str:
    scene_hint = _family_hint(selected_style_family, "scene_hint")
    lighting_hint = _family_hint(selected_style_family, "lighting_hint")
    if scene_hint or lighting_hint:
        return "; ".join(item for item in (scene_hint, lighting_hint) if item)
    if "vacation" in request.occasion_tags:
        return "clean sunlit resort-inspired studio; soft directional daylight; warm ivory and sand background; minimal props"
    if request.mode == "B":
        return "clean neutral studio; soft commercial lighting; background kept quiet for production review"
    return "clean studio; soft commercial lighting; quiet background that supports the garment without competing"


def _constraint_line(
    request: NormalizedRequest,
    selected_style_family: SelectedStyleFamily | None,
) -> str:
    items = ["no text", "no watermark", "no cluttered background", "no unrealistic garment construction"]
    if "bodycon" in request.avoid_tags:
        items.insert(0, "no bodycon fit")
    for tag in request.avoid_tags:
        if tag != "bodycon":
            items.append(f"avoid {tag} styling")
    items.extend(_family_constraint_hints(selected_style_family))
    items.extend(("no jacket", "no cardigan", "no bag covering the bodice", "no exaggerated editorial pose"))
    return "; ".join(items)


def _shot_line(shot_line: str, selected_style_family: SelectedStyleFamily | None) -> str:
    styling_hint = _family_hint(selected_style_family, "styling_hint")
    if not styling_hint:
        return shot_line
    return f"{shot_line}; styling direction: {styling_hint}"


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
    fabric = _selected_phrase(concept, "fabric", "dress fabric")
    pattern = _selected_phrase(concept, "pattern", "surface print")
    color = _selected_phrase(concept, "color_family", "commercial color")
    detail = _selected_phrase(concept, "detail", "construction detail")
    return (
        "Keep the exact same dress, same model, same silhouette, "
        f"same {fabric} texture, same {pattern} placement, same {color}, and same {detail}."
    )


def _construction_edit_instruction(concept: ComposedConcept) -> str:
    neckline = _selected_phrase(concept, "neckline", "selected neckline")
    detail = _selected_phrase(concept, "detail", _selected_phrase(concept, "fabric", "selected fabric"))
    waistline = _selected_phrase(
        concept,
        "waistline",
        _selected_phrase(concept, "silhouette", "selected silhouette"),
    )
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
    fabric = _selected_phrase(concept, "fabric", "selected fabric")
    pattern = _selected_phrase(concept, "pattern", "solid color")
    print_scale = _element_phrase("print_scale", _selected_value(concept, "print_scale", "commercial print"))
    opacity = _element_phrase("opacity_level", _selected_value(concept, "opacity_level", "opaque"))
    return " ".join(
        (
            "Edit the reference image.",
            _identity_lock_line(concept),
            f"Zoom into the {fabric} surface.",
            f"Clearly show {pattern}, {print_scale}, {opacity}, weave texture, and color accuracy.",
            "Keep soft studio lighting and realistic surface detail; no blur, no props, no text.",
        )
    )


def _hem_edit_instruction(concept: ComposedConcept) -> str:
    silhouette = _selected_phrase(concept, "silhouette", "selected silhouette")
    dress_length = _selected_value(concept, "dress_length", "balanced")
    pattern = _selected_phrase(concept, "pattern", "surface print")
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


def _selected_optional_value(concept: ComposedConcept, slot: str) -> str | None:
    element = concept.selected_elements.get(slot)
    if element is None:
        return None
    return element.value


def _selected_phrase(concept: ComposedConcept, slot: str, default: str) -> str:
    element = concept.selected_elements.get(slot)
    if element is None:
        return default
    return _element_phrase(slot, element.value)


def _selected_style_family_id(selected_style_family: SelectedStyleFamily | None) -> str:
    if selected_style_family is None:
        return ""
    return selected_style_family.profile.style_family_id


def _generic_visual_line(concept: ComposedConcept) -> str:
    targets = _generic_visual_targets(concept)
    return (
        f"keep the {_oxford_join(targets)} clearly readable from first glance; "
        "do not simplify the garment into a generic commercial dress shape"
    )


def _generic_visual_targets(concept: ComposedConcept) -> list[str]:
    slots = ("neckline", "silhouette", "detail", "pattern")
    targets = []
    for slot in slots:
        value = _selected_optional_value(concept, slot)
        if value is None:
            continue
        targets.append(_element_phrase(slot, value))
    if targets:
        return targets
    return ["selected neckline", "selected silhouette"]


def _clean_minimal_visual_line(concept: ComposedConcept) -> str:
    neckline = _selected_value(concept, "neckline", "jewel neckline")
    return (
        f"{neckline} should read close to the base of the neck with a quiet clean edge; "
        "the front body should stay low-noise and minimal; not a square neckline; "
        "not a sweetheart neckline; not a boat neckline; not an off-shoulder impression"
    )


def _city_polished_visual_line(concept: ComposedConcept) -> str:
    neckline = _selected_value(concept, "neckline", "square neckline")
    detail = _selected_value(concept, "detail", "tailored seam panel")
    return (
        f"{neckline} with visible corner geometry should stay obvious; "
        f"{detail} should stay obvious on the front body; "
        "keep the torso polished and structured; not a boat neckline; not a sweetheart neckline"
    )


def _party_fitted_visual_line(concept: ComposedConcept) -> str:
    neckline = _selected_value(concept, "neckline", "sweetheart neckline")
    detail = _selected_value(concept, "detail", "ruched side seam")
    return (
        f"{neckline} bust curve should read clearly; {detail} should stay visible; "
        "keep the fitted evening shape sharp; not a flat boat neckline; not a rigid square neckline"
    )


def _vacation_romantic_visual_line(concept: ComposedConcept) -> str:
    neckline = _selected_value(concept, "neckline", "square neckline")
    detail = _selected_value(concept, "detail", "neck scarf")
    sleeve = _selected_value(concept, "sleeve", "flutter sleeve")
    return (
        f"{neckline}, {sleeve}, and {detail} should feel airy and soft; "
        "keep the resort mood feminine and light; not sharp office tailoring; not an evening bodycon read"
    )


def _detail_visibility_targets(concept: ComposedConcept) -> str:
    targets = [
        "neckline depth",
        "bodice construction",
        "sleeve opening",
        "waist seam position",
        "skirt volume",
        "hem finish",
        "fabric texture",
    ]
    if "pattern" in concept.selected_elements:
        targets.insert(-1, "print placement")
    if "print_scale" in concept.selected_elements:
        targets.insert(-1, "print scale")
    return _oxford_join(targets)


def _oxford_join(items: list[str]) -> str:
    if len(items) == 1:
        return items[0]
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def _family_hint(selected_style_family: SelectedStyleFamily | None, field: str) -> str:
    if selected_style_family is None:
        return ""
    return str(getattr(selected_style_family.profile, field))


def _family_constraint_hints(selected_style_family: SelectedStyleFamily | None) -> tuple[str, ...]:
    if selected_style_family is None:
        return ()
    return selected_style_family.profile.constraint_hints


def _strategy_reason_summary(selected_strategies: tuple[SelectedStrategy, ...]) -> str:
    return "; ".join(item.reason for item in selected_strategies)
