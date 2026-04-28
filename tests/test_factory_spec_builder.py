from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
import unittest


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
        self.assertEqual(
            factory_spec["known"]["selected_elements"]["dress_length"]["value"],
            "mini",
        )
        self.assertEqual(
            factory_spec["known"]["selected_elements"]["waistline"]["value"],
            "drop waist",
        )
        self.assertEqual(
            factory_spec["known"]["selected_elements"]["color_family"]["value"],
            "white",
        )
        self.assertEqual(
            factory_spec["known"]["selected_elements"]["opacity_level"]["value"],
            "opaque",
        )
        self.assertEqual(
            factory_spec["known"]["selected_elements"]["print_scale"]["value"],
            "micro print",
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
            "verify the visible construction detail is cleanly attached and repeatable in production",
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
        )

        inferred = factory_spec["inferred"]
        self._assert_success_review_watchpoints(inferred)
        self._assert_success_review_cues(inferred)

    def test_build_factory_spec_adds_visible_checks_and_open_questions(self) -> None:
        from temu_y2_women.factory_spec_builder import build_factory_spec

        request, concept, selected_strategies = _build_success_inputs(
            "success-summer-vacation-mode-a.json"
        )
        factory_spec = build_factory_spec(
            request=request,
            concept=concept,
            selected_strategies=selected_strategies,
        )

        inferred = factory_spec["inferred"]
        self.assertEqual(
            inferred["visible_construction_checks"][:6],
            [
                "visible check: confirm square neckline edge finish stays clean and even",
                "visible check: confirm visible detail construction stays clean and balanced",
                "visible check: confirm flutter sleeve openings keep soft volume with clean finishing",
                "visible check: confirm waist seam placement supports balanced a-line proportion",
                "visible check: confirm hem finish hangs cleanly without torque",
                "visible check: confirm floral print continuity across visible seams",
            ],
        )
        self.assertEqual(
            inferred["visible_construction_checks"][-1],
            "visible check: confirm neck scarf placement stays visually symmetrical",
        )
        self.assertIn(
            "visible check: confirm drop waist seam stays level and visually intentional around the body",
            inferred["visible_construction_checks"],
        )
        self.assertIn(
            "visible check: confirm micro print stays crisp without muddying at seams or gathers",
            inferred["visible_construction_checks"],
        )
        self.assertIn(
            "visible check: confirm opaque coverage stays consistent in bright light",
            inferred["visible_construction_checks"],
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

    def test_build_factory_spec_adds_objective_slot_cues_for_overridden_concept(self) -> None:
        from temu_y2_women.factory_spec_builder import build_factory_spec

        request, concept, selected_strategies = _build_success_inputs(
            "success-summer-vacation-mode-a.json"
        )
        concept = _override_concept_slots(
            concept,
            opacity_level="sheer",
            color_family="white",
            print_scale="micro print",
            waistline="drop waist",
            dress_length="mini",
        )

        factory_spec = build_factory_spec(
            request=request,
            concept=concept,
            selected_strategies=selected_strategies,
        )

        known_selected = factory_spec["known"]["selected_elements"]
        self.assertEqual(known_selected["opacity_level"]["value"], "sheer")
        self.assertEqual(known_selected["color_family"]["value"], "white")
        self.assertEqual(known_selected["print_scale"]["value"], "micro print")
        self.assertEqual(known_selected["waistline"]["value"], "drop waist")
        self.assertEqual(known_selected["dress_length"]["value"], "mini")

        inferred = factory_spec["inferred"]
        self.assertIn(
            "commercial cue: review white sheer execution for coverage, layering, and online readability",
            inferred["commercial_review_cues"],
        )
        self.assertIn(
            "commercial cue: make sure micro print still reads clearly in thumbnails and first-glance product imagery",
            inferred["commercial_review_cues"],
        )
        self.assertIn(
            "visible check: confirm sheer areas stay intentional and balanced across layers and seam zones",
            inferred["visible_construction_checks"],
        )
        self.assertNotIn(
            "visible check: confirm opaque coverage stays consistent in bright light",
            inferred["visible_construction_checks"],
        )

    def _assert_success_review_watchpoints(self, inferred: dict[str, list[str]]) -> None:
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
                "qa review: check visible detail attachment stays secure, even, and repeatable",
                "qa review: check flutter sleeve openings and hem finish for clean turnback and stable shape",
                "qa review: check floral print alignment and continuity across visible seams",
            ],
        )

    def _assert_success_review_cues(self, inferred: dict[str, list[str]]) -> None:
        fit_cues = (
            "fit cue: protect non-bodycon ease through bust, waist, and skirt sweep",
            "fit cue: keep a-line volume easy and mobile instead of collapsing into a narrow shape",
            "fit cue: verify mini length keeps intended coverage in motion and while seated",
            "fit cue: confirm drop waist seam lands low enough to read intentional without dragging the torso",
        )
        commercial_cues = (
            "commercial cue: seasonal review should stay anchored to launch date falls in the US summer vacation window and occasion tags align to vacation demand",
            "commercial cue: keep vacation use obvious from first-glance silhouette, fabric, and print direction",
            "commercial cue: keep visible construction commercially realistic for mid pricing",
            "commercial cue: make sure micro print still reads clearly in thumbnails and first-glance product imagery",
        )
        for cue in fit_cues:
            self.assertIn(cue, inferred["fit_review_cues"])
        for cue in commercial_cues:
            self.assertIn(cue, inferred["commercial_review_cues"])


def _build_success_inputs(
    fixture_name: str,
) -> tuple[object, object, tuple[object, ...]]:
    from temu_y2_women.composition_engine import compose_concept
    from temu_y2_women.evidence_paths import EvidencePaths
    from temu_y2_women.evidence_repository import load_elements, load_strategy_templates, retrieve_candidates
    from temu_y2_women.request_normalizer import normalize_request
    from temu_y2_women.strategy_selector import select_strategies

    payload = _read_request(fixture_name)
    evidence_paths = EvidencePaths.defaults()
    request = normalize_request(payload)
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
    grouped_candidates, _ = retrieve_candidates(request, elements, strategy_result.selected)
    concept = compose_concept(request, grouped_candidates)
    return request, concept, strategy_result.selected


def _read_request(filename: str) -> dict[str, object]:
    return json.loads((_REQUEST_FIXTURE_DIR / filename).read_text(encoding="utf-8"))


def _override_concept_slots(concept: object, **slot_values: str) -> object:
    from temu_y2_women.models import ComposedElement

    selected_elements = dict(concept.selected_elements)
    for slot, value in slot_values.items():
        existing = selected_elements.get(slot)
        element_id = "" if existing is None else existing.element_id
        selected_elements[slot] = ComposedElement(element_id=element_id, value=value)
    return replace(concept, selected_elements=selected_elements)
