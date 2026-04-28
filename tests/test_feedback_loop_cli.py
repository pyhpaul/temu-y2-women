from __future__ import annotations

import io
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


_FEEDBACK_FIXTURE_DIR = Path("tests/fixtures/feedback/dress")
_ACTIVE_ELEMENTS_PATH = Path("data/mvp/dress/elements.json")
_LEDGER_SEED_PATH = Path("data/feedback/dress/feedback_ledger.json")
_FIXED_RECORDED_AT = "2026-04-27T12:00:00Z"
_TARGET_ELEMENT_IDS = {
    "dress-detail-smocked-bodice-001",
    "dress-fabric-cotton-poplin-001",
    "dress-neckline-square-001",
    "dress-pattern-floral-001",
    "dress-silhouette-a-line-001",
    "dress-sleeve-flutter-001",
}


class FeedbackLoopCliTest(unittest.TestCase):
    def test_prepare_cli_prints_review_and_writes_output(self) -> None:
        from temu_y2_women.feedback_loop_cli import main

        stdout = io.StringIO()
        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "review.json"
            with patch("sys.stdout", stdout):
                exit_code = main(
                    [
                        "prepare",
                        "--result",
                        str(_FEEDBACK_FIXTURE_DIR / "result_success.json"),
                        "--output",
                        str(output_path),
                    ]
                )
            written_payload = _read_json(output_path)

        self.assertEqual(exit_code, 0)
        expected = _read_json(_FEEDBACK_FIXTURE_DIR / "expected_review_template.json")
        self.assertEqual(json.loads(stdout.getvalue()), expected)
        self.assertEqual(written_payload, expected)

    def test_apply_cli_prints_report_and_writes_outputs(self) -> None:
        from temu_y2_women.feedback_loop_cli import main

        stdout = io.StringIO()
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            elements_path, ledger_path = _seed_active_feedback_files(temp_root)
            elements_before = _read_json(elements_path)
            report_path = temp_root / "feedback_report.json"
            with patch("sys.stdout", stdout), patch(
                "temu_y2_women.feedback_loop._current_timestamp",
                return_value=_FIXED_RECORDED_AT,
            ):
                exit_code = main(
                    [
                        "apply",
                        "--reviewed",
                        str(_FEEDBACK_FIXTURE_DIR / "reviewed_keep.json"),
                        "--result",
                        str(_FEEDBACK_FIXTURE_DIR / "result_success.json"),
                        "--active-elements",
                        str(elements_path),
                        "--ledger",
                        str(ledger_path),
                        "--report-output",
                        str(report_path),
                    ]
                )

            self.assertEqual(exit_code, 0)
            expected = _read_json(_FEEDBACK_FIXTURE_DIR / "expected_keep_report.json")
            self.assertEqual(json.loads(stdout.getvalue()), expected)
            self.assertEqual(_read_json(report_path), expected)
            _assert_element_score_updates(self, before=elements_before, after=_read_json(elements_path), delta=0.02)
            self.assertEqual(
                _read_json(ledger_path),
                _read_json(_FEEDBACK_FIXTURE_DIR / "expected_ledger_after_keep.json"),
            )

    def test_apply_cli_prints_failure_json(self) -> None:
        from temu_y2_women.feedback_loop_cli import main

        stdout = io.StringIO()
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            elements_path, ledger_path = _seed_active_feedback_files(temp_root)
            report_path = temp_root / "feedback_report.json"
            invalid_review = _read_json(_FEEDBACK_FIXTURE_DIR / "reviewed_keep.json")
            invalid_review["feedback_target"]["selected_element_ids"] = ["tampered"]
            invalid_review_path = temp_root / "invalid_review.json"
            invalid_review_path.write_text(json.dumps(invalid_review), encoding="utf-8")
            elements_before = _read_json(elements_path)
            ledger_before = _read_json(ledger_path)

            with patch("sys.stdout", stdout):
                exit_code = main(
                    [
                        "apply",
                        "--reviewed",
                        str(invalid_review_path),
                        "--result",
                        str(_FEEDBACK_FIXTURE_DIR / "result_success.json"),
                        "--active-elements",
                        str(elements_path),
                        "--ledger",
                        str(ledger_path),
                        "--report-output",
                        str(report_path),
                    ]
                )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(exit_code, 1)
            self.assertEqual(payload["error"]["code"], "INVALID_FEEDBACK_REVIEW")
            self.assertIn("field", payload["error"]["details"])
            self.assertFalse(report_path.exists())
            self.assertEqual(_read_json(elements_path), elements_before)
            self.assertEqual(_read_json(ledger_path), ledger_before)

    def test_prepare_cli_prints_failure_json_for_output_write_error(self) -> None:
        from temu_y2_women.feedback_loop_cli import main

        stdout = io.StringIO()
        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "missing-dir" / "review.json"
            with patch("sys.stdout", stdout):
                exit_code = main(
                    [
                        "prepare",
                        "--result",
                        str(_FEEDBACK_FIXTURE_DIR / "result_success.json"),
                        "--output",
                        str(output_path),
                    ]
                )

        self.assertEqual(exit_code, 1)
        self.assertEqual(json.loads(stdout.getvalue())["error"]["code"], "FEEDBACK_WRITE_FAILED")

    def test_prepare_cli_module_entrypoint_runs_outside_repo_root(self) -> None:
        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "review.json"
            env = dict(os.environ)
            repo_root = Path.cwd()
            env["PYTHONPATH"] = str(repo_root)
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "temu_y2_women.feedback_loop_cli",
                    "prepare",
                    "--result",
                    str((repo_root / _FEEDBACK_FIXTURE_DIR / "result_success.json").resolve()),
                    "--output",
                    str(output_path),
                ],
                capture_output=True,
                cwd=temp_dir,
                env=env,
                text=True,
                check=False,
            )
            if output_path.exists():
                written_payload = _read_json(output_path)
            else:
                written_payload = None

        self.assertEqual(completed.returncode, 0)
        expected = _read_json(_FEEDBACK_FIXTURE_DIR / "expected_review_template.json")
        self.assertEqual(json.loads(completed.stdout), expected)
        self.assertEqual(written_payload, expected)


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _seed_active_feedback_files(temp_root: Path) -> tuple[Path, Path]:
    elements_path = temp_root / "elements.json"
    ledger_path = temp_root / "feedback_ledger.json"
    elements_path.write_text(_ACTIVE_ELEMENTS_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    ledger_path.write_text(_LEDGER_SEED_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    return elements_path, ledger_path


def _assert_element_score_updates(
    test_case: unittest.TestCase,
    *,
    before: dict[str, object],
    after: dict[str, object],
    delta: float,
) -> None:
    before_elements = before["elements"]
    after_elements = after["elements"]
    test_case.assertEqual(len(after_elements), len(before_elements))

    before_by_id = {item["element_id"]: item for item in before_elements}
    after_by_id = {item["element_id"]: item for item in after_elements}
    test_case.assertEqual(set(after_by_id), set(before_by_id))

    for element_id, before_item in before_by_id.items():
        after_item = after_by_id[element_id]
        expected_score = before_item["base_score"] + (delta if element_id in _TARGET_ELEMENT_IDS else 0.0)
        test_case.assertAlmostEqual(after_item["base_score"], expected_score, places=7, msg=element_id)

        before_without_score = {key: value for key, value in before_item.items() if key != "base_score"}
        after_without_score = {key: value for key, value in after_item.items() if key != "base_score"}
        test_case.assertEqual(after_without_score, before_without_score, msg=element_id)
