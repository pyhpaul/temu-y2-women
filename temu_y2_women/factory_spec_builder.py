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
_FIT_REVIEW_RULES = {
    ("dress_length", "mini"): "fit cue: verify mini length keeps intended coverage in motion and while seated",
    ("waistline", "drop waist"): "fit cue: confirm drop waist seam lands low enough to read intentional without dragging the torso",
}
_VISIBLE_CHECK_RULES = {
    ("waistline", "drop waist"): "visible check: confirm drop waist seam stays level and visually intentional around the body",
    ("print_scale", "micro print"): "visible check: confirm micro print stays crisp without muddying at seams or gathers",
    ("opacity_level", "opaque"): "visible check: confirm opaque coverage stays consistent in bright light",
    ("opacity_level", "sheer"): "visible check: confirm sheer areas stay intentional and balanced across layers and seam zones",
}
_COMMERCIAL_CUE_RULES = {
    ("print_scale", "micro print"): "commercial cue: make sure micro print still reads clearly in thumbnails and first-glance product imagery",
}
_OPEN_QUESTIONS = (
    "open question: confirm fiber_content from approved fabric submission",
    "open question: confirm fabric_weight_gsm from supplier or mill data",
    "open question: confirm lining need based on opacity and wear test outcome",
    "open question: confirm closure_details after sample review of entry and fit",
    "open question: define measurements_pom before tech-pack handoff",
    "open question: define seam_allowance with patternmaking owner",
    "open question: define tolerance by measurement point before production release",
    "open question: confirm bom_grade_trim requirements for elastic, labels, and finishing trims",
)


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
        "sample_review_watchpoints": _sample_review_watchpoints(request, concept),
        "qa_review_notes": _qa_review_notes(concept),
        "fit_review_cues": _fit_review_cues(request, concept),
        "commercial_review_cues": _commercial_review_cues(request, concept, selected_strategies),
        "visible_construction_checks": _visible_construction_checks(concept),
        "open_questions": list(_OPEN_QUESTIONS),
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


def _sample_review_watchpoints(
    request: NormalizedRequest,
    concept: ComposedConcept,
) -> list[str]:
    watchpoints = [_fabric_watchpoint(concept)]
    visible_parts = _selected_values(concept, "neckline", "detail", "sleeve")
    if visible_parts:
        watchpoints.append(
            f"sample review: verify {_join_values(visible_parts)} read clearly in the first sample"
        )
    pattern = _selected_value(concept, "pattern")
    if pattern:
        watchpoints.append(
            f"sample review: check {pattern} continuity and placement across bodice, waist seam, and skirt panels"
        )
    silhouette = _selected_value(concept, "silhouette")
    if silhouette:
        fit_phrase = "non-bodycon" if "bodycon" in request.avoid_tags else "commercially wearable"
        watchpoints.append(
            f"sample review: confirm {silhouette} shape stays easy and {fit_phrase} through waist-to-hem movement"
        )
    return watchpoints


def _qa_review_notes(concept: ComposedConcept) -> list[str]:
    notes = []
    neckline = _selected_value(concept, "neckline")
    if neckline:
        notes.append(f"qa review: check {neckline} edge finish for symmetry and clean top-line shape")
    detail = _selected_value(concept, "detail")
    notes.append(_detail_qa_note(detail))
    sleeve = _selected_value(concept, "sleeve")
    if sleeve:
        notes.append(f"qa review: check {sleeve} openings and hem finish for clean turnback and stable shape")
    pattern = _selected_value(concept, "pattern")
    if pattern:
        notes.append(f"qa review: check {pattern} alignment and continuity across visible seams")
    return notes


def _fit_review_cues(
    request: NormalizedRequest,
    concept: ComposedConcept,
) -> list[str]:
    cues = []
    if "bodycon" in request.avoid_tags:
        cues.append("fit cue: protect non-bodycon ease through bust, waist, and skirt sweep")
    if _selected_value(concept, "silhouette") == "a-line":
        cues.append("fit cue: keep a-line volume easy and mobile instead of collapsing into a narrow shape")
    if _selected_value(concept, "detail") == "smocked bodice":
        cues.append("fit cue: make sure smocked bodice shaping stays flexible rather than restrictive")
    cues.extend(_objective_slot_notes(concept, _FIT_REVIEW_RULES))
    return cues or ["fit cue: confirm the sample stays easy to wear for the intended market"]


def _commercial_review_cues(
    request: NormalizedRequest,
    concept: ComposedConcept,
    selected_strategies: tuple[SelectedStrategy, ...],
) -> list[str]:
    cues = []
    if selected_strategies:
        cues.append(f"commercial cue: seasonal review should stay anchored to {selected_strategies[0].reason}")
    if request.occasion_tags:
        cues.append(
            f"commercial cue: keep {request.occasion_tags[0]} use obvious from first-glance silhouette, fabric, and print direction"
        )
    if request.price_band:
        cues.append(f"commercial cue: keep visible construction commercially realistic for {request.price_band} pricing")
    if _selected_value(concept, "color_family") == "white" and _selected_value(concept, "opacity_level") == "sheer":
        cues.append("commercial cue: review white sheer execution for coverage, layering, and online readability")
    cues.extend(_objective_slot_notes(concept, _COMMERCIAL_CUE_RULES))
    if _selected_value(concept, "detail") and not cues:
        cues.append("commercial cue: keep the selected detail readable without overcomplicating production")
    return cues


def _visible_construction_checks(concept: ComposedConcept) -> list[str]:
    checks = []
    neckline = _selected_value(concept, "neckline")
    if neckline:
        checks.append(f"visible check: confirm {neckline} edge finish stays clean and even")
    detail = _selected_value(concept, "detail")
    checks.append(_detail_visible_check(detail))
    sleeve = _selected_value(concept, "sleeve")
    if sleeve:
        checks.append(f"visible check: confirm {sleeve} openings keep soft volume with clean finishing")
    silhouette = _selected_value(concept, "silhouette")
    if silhouette:
        checks.append(_silhouette_visible_check(silhouette))
    checks.append("visible check: confirm hem finish hangs cleanly without torque")
    pattern = _selected_value(concept, "pattern")
    if pattern:
        checks.append(f"visible check: confirm {pattern} continuity across visible seams")
    checks.extend(_objective_slot_notes(concept, _VISIBLE_CHECK_RULES))
    if detail:
        checks.append(f"visible check: confirm {_detail_visible_label(detail)} placement stays visually symmetrical")
    return checks


def _selected_value(concept: ComposedConcept, slot: str) -> str:
    element = concept.selected_elements.get(slot)
    return "" if element is None else element.value


def _selected_values(concept: ComposedConcept, *slots: str) -> list[str]:
    return [value for slot in slots if (value := _selected_value(concept, slot))]


def _fabric_watchpoint(concept: ComposedConcept) -> str:
    fabric = _selected_value(concept, "fabric")
    if fabric == "cotton poplin":
        return "sample review: confirm cotton poplin keeps crisp opacity and breathable structure in the finished dress"
    return f"sample review: confirm {fabric or 'selected fabric'} keeps stable texture, opacity, and commercial drape"


def _detail_qa_note(detail: str) -> str:
    if detail == "smocked bodice":
        return "qa review: check smocking rows for even tension, secure attachment, and balanced visual spacing"
    return "qa review: check visible detail attachment stays secure, even, and repeatable"


def _detail_visible_check(detail: str) -> str:
    if detail == "smocked bodice":
        return "visible check: confirm smocked bodice construction stays consistent across the front bodice"
    return "visible check: confirm visible detail construction stays clean and balanced"


def _detail_visible_label(detail: str) -> str:
    if detail == "smocked bodice":
        return "smocked detail"
    return detail or "detail"


def _silhouette_visible_check(silhouette: str) -> str:
    if silhouette == "a-line":
        return "visible check: confirm waist seam placement supports balanced a-line proportion"
    return f"visible check: confirm waist seam placement supports balanced {silhouette} proportion"


def _join_values(values: list[str]) -> str:
    if len(values) < 3:
        return " and ".join(values)
    return f"{', '.join(values[:-1])}, and {values[-1]}"


def _objective_slot_notes(concept: ComposedConcept, rules: dict[tuple[str, str], str]) -> list[str]:
    return [
        note
        for (slot, expected_value), note in rules.items()
        if _selected_value(concept, slot) == expected_value
    ]
