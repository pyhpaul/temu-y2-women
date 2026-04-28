from __future__ import annotations

from typing import Any

from temu_y2_women.compatibility_evaluator import (
    CompatibilityEvaluation,
    CompatibilityRule,
    evaluate_selection_compatibility,
    load_compatibility_rules,
)
from temu_y2_women.errors import GenerationError
from temu_y2_women.models import CandidateElement, ComposedConcept, ComposedElement, NormalizedRequest

_REQUIRED_SLOTS = ("silhouette", "fabric")
_STANDARD_OPTIONAL_SLOTS = (
    "neckline",
    "sleeve",
    "dress_length",
    "waistline",
    "color_family",
    "opacity_level",
)
_SURFACE_TOP_K = 3


def compose_concept(
    request: NormalizedRequest,
    candidates_by_slot: dict[str, list[dict[str, Any]]],
    compatibility_rules: tuple[CompatibilityRule, ...] | None = None,
) -> ComposedConcept:
    parsed_candidates = {
        slot: [_parse_candidate(candidate) for candidate in candidates]
        for slot, candidates in candidates_by_slot.items()
    }
    rules = tuple(compatibility_rules) if compatibility_rules is not None else tuple(load_compatibility_rules())
    selected = _select_required_slots(parsed_candidates)
    optional_selected, optional_notes = _select_standard_optional_slots(parsed_candidates, selected)
    selected.update(optional_selected)
    surface_selected, evaluation = _select_surface_group(parsed_candidates, rules)
    selected.update(surface_selected)
    constraint_notes = [*_must_have_notes(request, selected), *optional_notes, *evaluation.compatibility_notes]
    concept_score = _concept_score(selected, evaluation)
    return ComposedConcept(
        category=request.category,
        concept_score=concept_score,
        selected_elements={
            slot: ComposedElement(element_id=candidate.element_id, value=candidate.value)
            for slot, candidate in selected.items()
        },
        style_summary=_style_summary(selected),
        constraint_notes=tuple(constraint_notes),
    )


def _parse_candidate(payload: dict[str, Any]) -> CandidateElement:
    return CandidateElement(
        element_id=str(payload["element_id"]),
        category=str(payload["category"]),
        slot=str(payload["slot"]),
        value=str(payload["value"]),
        tags=tuple(payload.get("tags", [])),
        base_score=float(payload["base_score"]),
        effective_score=float(payload.get("effective_score", payload["base_score"])),
        risk_flags=tuple(payload.get("risk_flags", [])),
        evidence_summary=str(payload.get("evidence_summary", "")),
    )


def _top_candidate(candidates: list[CandidateElement]) -> CandidateElement:
    return max(candidates, key=lambda candidate: (candidate.effective_score, candidate.element_id))


def _select_required_slots(
    parsed_candidates: dict[str, list[CandidateElement]],
) -> dict[str, CandidateElement]:
    selected: dict[str, CandidateElement] = {}
    for slot in _REQUIRED_SLOTS:
        candidates = parsed_candidates.get(slot, [])
        if not candidates:
            raise GenerationError(
                code="INCOMPLETE_CONCEPT",
                message=f"missing required slot: {slot}",
                details={"slot": slot},
            )
        selected[slot] = _top_candidate(candidates)
    return selected


def _select_standard_optional_slots(
    parsed_candidates: dict[str, list[CandidateElement]],
    required_selected: dict[str, CandidateElement],
) -> tuple[dict[str, CandidateElement], tuple[str, ...]]:
    selected: dict[str, CandidateElement] = {}
    notes: list[str] = []
    for slot in _STANDARD_OPTIONAL_SLOTS:
        ranked = _top_candidates(parsed_candidates.get(slot, []), limit=3)
        chosen = _first_eligible_optional(slot, ranked, {**required_selected, **selected}, notes)
        if chosen is not None:
            selected[slot] = chosen
    return selected, tuple(notes)


def _first_eligible_optional(
    slot: str,
    ranked: list[CandidateElement],
    selected: dict[str, CandidateElement],
    notes: list[str],
) -> CandidateElement | None:
    for candidate in ranked:
        if slot == "waistline" and _selected_value(selected, "silhouette") == "bodycon" and candidate.value == "drop waist":
            notes.append("structural conflict avoided: bodycon + drop waist")
            continue
        return candidate
    return None


def _select_surface_group(
    parsed_candidates: dict[str, list[CandidateElement]],
    rules: tuple[CompatibilityRule, ...],
) -> tuple[dict[str, CandidateElement], CompatibilityEvaluation]:
    best_selected: dict[str, CandidateElement] = {}
    best_evaluation = CompatibilityEvaluation((), (), 0.0, ())
    best_rank = _selection_rank(best_selected, best_evaluation)
    skipped_conflicts: list[tuple[dict[str, CandidateElement], CompatibilityEvaluation]] = []
    pattern_options = [None, *_top_candidates(parsed_candidates.get("pattern", []), limit=_SURFACE_TOP_K)]
    detail_options = [None, *_top_candidates(parsed_candidates.get("detail", []), limit=_SURFACE_TOP_K)]
    for pattern in pattern_options:
        print_scale_options = [None] if pattern is None else [
            None,
            *_top_candidates(parsed_candidates.get("print_scale", []), limit=_SURFACE_TOP_K),
        ]
        for print_scale in print_scale_options:
            for detail in detail_options:
                current = _selected_surface(pattern, print_scale, detail)
                evaluation = evaluate_selection_compatibility(current, rules)
                if evaluation.hard_conflicts:
                    skipped_conflicts.append((current, evaluation))
                    continue
                rank = _selection_rank(current, evaluation)
                if rank > best_rank:
                    best_selected, best_evaluation, best_rank = current, evaluation, rank
    return best_selected, _merge_avoided_conflict_notes(best_selected, best_evaluation, skipped_conflicts)


def _merge_avoided_conflict_notes(
    best_selected: dict[str, CandidateElement],
    best_evaluation: CompatibilityEvaluation,
    skipped_conflicts: list[tuple[dict[str, CandidateElement], CompatibilityEvaluation]],
) -> CompatibilityEvaluation:
    notes = list(best_evaluation.compatibility_notes)
    for skipped_selected, evaluation in skipped_conflicts:
        if not _is_omitted_subset(best_selected, skipped_selected):
            continue
        for note in evaluation.compatibility_notes:
            if note not in notes:
                notes.append(note)
    return CompatibilityEvaluation(
        best_evaluation.hard_conflicts,
        best_evaluation.soft_conflicts,
        best_evaluation.compatibility_penalty,
        tuple(notes),
    )


def _is_omitted_subset(
    best_selected: dict[str, CandidateElement],
    skipped_selected: dict[str, CandidateElement],
) -> bool:
    if not best_selected or len(best_selected) >= len(skipped_selected):
        return False
    return all(
        skipped_selected.get(slot) is not None
        and skipped_selected[slot].element_id == candidate.element_id
        for slot, candidate in best_selected.items()
    )


def _top_candidates(
    candidates: list[CandidateElement],
    limit: int = _SURFACE_TOP_K,
) -> list[CandidateElement]:
    ranked = sorted(
        candidates,
        key=lambda candidate: (candidate.effective_score, candidate.element_id),
        reverse=True,
    )
    return ranked[:limit]


def _selection_score(
    selected: dict[str, CandidateElement],
    evaluation: CompatibilityEvaluation,
) -> float:
    return sum(candidate.effective_score for candidate in selected.values()) - evaluation.compatibility_penalty


def _concept_score(
    selected: dict[str, CandidateElement],
    evaluation: CompatibilityEvaluation,
) -> float:
    return round(_selection_score(selected, evaluation) / len(selected), 4)


def _selection_rank(
    selected: dict[str, CandidateElement],
    evaluation: CompatibilityEvaluation,
) -> tuple[float, int, str, str, str]:
    return (
        _selection_score(selected, evaluation),
        len(selected),
        _selected_element_id(selected, "pattern"),
        _selected_element_id(selected, "print_scale"),
        _selected_element_id(selected, "detail"),
    )


def _selected_surface(
    pattern: CandidateElement | None,
    print_scale: CandidateElement | None,
    detail: CandidateElement | None,
) -> dict[str, CandidateElement]:
    selected: dict[str, CandidateElement] = {}
    if pattern is not None:
        selected["pattern"] = pattern
    if print_scale is not None:
        selected["print_scale"] = print_scale
    if detail is not None:
        selected["detail"] = detail
    return selected


def _selected_element_id(
    selected: dict[str, CandidateElement],
    slot: str,
) -> str:
    candidate = selected.get(slot)
    return "" if candidate is None else candidate.element_id


def _selected_value(
    selected: dict[str, CandidateElement],
    slot: str,
) -> str:
    candidate = selected.get(slot)
    return "" if candidate is None else candidate.value


def _must_have_notes(
    request: NormalizedRequest,
    selected: dict[str, CandidateElement],
) -> tuple[str, ...]:
    if not request.must_have_tags:
        return ()

    available_tags = {
        tag
        for candidate in selected.values()
        for tag in candidate.tags
    }
    notes: list[str] = []
    for tag in request.must_have_tags:
        if tag not in available_tags:
            raise GenerationError(
                code="CONSTRAINT_CONFLICT",
                message="must_have_tags could not be satisfied",
                details={"must_have_tag": tag},
            )
        notes.append(f"must_have_tags satisfied: {tag}")
    return tuple(notes)


def _style_summary(selected: dict[str, CandidateElement]) -> tuple[str, ...]:
    tags = []
    for candidate in selected.values():
        for tag in candidate.tags:
            if tag not in tags:
                tags.append(tag)
    return tuple(tags[:4])
