from __future__ import annotations

import json
from pathlib import Path
import unittest

from temu_y2_women.models import (
    ComposedConcept,
    ComposedElement,
    DateWindow,
    NormalizedRequest,
    SelectedStrategy,
    SelectedStyleFamily,
    StyleFamilyProfile,
    StrategyTemplate,
)


_REQUEST_FIXTURE_DIR = Path("tests/fixtures/requests/dress-generation-mvp")
_UNRESOLVED_FIELDS = [
    "fiber_content",
    "fabric_weight_gsm",
    "lining",
    "closure_details",
    "measurements_pom",
    "seam_allowance",
    "tolerance",
    "bom_grade_trim",
]


class FactorySpecBuilderTest(unittest.TestCase):
    def test_build_factory_spec_returns_draft_sections_for_successful_concept(self) -> None:
        from temu_y2_women.factory_spec_builder import build_factory_spec

        request, concept, selected_strategies = _build_success_inputs(
            "success-summer-vacation-mode-a.json"
        )
        factory_spec = build_factory_spec(
            request=request,
            concept=concept,
            selected_strategies=selected_strategies,
            selected_style_family=_selected_style_family("vacation-romantic"),
        )

        self.assertEqual(factory_spec["schema_version"], "factory-spec-v1")
        self.assertEqual(factory_spec["known"]["category"], "dress")
        self.assertEqual(factory_spec["known"]["target_market"], "US")
        self.assertEqual(
            factory_spec["known"]["selected_elements"]["fabric"]["value"],
            "cotton poplin",
        )
        self.assertEqual(
            factory_spec["known"]["selected_elements"]["detail"]["value"],
            "neck scarf",
        )
        self.assertIn(
            "non-bodycon fit requested by avoid_tags",
            factory_spec["inferred"]["fit_intent"],
        )
        self.assertIn(
            "confirm crisp texture, opacity, and print clarity for cotton poplin",
            factory_spec["inferred"]["fabric_review_focus"],
        )
        self.assertIn(
            "verify neck scarf attachment, width consistency, and clean turning",
            factory_spec["inferred"]["detail_review_focus"],
        )
        self.assertIn(
            "print continuity across seams",
            factory_spec["inferred"]["visible_construction_priorities"],
        )
        self.assertEqual(factory_spec["unresolved"], _UNRESOLVED_FIELDS)

    def test_build_factory_spec_adds_richer_review_watchpoints_and_cues(self) -> None:
        from temu_y2_women.factory_spec_builder import build_factory_spec

        request, concept, selected_strategies = _build_success_inputs(
            "success-summer-vacation-mode-a.json"
        )
        factory_spec = build_factory_spec(
            request=request,
            concept=concept,
            selected_strategies=selected_strategies,
            selected_style_family=_selected_style_family("vacation-romantic"),
        )

        inferred = factory_spec["inferred"]
        self.assertEqual(
            inferred["sample_review_watchpoints"],
            [
                "sample review: confirm cotton poplin keeps crisp opacity and breathable structure in the finished dress",
                "sample review: verify square neckline, neck scarf, and flutter sleeve read clearly in the first sample",
                "sample review: check floral print continuity and placement across bodice, waist seam, and skirt panels",
                "sample review: confirm a-line shape stays easy and non-bodycon through waist-to-hem movement",
            ],
        )
        self.assertEqual(
            inferred["qa_review_notes"],
            [
                "qa review: check square neckline edge finish for symmetry and clean top-line shape",
                "qa review: check neck scarf attachment, symmetry, and edge finish for clean repeatability",
                "qa review: check flutter sleeve openings and hem finish for clean turnback and stable shape",
                "qa review: check floral print alignment and continuity across visible seams",
            ],
        )
        self.assertEqual(
            inferred["fit_review_cues"],
            [
                "fit cue: protect non-bodycon ease through bust, waist, and skirt sweep",
                "fit cue: keep a-line volume easy and mobile instead of collapsing into a narrow shape",
                "fit cue: confirm drop-waist placement does not collapse the skirt balance",
                "fit cue: confirm mini length still feels secure and commercially wearable in motion",
            ],
        )
        self.assertEqual(
            inferred["commercial_review_cues"],
            [
                "commercial cue: keep white color direction and sheer balance commercially readable in first-glance imagery",
                "commercial cue: keep micro print scale crisp enough to read without visual noise",
                "commercial cue: seasonal review should stay anchored to launch date falls in the US summer vacation window and occasion tags align to vacation demand",
                "commercial cue: keep vacation use obvious from first-glance silhouette, fabric, and print direction",
                "commercial cue: keep visible construction commercially realistic for mid pricing",
            ],
        )

    def test_build_factory_spec_adds_visible_checks_and_open_questions(self) -> None:
        from temu_y2_women.factory_spec_builder import build_factory_spec

        request, concept, selected_strategies = _build_success_inputs(
            "success-summer-vacation-mode-a.json"
        )
        factory_spec = build_factory_spec(
            request=request,
            concept=concept,
            selected_strategies=selected_strategies,
            selected_style_family=_selected_style_family("vacation-romantic"),
        )

        inferred = factory_spec["inferred"]
        self.assertEqual(
            inferred["visible_construction_checks"],
            [
                "visible check: confirm square neckline edge finish stays clean and even",
                "visible check: confirm neck scarf attachment stays clean and balanced around the neckline",
                "visible check: confirm flutter sleeve openings keep soft volume with clean finishing",
                "visible check: confirm waist seam placement supports balanced a-line proportion",
                "visible check: confirm drop-waist seam reads level and balanced across the full body",
                "visible check: confirm micro print scale stays readable without muddying the fabric surface",
                "visible check: confirm sheer behavior stays intentional rather than accidentally transparent",
                "visible check: confirm hem finish hangs cleanly without torque",
                "visible check: confirm floral print continuity across visible seams",
                "visible check: confirm neck scarf placement stays visually symmetrical",
            ],
        )
        self.assertEqual(
            inferred["open_questions"],
            [
                "open question: confirm fiber_content from approved fabric submission",
                "open question: confirm fabric_weight_gsm from supplier or mill data",
                "open question: confirm lining need based on opacity and wear test outcome",
                "open question: confirm closure_details after sample review of entry and fit",
                "open question: define measurements_pom before tech-pack handoff",
                "open question: define seam_allowance with patternmaking owner",
                "open question: define tolerance by measurement point before production release",
                "open question: confirm bom_grade_trim requirements for elastic, labels, and finishing trims",
            ],
        )

    def test_build_factory_spec_carries_objective_slots_into_known_and_review_cues(self) -> None:
        from temu_y2_women.factory_spec_builder import build_factory_spec

        factory_spec = build_factory_spec(
            request=_objective_request(),
            concept=_objective_concept(),
            selected_strategies=(_objective_strategy(),),
            selected_style_family=_selected_style_family("vacation-romantic"),
        )

        selected = factory_spec["known"]["selected_elements"]
        self.assertEqual(selected["dress_length"]["value"], "mini")
        self.assertEqual(selected["waistline"]["value"], "drop waist")
        self.assertEqual(selected["color_family"]["value"], "white")
        self.assertEqual(selected["print_scale"]["value"], "micro print")
        self.assertEqual(selected["opacity_level"]["value"], "sheer")
        inferred = factory_spec["inferred"]
        self.assertIn(
            "fit cue: confirm drop-waist placement does not collapse the skirt balance",
            inferred["fit_review_cues"],
        )
        self.assertIn(
            "visible check: confirm micro print scale stays readable without muddying the fabric surface",
            inferred["visible_construction_checks"],
        )
        self.assertIn(
            "commercial cue: keep white color direction and sheer balance commercially readable in first-glance imagery",
            inferred["commercial_review_cues"],
        )
        self.assertEqual(factory_spec["known"]["selected_style_family_id"], "vacation-romantic")
        self.assertIn(
            "style family review context: vacation-romantic",
            inferred["commercial_review_context"],
        )

    def test_build_factory_spec_surfaces_editorial_value_specific_review_notes(self) -> None:
        from temu_y2_women.factory_spec_builder import build_factory_spec

        factory_spec = build_factory_spec(
            request=_objective_request(),
            concept=_editorial_concept(),
            selected_strategies=(_objective_strategy(),),
            selected_style_family=_selected_style_family("vacation-romantic"),
        )

        inferred = factory_spec["inferred"]
        self.assertIn(
            "babydoll silhouette should keep easy high-waist volume without looking oversized",
            inferred["fit_intent"],
        )
        self.assertEqual(
            inferred["fabric_review_focus"],
            [
                "confirm linen-blend texture, breathable handfeel, and stable color clarity",
                "check drape stays airy and separated without reading stiff or collapsed",
            ],
        )
        self.assertEqual(
            inferred["detail_review_focus"],
            [
                "verify bubble-hem turnback stays even, full, and repeatable around the skirt",
                "confirm bubble-hem volume stays balanced without torque or collapse",
            ],
        )
        self.assertIn(
            "sample review: confirm linen blend keeps airy texture, breathable separation, and stable drape in the finished dress",
            inferred["sample_review_watchpoints"],
        )
        self.assertIn(
            "qa review: check bubble-hem turnback, fullness, and seam balance for a stable rounded shape",
            inferred["qa_review_notes"],
        )
        self.assertIn(
            "fit cue: keep babydoll volume lifted and easy without turning boxy through the body",
            inferred["fit_review_cues"],
        )
        self.assertIn(
            "visible check: confirm bubble-hem volume reads even and rounded across the skirt",
            inferred["visible_construction_checks"],
        )

    def test_build_factory_spec_includes_overlay_strategy_reason_when_present(self) -> None:
        from temu_y2_women.factory_spec_builder import build_factory_spec

        factory_spec = build_factory_spec(
            request=_objective_request(),
            concept=_objective_concept(),
            selected_strategies=(_objective_strategy(), _overlay_strategy()),
            selected_style_family=_selected_style_family("vacation-romantic"),
        )

        inferred = factory_spec["inferred"]
        self.assertIn(
            "seasonal review context: matched summer vacation window; product image evidence overlay",
            inferred["commercial_review_context"],
        )
        self.assertIn(
            "commercial cue: seasonal review should stay anchored to matched summer vacation window; product image evidence overlay",
            inferred["commercial_review_cues"],
        )


def _build_success_inputs(
    fixture_name: str,
) -> tuple[object, object, tuple[object, ...]]:
    from temu_y2_women.composition_engine import compose_concept
    from temu_y2_women.evidence_paths import EvidencePaths
    from temu_y2_women.evidence_repository import load_elements, load_strategy_templates, retrieve_candidates
    from temu_y2_women.request_normalizer import normalize_request
    from temu_y2_women.style_family_repository import load_style_families
    from temu_y2_women.style_family_selector import select_style_family
    from temu_y2_women.strategy_selector import select_strategies

    payload = _read_request(fixture_name)
    evidence_paths = EvidencePaths.defaults()
    request = normalize_request(payload)
    selected_style_family = select_style_family(
        request,
        load_style_families(
            path=evidence_paths.style_families_path,
            elements_path=evidence_paths.elements_path,
            taxonomy_path=evidence_paths.taxonomy_path,
        ),
    )
    strategies = load_strategy_templates(
        path=evidence_paths.strategies_path,
        taxonomy_path=evidence_paths.taxonomy_path,
        elements_path=evidence_paths.elements_path,
    )
    strategy_result = select_strategies(request, strategies)
    elements = load_elements(
        path=evidence_paths.elements_path,
        taxonomy_path=evidence_paths.taxonomy_path,
    )
    grouped_candidates, _ = retrieve_candidates(
        request,
        elements,
        strategy_result.selected,
        selected_style_family=selected_style_family,
    )
    concept = compose_concept(request, grouped_candidates)
    return request, concept, strategy_result.selected


def _read_request(filename: str) -> dict[str, object]:
    return json.loads((_REQUEST_FIXTURE_DIR / filename).read_text(encoding="utf-8"))


def _objective_request() -> NormalizedRequest:
    from datetime import date

    return NormalizedRequest(
        category="dress",
        target_market="US",
        target_launch_date=date(2026, 6, 15),
        mode="A",
        price_band="mid",
        occasion_tags=("vacation",),
        must_have_tags=("floral",),
        avoid_tags=("bodycon",),
        style_family=None,
    )


def _objective_concept() -> ComposedConcept:
    return ComposedConcept(
        category="dress",
        concept_score=0.94,
        selected_elements={
            "silhouette": ComposedElement("dress-silhouette-a-line-001", "a-line"),
            "fabric": ComposedElement("dress-fabric-cotton-poplin-001", "cotton poplin"),
            "neckline": ComposedElement("dress-neckline-square-001", "square neckline"),
            "sleeve": ComposedElement("dress-sleeve-flutter-001", "flutter sleeve"),
            "dress_length": ComposedElement("dress-length-mini-001", "mini"),
            "waistline": ComposedElement("dress-waistline-drop-waist-001", "drop waist"),
            "color_family": ComposedElement("dress-color-family-white-001", "white"),
            "pattern": ComposedElement("dress-pattern-polka-dot-001", "polka dot"),
            "print_scale": ComposedElement("dress-print-scale-micro-print-001", "micro print"),
            "opacity_level": ComposedElement("dress-opacity-level-sheer-001", "sheer"),
            "detail": ComposedElement("dress-detail-neck-scarf-001", "neck scarf"),
        },
        style_summary=("summer-ready", "vacation-oriented", "feminine silhouette"),
        constraint_notes=("must_have_tags satisfied: floral",),
    )


def _editorial_concept() -> ComposedConcept:
    return ComposedConcept(
        category="dress",
        concept_score=0.93,
        selected_elements={
            "silhouette": ComposedElement("dress-silhouette-babydoll-001", "babydoll"),
            "fabric": ComposedElement("dress-fabric-linen-blend-001", "linen blend"),
            "neckline": ComposedElement("dress-neckline-halter-001", "halter neckline"),
            "sleeve": ComposedElement("dress-sleeve-puff-001", "short puff sleeve"),
            "dress_length": ComposedElement("dress-length-mini-001", "mini"),
            "color_family": ComposedElement("dress-color-family-brown-001", "brown"),
            "pattern": ComposedElement("dress-pattern-gingham-check-001", "gingham check"),
            "detail": ComposedElement("dress-detail-bubble-hem-001", "bubble hem"),
        },
        style_summary=("editorial-trend-led", "summer-ready", "commercially grounded"),
        constraint_notes=(),
    )


def _objective_strategy() -> SelectedStrategy:
    return SelectedStrategy(
        strategy=StrategyTemplate(
            strategy_id="dress-us-summer-vacation",
            category="dress",
            target_market="US",
            priority=10,
            date_window=DateWindow(start="05-15", end="08-31"),
            occasion_tags=("vacation",),
            boost_tags=("summer", "floral"),
            suppress_tags=("velvet",),
            slot_preferences={"silhouette": ("a-line",)},
            score_boost=0.12,
            score_cap=0.2,
            prompt_hints=("fresh summer styling", "vacation-ready feminine silhouette"),
            reason_template="launch date falls into the US summer vacation window",
            status="active",
        ),
        reason="matched summer vacation window",
    )


def _overlay_strategy() -> SelectedStrategy:
    return SelectedStrategy(
        strategy=StrategyTemplate(
            strategy_id="dress-us-summer-vacation-product-image",
            category="dress",
            target_market="US",
            priority=1,
            date_window=DateWindow(start="01-01", end="12-31"),
            occasion_tags=("vacation",),
            boost_tags=("summer", "vacation", "feminine"),
            suppress_tags=(),
            slot_preferences={"detail": ("waist tie",), "dress_length": ("mini",)},
            score_boost=0.08,
            score_cap=0.12,
            prompt_hints=("product image overlay",),
            reason_template="product image evidence overlay",
            status="active",
        ),
        reason="product image evidence overlay",
    )


def _selected_style_family(style_family_id: str) -> SelectedStyleFamily:
    return SelectedStyleFamily(
        profile=StyleFamilyProfile(
            style_family_id=style_family_id,
            hard_slot_values={},
            soft_slot_values={},
            blocked_slot_values={},
            subject_hint="fixture subject",
            scene_hint="fixture scene",
            lighting_hint="fixture lighting",
            styling_hint="fixture styling",
            constraint_hints=(),
            fallback_reason="fixture",
            status="active",
        ),
        selection_mode="explicit",
        reason="fixture",
    )
