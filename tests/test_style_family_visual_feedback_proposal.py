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

    def test_apply_proposal_updates_only_recommended_changes_and_writes_report(self) -> None:
        from temu_y2_women.style_family_visual_feedback_proposal import apply_visual_feedback_proposal

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            proposal_path = root / "proposal.json"
            elements_path = root / "elements.json"
            report_path = root / "apply-report.json"
            _write_apply_proposal(proposal_path)
            _write_elements(elements_path)

            report = apply_visual_feedback_proposal(
                proposal_path=proposal_path,
                active_elements_path=elements_path,
                taxonomy_path=Path("data/mvp/dress/evidence_taxonomy.json"),
                report_path=report_path,
            )
            written_report = _read_json(report_path)
            updated = _read_json(elements_path)

        self.assertEqual(report["schema_version"], "style-family-visual-feedback-apply-report-v1")
        self.assertEqual(written_report, report)
        self.assertEqual(report["summary"], {"recommended": 2, "applied": 2, "held": 1, "net_applied_delta": 0.1})
        self.assertEqual(_element_score(updated, "shared-strong"), 0.86)
        self.assertEqual(_element_score(updated, "shared-medium"), 0.77)
        self.assertEqual(_element_score(updated, "held-solo"), 0.72)

    def test_apply_proposal_rejects_stale_active_score_before_writing(self) -> None:
        from temu_y2_women.style_family_visual_feedback_proposal import apply_visual_feedback_proposal

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            proposal_path = root / "proposal.json"
            elements_path = root / "elements.json"
            report_path = root / "apply-report.json"
            _write_apply_proposal(proposal_path)
            _write_elements(elements_path, shared_strong_score=0.81)

            with self.assertRaisesRegex(ValueError, "proposal does not match active evidence"):
                apply_visual_feedback_proposal(
                    proposal_path=proposal_path,
                    active_elements_path=elements_path,
                    taxonomy_path=Path("data/mvp/dress/evidence_taxonomy.json"),
                    report_path=report_path,
                )
            report_exists = report_path.exists()
            unchanged_score = _element_score(_read_json(elements_path), "shared-strong")

        self.assertFalse(report_exists)
        self.assertEqual(unchanged_score, 0.81)


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

    def test_cli_applies_proposal_and_prints_report(self) -> None:
        from temu_y2_women.style_family_visual_feedback_proposal_cli import main

        stdout = io.StringIO()
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            proposal_path = root / "proposal.json"
            elements_path = root / "elements.json"
            report_path = root / "apply-report.json"
            _write_apply_proposal(proposal_path)
            _write_elements(elements_path)

            with patch("sys.stdout", stdout):
                exit_code = main(
                    [
                        "apply",
                        "--proposal",
                        str(proposal_path),
                        "--active-elements",
                        str(elements_path),
                        "--taxonomy",
                        "data/mvp/dress/evidence_taxonomy.json",
                        "--report-output",
                        str(report_path),
                    ]
                )
            printed = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(printed["status"], "applied")
        self.assertEqual(printed["summary"]["applied"], 2)


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


def _write_apply_proposal(path: Path) -> None:
    _write_json(
        path,
        {
            "schema_version": "style-family-visual-feedback-proposal-v1",
            "status": "ready",
            "source_artifacts": {"dry_run_report": "dry-run.json"},
            "policy": {"minimum_delta": 0.04, "minimum_family_count": 2},
            "summary": {"total_candidates": 3, "recommended": 2, "held": 1, "net_recommended_delta": 0.1},
            "recommended_changes": [
                _proposal_change("shared-strong", "waistline", "natural waist", 0.8, 0.86, 0.06, 3, "apply"),
                _proposal_change("shared-medium", "neckline", "square neckline", 0.73, 0.77, 0.04, 2, "apply"),
            ],
            "held_changes": [
                _proposal_change("held-solo", "detail", "neck scarf", 0.72, 0.74, 0.02, 1, "hold"),
            ],
            "candidates": [],
        },
    )


def _proposal_change(
    element_id: str,
    slot: str,
    value: str,
    original: float,
    recommended: float,
    delta: float,
    family_count: int,
    recommendation: str,
) -> dict[str, object]:
    return {
        "element_id": element_id,
        "slot": slot,
        "value": value,
        "original_base_score": original,
        "dry_run_base_score": recommended,
        "delta": delta,
        "family_count": family_count,
        "families": ["city-polished", "clean-minimal"][:family_count],
        "recommendation": recommendation,
        "direction": "increase",
        "recommended_base_score": recommended if recommendation == "apply" else original,
    }


def _write_elements(path: Path, shared_strong_score: float = 0.8) -> None:
    _write_json(
        path,
        {
            "schema_version": "mvp-v1",
            "elements": [
                _element("shared-strong", "waistline", "natural waist", shared_strong_score),
                _element("shared-medium", "neckline", "square neckline", 0.73),
                _element("held-solo", "detail", "neck scarf", 0.72),
            ],
        },
    )


def _element(element_id: str, slot: str, value: str, score: float) -> dict[str, object]:
    return {
        "element_id": element_id,
        "category": "dress",
        "slot": slot,
        "value": value,
        "tags": ["dress"],
        "base_score": score,
        "price_bands": ["mid"],
        "occasion_tags": ["casual"],
        "season_tags": ["spring"],
        "risk_flags": [],
        "evidence_summary": f"Fixture evidence summary for {value}.",
        "status": "active",
    }


def _element_score(payload: dict[str, object], element_id: str) -> float:
    elements = payload["elements"]
    for element in elements:
        if element["element_id"] == element_id:
            return float(element["base_score"])
    raise AssertionError(f"missing element {element_id}")


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
