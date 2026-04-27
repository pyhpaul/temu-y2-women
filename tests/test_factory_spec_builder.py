from __future__ import annotations

import json
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
            "smocked bodice",
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
            "verify smocking stitch consistency, recovery, and clean attachment",
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
        self.assertEqual(
            inferred["sample_review_watchpoints"],
            [
                "sample review: confirm cotton poplin keeps crisp opacity and breathable structure in the finished dress",
                "sample review: verify square neckline, smocked bodice, and flutter sleeve read clearly in the first sample",
                "sample review: check floral print continuity and placement across bodice, waist seam, and skirt panels",
                "sample review: confirm a-line shape stays easy and non-bodycon through waist-to-hem movement",
            ],
        )
        self.assertEqual(
            inferred["qa_review_notes"],
            [
                "qa review: check square neckline edge finish for symmetry and clean top-line shape",
                "qa review: check smocking rows for even tension, secure attachment, and balanced visual spacing",
                "qa review: check flutter sleeve openings and hem finish for clean turnback and stable shape",
                "qa review: check floral print alignment and continuity across visible seams",
            ],
        )
        self.assertEqual(
            inferred["fit_review_cues"],
            [
                "fit cue: protect non-bodycon ease through bust, waist, and skirt sweep",
                "fit cue: keep a-line volume easy and mobile instead of collapsing into a narrow shape",
                "fit cue: make sure smocked bodice shaping stays flexible rather than restrictive",
            ],
        )
        self.assertEqual(
            inferred["commercial_review_cues"],
            [
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
        )

        inferred = factory_spec["inferred"]
        self.assertEqual(
            inferred["visible_construction_checks"],
            [
                "visible check: confirm square neckline edge finish stays clean and even",
                "visible check: confirm smocked bodice construction stays consistent across the front bodice",
                "visible check: confirm flutter sleeve openings keep soft volume with clean finishing",
                "visible check: confirm waist seam placement supports balanced a-line proportion",
                "visible check: confirm hem finish hangs cleanly without torque",
                "visible check: confirm floral print continuity across visible seams",
                "visible check: confirm smocked detail placement stays visually symmetrical",
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
