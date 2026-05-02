from __future__ import annotations

import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


class StyleFamilyVisualFeedbackProposalTest(unittest.TestCase):
    def test_build_proposal_recommends_only_shared_high_delta_changes(self) -> None:
        from temu_y2_women.style_family_visual_feedback_proposal import build_visual_feedback_apply_proposal

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dry_run_path = root / "dry_run.json"
            _write_dry_run_report(dry_run_path)

            proposal = build_visual_feedback_apply_proposal(
                dry_run_path=dry_run_path,
                minimum_delta=0.04,
                minimum_family_count=2,
            )

        self.assertEqual(proposal["schema_version"], "style-family-visual-feedback-proposal-v1")
        self.assertEqual(proposal["status"], "ready")
        self.assertEqual(proposal["policy"], {"minimum_delta": 0.04, "minimum_family_count": 2})
        self.assertEqual(proposal["summary"]["total_candidates"], 4)
        self.assertEqual(proposal["summary"]["recommended"], 2)
        self.assertEqual(proposal["summary"]["held"], 2)
        self.assertEqual(proposal["summary"]["net_recommended_delta"], 0.1)
        self.assertEqual([item["element_id"] for item in proposal["recommended_changes"]], ["shared-strong", "shared-medium"])
        self.assertEqual(proposal["recommended_changes"][0]["family_count"], 3)
        self.assertEqual(proposal["recommended_changes"][0]["families"], ["city-polished", "clean-minimal", "vacation-romantic"])
        self.assertEqual(proposal["recommended_changes"][0]["recommended_base_score"], 0.86)
        self.assertEqual(proposal["held_changes"][0]["recommendation"], "hold")
        self.assertEqual(proposal["held_changes"][0]["hold_reason"], "below minimum shared-signal threshold")

    def test_build_proposal_rejects_non_dry_run_input(self) -> None:
        from temu_y2_women.style_family_visual_feedback_proposal import build_visual_feedback_apply_proposal

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dry_run_path = root / "dry_run.json"
            _write_json(dry_run_path, {"schema_version": "wrong", "cases": [], "element_changes": []})

            with self.assertRaisesRegex(ValueError, "dry-run schema_version is not supported"):
                build_visual_feedback_apply_proposal(dry_run_path=dry_run_path)


class StyleFamilyVisualFeedbackProposalCliTest(unittest.TestCase):
    def test_cli_writes_proposal_and_prints_payload(self) -> None:
        from temu_y2_women.style_family_visual_feedback_proposal_cli import main

        stdout = io.StringIO()
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dry_run_path = root / "dry_run.json"
            output_path = root / "proposal.json"
            _write_dry_run_report(dry_run_path)

            with patch("sys.stdout", stdout):
                exit_code = main(
                    [
                        "build",
                        "--dry-run",
                        str(dry_run_path),
                        "--output",
                        str(output_path),
                        "--minimum-delta",
                        "0.04",
                        "--minimum-family-count",
                        "2",
                    ]
                )
            printed = json.loads(stdout.getvalue())
            written = _read_json(output_path)

        self.assertEqual(exit_code, 0)
        self.assertEqual(printed, written)
        self.assertEqual(written["summary"]["recommended"], 2)


def _write_dry_run_report(path: Path) -> None:
    _write_json(
        path,
        {
            "schema_version": "style-family-visual-feedback-dry-run-v1",
            "status": "applied",
            "cases": [
                _case("vacation-romantic", ["solo-a", "shared-strong", "shared-medium"]),
                _case("clean-minimal", ["shared-strong"]),
                _case("city-polished", ["shared-strong", "shared-medium", "solo-b"]),
            ],
            "element_changes": [
                _change("solo-a", "detail", "neck scarf", 0.72, 0.74),
                _change("shared-strong", "waistline", "natural waist", 0.8, 0.86),
                _change("shared-medium", "neckline", "square neckline", 0.73, 0.77),
                _change("solo-b", "pattern", "stripe print", 0.73, 0.75),
            ],
        },
    )


def _case(family: str, element_ids: list[str]) -> dict[str, object]:
    return {
        "style_family_id": family,
        "feedback_decision": "keep",
        "status": "applied",
        "affected_element_ids": element_ids,
    }


def _change(element_id: str, slot: str, value: str, original: float, dry_run: float) -> dict[str, object]:
    return {
        "element_id": element_id,
        "slot": slot,
        "value": value,
        "original_base_score": original,
        "dry_run_base_score": dry_run,
        "delta": round(dry_run - original, 4),
    }


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))
