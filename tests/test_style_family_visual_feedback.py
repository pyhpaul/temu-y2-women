from __future__ import annotations

import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


class StyleFamilyVisualFeedbackTest(unittest.TestCase):
    def test_prepare_visual_feedback_reviews_writes_keep_and_reject_reviews(self) -> None:
        from temu_y2_women.style_family_visual_feedback import prepare_visual_feedback_reviews

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_path = root / "manifest.json"
            quality_path = root / "visual_quality_review.json"
            output_dir = root / "feedback"
            _write_inputs(root, manifest_path, quality_path)

            report = prepare_visual_feedback_reviews(
                manifest_path=manifest_path,
                quality_review_path=quality_path,
                output_dir=output_dir,
            )

            vacation_review = _read_json(output_dir / "vacation-romantic-feedback_review.json")
            party_review = _read_json(output_dir / "party-fitted-feedback_review.json")

        self.assertEqual(report["schema_version"], "style-family-visual-feedback-batch-v1")
        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["summary"], {"total": 2, "keep": 1, "reject": 1, "written": 2})
        self.assertEqual(report["cases"][0]["style_family_id"], "vacation-romantic")
        self.assertEqual(report["cases"][0]["feedback_decision"], "keep")
        self.assertEqual(report["cases"][1]["feedback_decision"], "reject")
        self.assertEqual(vacation_review["decision"], "keep")
        self.assertEqual(party_review["decision"], "reject")
        self.assertIn("style_family=vacation-romantic", vacation_review["notes"])
        self.assertIn("average_score=4.4", vacation_review["notes"])
        self.assertIn("revision_reasons=hands need cleanup", party_review["notes"])
        self.assertEqual(vacation_review["feedback_target"]["selected_element_ids"], ["vacation-romantic-element"])

    def test_prepare_visual_feedback_reviews_rejects_quality_case_missing_from_manifest(self) -> None:
        from temu_y2_women.style_family_visual_feedback import prepare_visual_feedback_reviews

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_path = root / "manifest.json"
            quality_path = root / "visual_quality_review.json"
            _write_manifest(root, manifest_path, families=("vacation-romantic",))
            _write_quality_review(quality_path, families=("vacation-romantic", "party-fitted"))

            with self.assertRaisesRegex(ValueError, "Missing manifest case for party-fitted"):
                prepare_visual_feedback_reviews(
                    manifest_path=manifest_path,
                    quality_review_path=quality_path,
                    output_dir=root / "feedback",
                )


class StyleFamilyVisualFeedbackCliTest(unittest.TestCase):
    def test_cli_writes_feedback_batch_and_prints_report(self) -> None:
        from temu_y2_women.style_family_visual_feedback_cli import main

        stdout = io.StringIO()
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_path = root / "manifest.json"
            quality_path = root / "visual_quality_review.json"
            output_dir = root / "feedback"
            _write_inputs(root, manifest_path, quality_path)

            with patch("sys.stdout", stdout):
                exit_code = main(
                    [
                        "prepare",
                        "--manifest",
                        str(manifest_path),
                        "--quality-review",
                        str(quality_path),
                        "--output-dir",
                        str(output_dir),
                    ]
                )
            printed = json.loads(stdout.getvalue())
            batch_exists = (output_dir / "visual_feedback_batch.json").exists()
            party_review_exists = (output_dir / "party-fitted-feedback_review.json").exists()

        self.assertEqual(exit_code, 0)
        self.assertEqual(printed["status"], "ready")
        self.assertTrue(batch_exists)
        self.assertTrue(party_review_exists)


def _write_inputs(root: Path, manifest_path: Path, quality_path: Path) -> None:
    families = ("vacation-romantic", "party-fitted")
    _write_manifest(root, manifest_path, families=families)
    _write_quality_review(quality_path, families=families)


def _write_manifest(root: Path, path: Path, *, families: tuple[str, ...]) -> None:
    cases = []
    for family in families:
        concept_path = root / "concepts" / f"{family}-concept_result.json"
        _write_json(concept_path, _concept_result(family))
        cases.append({"style_family_id": family, "concept_path": str(concept_path)})
    _write_json(path, {"schema_version": "style-family-anchor-validation-v1", "cases": cases})


def _write_quality_review(path: Path, *, families: tuple[str, ...]) -> None:
    cases = [_quality_case(family) for family in families]
    _write_json(
        path,
        {
            "schema_version": "style-family-visual-quality-review-v1",
            "status": "needs_revision",
            "criteria": ["family_differentiation", "prompt_adherence", "artifact_control"],
            "cases": cases,
        },
    )


def _quality_case(family: str) -> dict[str, object]:
    needs_revision = family == "party-fitted"
    return {
        "style_family_id": family,
        "decision": "needs_revision" if needs_revision else "accepted",
        "scores": {"family_differentiation": 5, "prompt_adherence": 4, "artifact_control": 4},
        "average_score": 4.2 if needs_revision else 4.4,
        "revision_reasons": ["hands need cleanup"] if needs_revision else [],
        "note": f"{family} visual note",
    }


def _concept_result(family: str) -> dict[str, object]:
    return {
        "request_normalized": {
            "category": "dress",
            "target_market": "US",
            "target_launch_date": "2026-09-15",
            "mode": "A",
            "price_band": "mid",
            "occasion_tags": ["casual"],
            "must_have_tags": [],
            "avoid_tags": ["bodycon"],
            "style_family": family,
        },
        "composed_concept": {
            "category": "dress",
            "concept_score": 0.8,
            "selected_elements": {
                "silhouette": {
                    "element_id": f"{family}-element",
                    "value": "a-line",
                }
            },
        },
    }


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))
