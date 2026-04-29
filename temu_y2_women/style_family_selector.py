from __future__ import annotations

from temu_y2_women.errors import GenerationError
from temu_y2_women.models import NormalizedRequest, SelectedStyleFamily, StyleFamilyProfile


def select_style_family(
    request: NormalizedRequest,
    profiles: tuple[StyleFamilyProfile, ...],
) -> SelectedStyleFamily:
    active_profiles = {item.style_family_id: item for item in profiles if item.status == "active"}
    if request.style_family is not None:
        profile = active_profiles.get(request.style_family)
        if profile is None:
            raise GenerationError(
                code="INVALID_REQUEST",
                message="style_family is not supported",
                details={"field": "style_family", "style_family": request.style_family},
            )
        _raise_if_explicit_conflicts(request, profile)
        return SelectedStyleFamily(profile=profile, selection_mode="explicit", reason=profile.fallback_reason)
    fallback_id = _fallback_style_family_id(request)
    profile = active_profiles[fallback_id]
    return SelectedStyleFamily(profile=profile, selection_mode="fallback", reason=profile.fallback_reason)


def _fallback_style_family_id(request: NormalizedRequest) -> str:
    if "party" in request.occasion_tags:
        return "party-fitted"
    if {"vacation", "resort"}.intersection(request.occasion_tags):
        return "vacation-romantic"
    if "transitional" in request.must_have_tags:
        return "clean-minimal"
    if "casual" in request.occasion_tags and "vacation" not in request.occasion_tags:
        return "clean-minimal"
    return "city-polished"


def _raise_if_explicit_conflicts(
    request: NormalizedRequest,
    profile: StyleFamilyProfile,
) -> None:
    blocked_avoid_tags = sorted(
        {
            tag
            for tag in request.avoid_tags
            if tag.casefold() in _canonical_hard_values(profile)
        }
    )
    if blocked_avoid_tags:
        raise GenerationError(
            code="CONSTRAINT_CONFLICT",
            message="explicit style_family conflicts with request constraints",
            details={"style_family": profile.style_family_id, "avoid_tags": blocked_avoid_tags},
        )


def _canonical_hard_values(profile: StyleFamilyProfile) -> set[str]:
    return {
        value.strip().casefold()
        for values in profile.hard_slot_values.values()
        for value in values
    }
