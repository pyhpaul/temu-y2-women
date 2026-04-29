from __future__ import annotations

import json
from pathlib import Path
import unittest


_REQUEST_FIXTURE_DIR = Path("tests/fixtures/requests/dress-generation-mvp")


class OrchestratorTest(unittest.TestCase):
    def test_successful_mode_a_flow(self) -> None:
        from temu_y2_women.orchestrator import generate_dress_concept

        result = generate_dress_concept(_read_request("success-summer-vacation-mode-a.json"))

        self.assertEqual(result["request_normalized"]["mode"], "A")
        self.assertEqual(result["selected_style_family"]["style_family_id"], "vacation-romantic")
        self.assertEqual(result["selected_strategies"][0]["strategy_id"], "dress-us-summer-vacation")
        self.assertEqual(result["prompt_bundle"]["mode"], "A")
        self.assertEqual(result["prompt_bundle"]["template_version"], "visual-prompt-v2")
        self.assertIn("product-first presentation", result["prompt_bundle"]["prompt"])
        self.assertIn("mini length", result["prompt_bundle"]["prompt"])
        self.assertIn("white color story", result["prompt_bundle"]["prompt"])
        self.assertEqual(len(result["prompt_bundle"]["detail_prompts"]), 3)
        self.assertEqual(result["factory_spec"]["schema_version"], "factory-spec-v1")
        self.assertEqual(
            result["factory_spec"]["known"]["selected_elements"]["fabric"]["value"],
            "cotton poplin",
        )
        self.assertEqual(
            result["factory_spec"]["known"]["selected_elements"]["dress_length"]["value"],
            "mini",
        )
        self.assertEqual(result["factory_spec"]["known"]["selected_style_family_id"], "vacation-romantic")
        self.assertIn(
            "print continuity across seams",
            result["factory_spec"]["inferred"]["visible_construction_priorities"],
        )
        self.assertIn(
            "sample review: confirm cotton poplin keeps crisp opacity and breathable structure in the finished dress",
            result["factory_spec"]["inferred"]["sample_review_watchpoints"],
        )
        self.assertIn(
            "qa review: check neck scarf attachment, symmetry, and edge finish for clean repeatability",
            result["factory_spec"]["inferred"]["qa_review_notes"],
        )
        self.assertIn(
            "fit cue: protect non-bodycon ease through bust, waist, and skirt sweep",
            result["factory_spec"]["inferred"]["fit_review_cues"],
        )
        self.assertEqual(result["composed_concept"]["selected_elements"]["silhouette"]["value"], "a-line")
        self.assertEqual(result["composed_concept"]["selected_elements"]["waistline"]["value"], "drop waist")
        self.assertIn("must_have_tags satisfied: floral", result["composed_concept"]["constraint_notes"])
        self.assertIn("avoid_tags removed: bodycon", " ".join(result["warnings"]))

    def test_successful_baseline_mode_a_flow(self) -> None:
        from temu_y2_women.orchestrator import generate_dress_concept

        result = generate_dress_concept(_read_request("success-baseline-transitional-mode-a.json"))

        self.assertEqual(result["request_normalized"]["mode"], "A")
        self.assertEqual(result["selected_style_family"]["style_family_id"], "clean-minimal")
        self.assertEqual(result["selected_strategies"][0]["strategy_id"], "dress-us-baseline")
        self.assertEqual(result["prompt_bundle"]["mode"], "A")
        self.assertEqual(
            result["composed_concept"]["selected_elements"]["neckline"]["value"],
            "jewel neckline",
        )
        self.assertEqual(
            result["composed_concept"]["selected_elements"]["waistline"]["value"],
            "natural waist",
        )
        self.assertIn(
            "must_have_tags satisfied: transitional",
            result["composed_concept"]["constraint_notes"],
        )

    def test_explicit_city_polished_flow_uses_city_specific_slots(self) -> None:
        from temu_y2_women.orchestrator import generate_dress_concept

        result = generate_dress_concept(
            {
                "category": "dress",
                "target_market": "US",
                "target_launch_date": "2026-09-15",
                "mode": "A",
                "price_band": "mid",
                "occasion_tags": ["casual"],
                "avoid_tags": ["bodycon"],
                "style_family": "city-polished",
            }
        )

        self.assertEqual(result["selected_style_family"]["style_family_id"], "city-polished")
        self.assertEqual(
            result["composed_concept"]["selected_elements"]["neckline"]["value"],
            "square neckline",
        )
        self.assertEqual(
            result["composed_concept"]["selected_elements"]["waistline"]["value"],
            "natural waist",
        )
        self.assertEqual(
            result["composed_concept"]["selected_elements"]["detail"]["value"],
            "tailored seam panel",
        )

    def test_successful_mode_b_flow(self) -> None:
        from temu_y2_women.orchestrator import generate_dress_concept

        result = generate_dress_concept(_read_request("success-summer-vacation-mode-b.json"))

        self.assertEqual(result["request_normalized"]["mode"], "B")
        self.assertEqual(result["selected_style_family"]["style_family_id"], "vacation-romantic")
        self.assertEqual(result["prompt_bundle"]["mode"], "B")
        self.assertEqual(result["factory_spec"]["schema_version"], "factory-spec-v1")
        self.assertIn("construction review clarity", " ".join(result["prompt_bundle"]["render_notes"]))
        self.assertTrue(result["prompt_bundle"]["development_notes"])
        self.assertEqual(len(result["prompt_bundle"]["detail_prompts"]), 3)

    def test_no_candidates_failure_flow(self) -> None:
        from temu_y2_women.orchestrator import generate_dress_concept

        result = generate_dress_concept(_read_request("failure-no-candidates-summer-vacation.json"))

        self.assertEqual(result["error"]["code"], "NO_CANDIDATES")

    def test_constraint_conflict_failure_flow(self) -> None:
        from temu_y2_women.orchestrator import generate_dress_concept

        result = generate_dress_concept(_read_request("failure-constraint-conflict-summer-vacation.json"))

        self.assertEqual(result["error"]["code"], "CONSTRAINT_CONFLICT")

    def test_unknown_style_family_fails_closed(self) -> None:
        from temu_y2_women.orchestrator import generate_dress_concept

        result = generate_dress_concept(
            {
                "category": "dress",
                "target_market": "US",
                "target_launch_date": "2026-06-15",
                "mode": "A",
                "style_family": "unknown-family",
            }
        )

        self.assertEqual(result["error"]["code"], "INVALID_REQUEST")

    def test_explicit_style_family_conflict_fails_closed(self) -> None:
        from temu_y2_women.orchestrator import generate_dress_concept

        result = generate_dress_concept(
            {
                "category": "dress",
                "target_market": "US",
                "target_launch_date": "2026-06-15",
                "mode": "A",
                "occasion_tags": ["party"],
                "avoid_tags": ["bodycon"],
                "style_family": "party-fitted",
            }
        )

        self.assertEqual(result["error"]["code"], "CONSTRAINT_CONFLICT")

    def test_non_us_market_fails_in_mvp(self) -> None:
        from temu_y2_women.orchestrator import generate_dress_concept

        result = generate_dress_concept(
            {
                "category": "dress",
                "target_market": "EU",
                "target_launch_date": "2026-06-15",
                "mode": "A",
            }
        )

        self.assertEqual(result["error"]["code"], "INVALID_REQUEST")


def _read_request(filename: str) -> dict[str, object]:
    return json.loads((_REQUEST_FIXTURE_DIR / filename).read_text(encoding="utf-8"))
