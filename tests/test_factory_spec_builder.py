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
