from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
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

    def test_product_image_promoted_overlay_influences_runtime_selection(self) -> None:
        from temu_y2_women.evidence_paths import EvidencePaths
        from temu_y2_women.evidence_promotion import apply_reviewed_dress_promotion, prepare_dress_promotion_review
        from temu_y2_women.orchestrator import generate_dress_concept
        from temu_y2_women.product_image_signal_run import run_product_image_signal_ingestion

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            workspace_root = _seed_workspace_evidence(temp_root)
            manifest_path = _write_product_image_manifest(temp_root)
            run_report = run_product_image_signal_ingestion(
                input_path=manifest_path,
                output_root=temp_root / "runs",
                observed_at="2026-04-30T07:30:00Z",
                observe_image=_fake_product_image_observer_with_new_detail,
            )
            run_dir = temp_root / "runs" / run_report["run_id"]
            reviewed = prepare_dress_promotion_review(
                draft_elements_path=run_dir / "draft_elements.json",
                draft_strategy_hints_path=run_dir / "draft_strategy_hints.json",
                active_elements_path=workspace_root / "data" / "mvp" / "dress" / "elements.json",
                active_strategies_path=workspace_root / "data" / "mvp" / "dress" / "strategy_templates.json",
            )
            for item in reviewed["elements"]:
                item["decision"] = "accept"
            for item in reviewed["strategy_hints"]:
                item["decision"] = "accept"
            reviewed_path = temp_root / "reviewed.json"
            reviewed_path.write_text(json.dumps(reviewed), encoding="utf-8")
            apply_reviewed_dress_promotion(
                reviewed_path=reviewed_path,
                draft_elements_path=run_dir / "draft_elements.json",
                draft_strategy_hints_path=run_dir / "draft_strategy_hints.json",
                active_elements_path=workspace_root / "data" / "mvp" / "dress" / "elements.json",
                active_strategies_path=workspace_root / "data" / "mvp" / "dress" / "strategy_templates.json",
                report_path=temp_root / "promotion_report.json",
            )

            result = generate_dress_concept(
                _read_request("success-summer-vacation-mode-b.json"),
                evidence_paths=EvidencePaths(
                    elements_path=workspace_root / "data" / "mvp" / "dress" / "elements.json",
                    strategies_path=workspace_root / "data" / "mvp" / "dress" / "strategy_templates.json",
                    taxonomy_path=workspace_root / "data" / "mvp" / "dress" / "evidence_taxonomy.json",
                ),
            )

        self.assertEqual(
            [item["strategy_id"] for item in result["selected_strategies"]],
            ["dress-us-summer-vacation", "dress-us-summer-vacation-product-image"],
        )
        self.assertEqual(result["composed_concept"]["selected_elements"]["detail"]["value"], "waist tie")
        self.assertEqual(result["composed_concept"]["selected_elements"]["neckline"]["value"], "square neckline")
        self.assertEqual(result["composed_concept"]["selected_elements"]["dress_length"]["value"], "mini")


def _read_request(filename: str) -> dict[str, object]:
    return json.loads((_REQUEST_FIXTURE_DIR / filename).read_text(encoding="utf-8"))


def _seed_workspace_evidence(temp_root: Path) -> Path:
    workspace_root = temp_root / "workspace"
    evidence_root = workspace_root / "data" / "mvp" / "dress"
    evidence_root.mkdir(parents=True)
    for name in ("elements.json", "strategy_templates.json", "evidence_taxonomy.json"):
        src = Path("data/mvp/dress") / name
        (evidence_root / name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return workspace_root


def _write_product_image_manifest(temp_root: Path) -> Path:
    from tests.test_evidence_promotion import _write_product_image_manifest as _write_manifest

    return _write_manifest(temp_root)


def _fake_product_image_observer_with_new_detail(image: dict[str, object]) -> dict[str, object]:
    from tests.test_evidence_promotion import _fake_product_image_observer_with_new_detail as _observe

    return _observe(image)
