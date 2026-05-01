from __future__ import annotations

import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


_FAMILIES = ("vacation-romantic", "clean-minimal", "city-polished", "party-fitted")
_CRITERIA = (
    "family_differentiation",
    "prompt_adherence",
    "garment_fidelity",
    "commercial_realism",
    "artifact_control",
)


class StyleFamilyVisualQualityTest(unittest.TestCase):
    def test_build_review_accepts_scored_cases_from_acceptance_report(self) -> None:
        from temu_y2_women.style_family_visual_quality import build_visual_quality_review

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            acceptance_path = root / "visual_acceptance.json"
            _write_acceptance_report(acceptance_path)

            report = build_visual_quality_review(
                acceptance_path=acceptance_path,
                decisions={family: "accepted" for family in _FAMILIES},
                scores=_quality_scores(),
                notes={"vacation-romantic": "Distinct resort romance direction."},
            )

        self.assertEqual(report["schema_version"], "style-family-visual-quality-review-v1")
        self.assertEqual(report["status"], "accepted")
        self.assertEqual(report["summary"]["total"], 4)
        self.assertEqual(report["summary"]["accepted"], 4)
        self.assertEqual(report["summary"]["needs_revision"], 0)
        self.assertEqual(report["summary"]["average_score"], 4.5)
        self.assertEqual(report["criteria"], list(_CRITERIA))
        self.assertEqual([case["style_family_id"] for case in report["cases"]], list(_FAMILIES))
        first_case = report["cases"][0]
        self.assertEqual(first_case["decision"], "accepted")
        self.assertEqual(first_case["scores"]["family_differentiation"], 5)
        self.assertEqual(first_case["average_score"], 4.4)
        self.assertEqual(first_case["revision_reasons"], [])
        self.assertEqual(first_case["note"], "Distinct resort romance direction.")
        self.assertEqual(first_case["acceptance_note"], "vacation-romantic acceptance note")
        self.assertEqual(first_case["selected_elements"]["silhouette"], "a-line")

    def test_build_review_requires_revision_when_any_case_needs_revision(self) -> None:
        from temu_y2_women.style_family_visual_quality import build_visual_quality_review

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            acceptance_path = root / "visual_acceptance.json"
            _write_acceptance_report(acceptance_path)
            decisions = {family: "accepted" for family in _FAMILIES}
            decisions["party-fitted"] = "needs_revision"

            report = build_visual_quality_review(
                acceptance_path=acceptance_path,
                decisions=decisions,
                scores=_quality_scores(),
                revision_reasons={"party-fitted": ["Hands need cleanup before lock."]},
            )

        self.assertEqual(report["status"], "needs_revision")
        self.assertEqual(report["summary"]["accepted"], 3)
        self.assertEqual(report["summary"]["needs_revision"], 1)
        self.assertEqual(report["cases"][-1]["revision_reasons"], ["Hands need cleanup before lock."])

    def test_build_review_rejects_missing_quality_score(self) -> None:
        from temu_y2_women.style_family_visual_quality import build_visual_quality_review

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            acceptance_path = root / "visual_acceptance.json"
            _write_acceptance_report(acceptance_path)
            scores = _quality_scores()
            del scores["party-fitted"]["artifact_control"]

            with self.assertRaisesRegex(ValueError, "Missing score for party-fitted:artifact_control"):
                build_visual_quality_review(
                    acceptance_path=acceptance_path,
                    decisions={family: "accepted" for family in _FAMILIES},
                    scores=scores,
                )

    def test_build_review_rejects_score_outside_one_to_five(self) -> None:
        from temu_y2_women.style_family_visual_quality import build_visual_quality_review

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            acceptance_path = root / "visual_acceptance.json"
            _write_acceptance_report(acceptance_path)
            scores = _quality_scores()
            scores["clean-minimal"]["prompt_adherence"] = 6

            with self.assertRaisesRegex(ValueError, "Score for clean-minimal:prompt_adherence must be 1-5"):
                build_visual_quality_review(
                    acceptance_path=acceptance_path,
                    decisions={family: "accepted" for family in _FAMILIES},
                    scores=scores,
                )

    def test_build_review_rejects_missing_decision(self) -> None:
        from temu_y2_women.style_family_visual_quality import build_visual_quality_review

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            acceptance_path = root / "visual_acceptance.json"
            _write_acceptance_report(acceptance_path)
            decisions = {family: "accepted" for family in _FAMILIES}
            del decisions["city-polished"]

            with self.assertRaisesRegex(ValueError, "Missing decision for city-polished"):
                build_visual_quality_review(
                    acceptance_path=acceptance_path,
                    decisions=decisions,
                    scores=_quality_scores(),
                )

    def test_build_review_rejects_incomplete_acceptance_report(self) -> None:
        from temu_y2_women.style_family_visual_quality import build_visual_quality_review

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            acceptance_path = root / "visual_acceptance.json"
            _write_acceptance_report(acceptance_path, status="incomplete")

            with self.assertRaisesRegex(ValueError, "Acceptance report status must be accepted"):
                build_visual_quality_review(
                    acceptance_path=acceptance_path,
                    decisions={family: "accepted" for family in _FAMILIES},
                    scores=_quality_scores(),
                )


class StyleFamilyVisualQualityCliTest(unittest.TestCase):
    def test_cli_writes_review_and_prints_payload(self) -> None:
        from temu_y2_women.style_family_visual_quality_cli import main

        stdout = io.StringIO()
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            acceptance_path = root / "visual_acceptance.json"
            output_path = root / "visual_quality_review.json"
            _write_acceptance_report(acceptance_path)

            with patch("sys.stdout", stdout):
                exit_code = main(_cli_args(acceptance_path, output_path))
            written = _read_json(output_path)

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "accepted")
        self.assertEqual(written, payload)
        self.assertEqual(written["summary"]["average_score"], 4.5)

    def test_cli_returns_validation_error_for_missing_score(self) -> None:
        from temu_y2_women.style_family_visual_quality_cli import main

        stderr = io.StringIO()
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            acceptance_path = root / "visual_acceptance.json"
            output_path = root / "visual_quality_review.json"
            _write_acceptance_report(acceptance_path)
            args = _cli_args(acceptance_path, output_path)
            score_index = args.index("party-fitted:artifact_control=4")
            del args[score_index - 1 : score_index + 1]

            with patch("sys.stderr", stderr):
                exit_code = main(args)

        self.assertEqual(exit_code, 2)
        self.assertIn("Missing score for party-fitted:artifact_control", stderr.getvalue())
        self.assertFalse(output_path.exists())


def _write_acceptance_report(path: Path, *, status: str = "accepted") -> None:
    cases = [_acceptance_case(family) for family in _FAMILIES]
    _write_json(
        path,
        {
            "schema_version": "style-family-visual-acceptance-v1",
            "accepted_at": "2026-05-01",
            "status": status,
            "summary": {"total": 4, "ready": 4, "missing": 0},
            "cases": cases,
        },
    )


def _acceptance_case(family: str) -> dict[str, object]:
    return {
        "style_family_id": family,
        "status": "ready",
        "image_path": f"renders/{family}/hero_front.png",
        "prompt_fingerprint": f"{family}-fp",
        "selected_elements": {
            "silhouette": "a-line" if family == "vacation-romantic" else "shift",
            "color_family": "white" if family == "vacation-romantic" else "blue",
        },
        "note": f"{family} acceptance note",
    }


def _quality_scores() -> dict[str, dict[str, int]]:
    return {
        "vacation-romantic": _score_values(5, 4, 4, 5, 4),
        "clean-minimal": _score_values(5, 5, 4, 4, 4),
        "city-polished": _score_values(5, 4, 5, 4, 4),
        "party-fitted": _score_values(5, 5, 5, 5, 4),
    }


def _score_values(*values: int) -> dict[str, int]:
    return dict(zip(_CRITERIA, values, strict=True))


def _cli_args(acceptance_path: Path, output_path: Path) -> list[str]:
    args = ["build", "--acceptance", str(acceptance_path), "--output", str(output_path)]
    for family in _FAMILIES:
        args.extend(["--decision", f"{family}=accepted"])
        for criterion, score in _quality_scores()[family].items():
            args.extend(["--score", f"{family}:{criterion}={score}"])
    args.extend(["--note", "vacation-romantic=Distinct resort romance direction."])
    return args


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))
