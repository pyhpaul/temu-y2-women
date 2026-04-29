from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


class StyleFamilyRepositoryTest(unittest.TestCase):
    def test_load_style_families_accepts_active_family_config(self) -> None:
        from temu_y2_women.style_family_repository import load_style_families

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            taxonomy_path = temp_root / "taxonomy.json"
            elements_path = temp_root / "elements.json"
            families_path = temp_root / "style_families.json"
            _write_taxonomy(taxonomy_path)
            _write_elements(elements_path)
            _write_style_families(families_path)

            profiles = load_style_families(
                path=families_path,
                elements_path=elements_path,
                taxonomy_path=taxonomy_path,
            )

        self.assertEqual(
            [item.style_family_id for item in profiles],
            ["vacation-romantic", "party-fitted"],
        )
        self.assertEqual(profiles[0].hard_slot_values["silhouette"], ("a-line",))
        self.assertEqual(profiles[1].soft_slot_values["detail"], ("ruched side seam",))

    def test_reject_style_family_with_unknown_active_value(self) -> None:
        from temu_y2_women.errors import GenerationError
        from temu_y2_women.style_family_repository import load_style_families

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            taxonomy_path = temp_root / "taxonomy.json"
            elements_path = temp_root / "elements.json"
            families_path = temp_root / "style_families.json"
            _write_taxonomy(taxonomy_path)
            _write_elements(elements_path)
            _write_style_families(
                families_path,
                overrides={
                    "style_families": [
                        {
                            "style_family_id": "broken-family",
                            "status": "active",
                            "fallback_reason": "test fixture",
                            "hard_slot_values": {"silhouette": ["missing-shape"]},
                            "soft_slot_values": {},
                            "blocked_slot_values": {},
                            "prompt_shell": {
                                "subject_hint": "broken",
                                "scene_hint": "broken",
                                "lighting_hint": "broken",
                                "styling_hint": "broken",
                                "constraint_hints": ["broken"],
                            },
                        }
                    ]
                },
            )

            with self.assertRaises(GenerationError) as error_context:
                load_style_families(
                    path=families_path,
                    elements_path=elements_path,
                    taxonomy_path=taxonomy_path,
                )

        self.assertEqual(error_context.exception.code, "INVALID_STYLE_FAMILY_CONFIG")
        self.assertEqual(
            error_context.exception.message,
            "style family references unknown active element values",
        )
        self.assertEqual(error_context.exception.details["slot"], "silhouette")
        self.assertEqual(error_context.exception.details["values"], ["missing-shape"])


def _write_taxonomy(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "allowed_slots": [
                    "silhouette",
                    "fabric",
                    "dress_length",
                    "color_family",
                    "detail",
                ],
                "allowed_tags": [
                    "dress",
                    "feminine",
                    "bodycon",
                    "romantic",
                    "evening",
                ],
                "allowed_occasions": ["vacation", "party"],
                "allowed_seasons": ["spring", "summer"],
                "allowed_risk_flags": ["fit_sensitivity"],
                "summary": {"min_length": 20, "max_length": 140},
                "base_score": {"min": 0.0, "max": 1.0},
            }
        ),
        encoding="utf-8",
    )


def _write_elements(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "mvp-v1",
                "elements": [
                    _element(
                        "dress-silhouette-a-line-001",
                        "silhouette",
                        "a-line",
                        ["dress", "feminine", "romantic"],
                    ),
                    _element(
                        "dress-silhouette-bodycon-001",
                        "silhouette",
                        "bodycon",
                        ["dress", "bodycon", "evening"],
                        risk_flags=["fit_sensitivity"],
                    ),
                    _element("dress-fabric-cotton-voile-001", "fabric", "cotton voile", ["dress", "romantic"]),
                    _element("dress-fabric-stretch-jersey-001", "fabric", "stretch jersey", ["dress", "evening"]),
                    _element("dress-length-maxi-001", "dress_length", "maxi", ["dress", "romantic"]),
                    _element("dress-length-mini-001", "dress_length", "mini", ["dress", "evening"]),
                    _element("dress-color-white-001", "color_family", "white", ["dress", "romantic"]),
                    _element("dress-color-black-001", "color_family", "black", ["dress", "evening"]),
                    _element("dress-detail-smocked-001", "detail", "smocked bodice", ["dress", "romantic"]),
                    _element("dress-detail-ruched-001", "detail", "ruched side seam", ["dress", "evening"]),
                ],
            }
        ),
        encoding="utf-8",
    )


def _write_style_families(path: Path, overrides: dict[str, object] | None = None) -> None:
    payload: dict[str, object] = {
        "schema_version": "style-family-v1",
        "style_families": [
            {
                "style_family_id": "vacation-romantic",
                "status": "active",
                "fallback_reason": "vacation request",
                "hard_slot_values": {
                    "silhouette": ["a-line"],
                    "fabric": ["cotton voile"],
                    "dress_length": ["maxi"],
                },
                "soft_slot_values": {"detail": ["smocked bodice"]},
                "blocked_slot_values": {},
                "prompt_shell": {
                    "subject_hint": "airy romantic vacation dress",
                    "scene_hint": "sunlit resort setting",
                    "lighting_hint": "soft daylight",
                    "styling_hint": "relaxed feminine styling",
                    "constraint_hints": ["avoid nightlife mood"],
                },
            },
            {
                "style_family_id": "party-fitted",
                "status": "active",
                "fallback_reason": "party request",
                "hard_slot_values": {
                    "silhouette": ["bodycon"],
                    "fabric": ["stretch jersey"],
                    "dress_length": ["mini"],
                },
                "soft_slot_values": {"detail": ["ruched side seam"]},
                "blocked_slot_values": {},
                "prompt_shell": {
                    "subject_hint": "sleek evening party dress",
                    "scene_hint": "night studio",
                    "lighting_hint": "high-contrast evening lighting",
                    "styling_hint": "confident fitted styling",
                    "constraint_hints": ["avoid resort props"],
                },
            },
        ],
    }
    if overrides:
        payload.update(overrides)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _element(
    element_id: str,
    slot: str,
    value: str,
    tags: list[str],
    risk_flags: list[str] | None = None,
) -> dict[str, object]:
    return {
        "element_id": element_id,
        "category": "dress",
        "slot": slot,
        "value": value,
        "tags": tags,
        "base_score": 0.7,
        "price_bands": ["mid"],
        "occasion_tags": ["vacation", "party"],
        "season_tags": ["spring", "summer"],
        "risk_flags": risk_flags or [],
        "evidence_summary": "Fixture record with enough detail to validate style family configuration loading.",
        "status": "active",
    }
