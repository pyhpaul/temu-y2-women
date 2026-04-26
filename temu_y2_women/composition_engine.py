from __future__ import annotations

from typing import Any

from temu_y2_women.errors import GenerationError
from temu_y2_women.models import CandidateElement, ComposedConcept, ComposedElement, NormalizedRequest

_REQUIRED_SLOTS = ("silhouette", "fabric")


def compose_concept(
    request: NormalizedRequest,
    candidates_by_slot: dict[str, list[dict[str, Any]]],
) -> ComposedConcept:
    parsed_candidates = {
        slot: [_parse_candidate(candidate) for candidate in candidates]
        for slot, candidates in candidates_by_slot.items()
    }

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

    for slot in ("neckline", "sleeve", "pattern", "detail"):
        candidates = parsed_candidates.get(slot, [])
        if candidates:
            selected[slot] = _top_candidate(candidates)

    constraint_notes = list(_must_have_notes(request, selected))
    concept_score = sum(candidate.effective_score for candidate in selected.values()) / len(selected)

    style_summary = _style_summary(selected)
    return ComposedConcept(
        category=request.category,
        concept_score=round(concept_score, 4),
        selected_elements={
            slot: ComposedElement(element_id=candidate.element_id, value=candidate.value)
            for slot, candidate in selected.items()
        },
        style_summary=style_summary,
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
