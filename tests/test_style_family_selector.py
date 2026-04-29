from __future__ import annotations

from datetime import date
import unittest

from temu_y2_women.models import NormalizedRequest, StyleFamilyProfile


class StyleFamilySelectorTest(unittest.TestCase):
    def test_select_explicit_style_family(self) -> None:
        from temu_y2_women.style_family_selector import select_style_family

        selected = select_style_family(
            request=_request(style_family="city-polished"),
            profiles=_profiles(),
        )

        self.assertEqual(selected.profile.style_family_id, "city-polished")
        self.assertEqual(selected.selection_mode, "explicit")

    def test_select_default_vacation_style_family(self) -> None:
        from temu_y2_women.style_family_selector import select_style_family

        selected = select_style_family(
            request=_request(occasion_tags=("vacation",)),
            profiles=_profiles(),
        )

        self.assertEqual(selected.profile.style_family_id, "vacation-romantic")
        self.assertEqual(selected.selection_mode, "fallback")

    def test_select_default_transitional_style_family(self) -> None:
        from temu_y2_women.style_family_selector import select_style_family

        selected = select_style_family(
            request=_request(
                occasion_tags=("casual",),
                must_have_tags=("transitional",),
            ),
            profiles=_profiles(),
        )

        self.assertEqual(selected.profile.style_family_id, "clean-minimal")
        self.assertEqual(selected.selection_mode, "fallback")

    def test_reject_explicit_style_family_when_request_conflicts(self) -> None:
        from temu_y2_women.errors import GenerationError
        from temu_y2_women.style_family_selector import select_style_family

        with self.assertRaises(GenerationError) as error_context:
            select_style_family(
                request=_request(
                    occasion_tags=("party",),
                    avoid_tags=("bodycon",),
                    style_family="party-fitted",
                ),
                profiles=_profiles(),
            )

        self.assertEqual(error_context.exception.code, "CONSTRAINT_CONFLICT")
        self.assertEqual(
            error_context.exception.message,
            "explicit style_family conflicts with request constraints",
        )
        self.assertEqual(error_context.exception.details["style_family"], "party-fitted")
        self.assertEqual(error_context.exception.details["avoid_tags"], ["bodycon"])


def _request(
    occasion_tags: tuple[str, ...] = (),
    must_have_tags: tuple[str, ...] = (),
    avoid_tags: tuple[str, ...] = (),
    style_family: str | None = None,
) -> NormalizedRequest:
    return NormalizedRequest(
        category="dress",
        target_market="US",
        target_launch_date=date(2026, 6, 15),
        mode="A",
        price_band="mid",
        occasion_tags=occasion_tags,
        must_have_tags=must_have_tags,
        avoid_tags=avoid_tags,
        style_family=style_family,
    )


def _profiles() -> tuple[StyleFamilyProfile, ...]:
    return (
        _profile(
            style_family_id="vacation-romantic",
            hard_slot_values={"silhouette": ("a-line",)},
            soft_slot_values={"detail": ("smocked bodice",)},
            blocked_slot_values={"silhouette": ("bodycon",)},
            subject_hint="airy romantic vacation dress",
            scene_hint="sunlit resort setting",
            lighting_hint="soft daylight",
            styling_hint="relaxed feminine styling",
            constraint_hints=("avoid nightlife mood",),
            fallback_reason="vacation request",
        ),
        _profile(
            style_family_id="clean-minimal",
            hard_slot_values={"silhouette": ("shift",)},
            soft_slot_values={"color_family": ("stone",)},
            blocked_slot_values={"pattern": ("floral print", "polka dot")},
            subject_hint="clean minimal dress",
            scene_hint="quiet studio",
            lighting_hint="flat studio light",
            styling_hint="minimal styling",
            constraint_hints=("avoid loud prints",),
            fallback_reason="transitional or casual request",
        ),
        _profile(
            style_family_id="city-polished",
            hard_slot_values={"silhouette": ("sheath",)},
            soft_slot_values={"detail": ("tailored seam panel",)},
            blocked_slot_values={"pattern": ("floral print",)},
            subject_hint="polished city dress",
            scene_hint="urban studio",
            lighting_hint="clean directional light",
            styling_hint="sharp commercial styling",
            constraint_hints=("avoid beach props",),
            fallback_reason="default route",
        ),
        _profile(
            style_family_id="party-fitted",
            hard_slot_values={"silhouette": ("bodycon",)},
            soft_slot_values={"detail": ("ruched side seam",)},
            blocked_slot_values={"pattern": ("floral print",)},
            subject_hint="sleek party dress",
            scene_hint="evening set",
            lighting_hint="high-contrast light",
            styling_hint="confident fitted styling",
            constraint_hints=("avoid daytime resort mood",),
            fallback_reason="party request",
        ),
    )


def _profile(
    style_family_id: str,
    hard_slot_values: dict[str, tuple[str, ...]],
    soft_slot_values: dict[str, tuple[str, ...]],
    blocked_slot_values: dict[str, tuple[str, ...]],
    subject_hint: str,
    scene_hint: str,
    lighting_hint: str,
    styling_hint: str,
    constraint_hints: tuple[str, ...],
    fallback_reason: str,
) -> StyleFamilyProfile:
    return StyleFamilyProfile(
        style_family_id=style_family_id,
        hard_slot_values=hard_slot_values,
        soft_slot_values=soft_slot_values,
        blocked_slot_values=blocked_slot_values,
        subject_hint=subject_hint,
        scene_hint=scene_hint,
        lighting_hint=lighting_hint,
        styling_hint=styling_hint,
        constraint_hints=constraint_hints,
        fallback_reason=fallback_reason,
        status="active",
    )
