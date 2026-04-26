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
        self.assertEqual(result["selected_strategies"][0]["strategy_id"], "dress-us-summer-vacation")
        self.assertEqual(result["prompt_bundle"]["mode"], "A")
        self.assertIn("product appeal", " ".join(result["prompt_bundle"]["render_notes"]))
        self.assertEqual(result["composed_concept"]["selected_elements"]["silhouette"]["value"], "a-line")
        self.assertIn("must_have_tags satisfied: floral", result["composed_concept"]["constraint_notes"])
        self.assertIn("avoid_tags removed: bodycon", " ".join(result["warnings"]))

    def test_successful_mode_b_flow(self) -> None:
        from temu_y2_women.orchestrator import generate_dress_concept

        result = generate_dress_concept(_read_request("success-summer-vacation-mode-b.json"))

        self.assertEqual(result["request_normalized"]["mode"], "B")
        self.assertEqual(result["prompt_bundle"]["mode"], "B")
        self.assertIn("garment construction clarity", " ".join(result["prompt_bundle"]["render_notes"]))
        self.assertTrue(result["prompt_bundle"]["development_notes"])

    def test_no_candidates_failure_flow(self) -> None:
        from temu_y2_women.orchestrator import generate_dress_concept

        result = generate_dress_concept(_read_request("failure-no-candidates-summer-vacation.json"))

        self.assertEqual(result["error"]["code"], "NO_CANDIDATES")

    def test_constraint_conflict_failure_flow(self) -> None:
        from temu_y2_women.orchestrator import generate_dress_concept

        result = generate_dress_concept(_read_request("failure-constraint-conflict-summer-vacation.json"))

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
