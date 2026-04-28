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


_PROMOTION_FIXTURE_DIR = Path("tests/fixtures/promotion/dress")


class EvidencePromotionCliTest(unittest.TestCase):
    def test_prepare_cli_prints_review_template_and_writes_output(self) -> None:
        from temu_y2_women.evidence_promotion_cli import main

        stdout = io.StringIO()
        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "review.json"
            with patch("sys.stdout", stdout):
                exit_code = main(
                    [
                        "prepare",
                        "--draft-elements",
                        str(_PROMOTION_FIXTURE_DIR / "create" / "draft_elements.json"),
                        "--draft-strategy-hints",
                        str(_PROMOTION_FIXTURE_DIR / "create" / "draft_strategy_hints.json"),
                        "--active-elements",
                        str(_PROMOTION_FIXTURE_DIR / "baseline" / "elements.json"),
                        "--active-strategies",
                        str(_PROMOTION_FIXTURE_DIR / "baseline" / "strategy_templates.json"),
                        "--output",
                        str(output_path),
                    ]
                )
            written_payload = _read_json(output_path)

        self.assertEqual(exit_code, 0)
        expected = _read_json(_PROMOTION_FIXTURE_DIR / "create" / "expected_review_template.json")
        self.assertEqual(json.loads(stdout.getvalue()), expected)
        self.assertEqual(written_payload, expected)

    def test_apply_cli_prints_report_and_writes_outputs(self) -> None:
        from temu_y2_women.evidence_promotion_cli import main

        stdout = io.StringIO()
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            elements_path, strategies_path = _seed_active_evidence(temp_root)
            report_path = temp_root / "promotion_report.json"
            with patch("sys.stdout", stdout):
                exit_code = main(
                    [
                        "apply",
                        "--reviewed",
                        str(_PROMOTION_FIXTURE_DIR / "create" / "reviewed_decisions.json"),
                        "--draft-elements",
                        str(_PROMOTION_FIXTURE_DIR / "create" / "draft_elements.json"),
                        "--draft-strategy-hints",
                        str(_PROMOTION_FIXTURE_DIR / "create" / "draft_strategy_hints.json"),
                        "--active-elements",
                        str(elements_path),
                        "--active-strategies",
                        str(strategies_path),
                        "--report-output",
                        str(report_path),
                    ]
                )

            self.assertEqual(exit_code, 0)
            expected = _read_json(_PROMOTION_FIXTURE_DIR / "create" / "expected_promotion_report.json")
            self.assertEqual(json.loads(stdout.getvalue()), expected)
            self.assertEqual(_read_json(report_path), expected)
            self.assertEqual(
                _read_json(elements_path),
                _read_json(_PROMOTION_FIXTURE_DIR / "create" / "expected_elements_after_apply.json"),
            )
            self.assertEqual(
                _read_json(strategies_path),
                _read_json(_PROMOTION_FIXTURE_DIR / "create" / "expected_strategy_templates_after_apply.json"),
            )

    def test_apply_cli_prints_failure_json(self) -> None:
        from temu_y2_women.evidence_promotion_cli import main

        stdout = io.StringIO()
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            elements_path, strategies_path = _seed_active_evidence(temp_root)
            report_path = temp_root / "promotion_report.json"
            invalid_review = _read_json(_PROMOTION_FIXTURE_DIR / "create" / "reviewed_decisions.json")
            invalid_review["strategy_hints"][0]["proposed_strategy_template"]["slot_preferences"]["detail"] = ["missing"]
            invalid_review_path = temp_root / "invalid_review.json"
            invalid_review_path.write_text(json.dumps(invalid_review), encoding="utf-8")

            with patch("sys.stdout", stdout):
                exit_code = main(
                    [
                        "apply",
                        "--reviewed",
                        str(invalid_review_path),
                        "--draft-elements",
                        str(_PROMOTION_FIXTURE_DIR / "create" / "draft_elements.json"),
                        "--draft-strategy-hints",
                        str(_PROMOTION_FIXTURE_DIR / "create" / "draft_strategy_hints.json"),
                        "--active-elements",
                        str(elements_path),
                        "--active-strategies",
                        str(strategies_path),
                        "--report-output",
                        str(report_path),
                    ]
                )

        self.assertEqual(exit_code, 1)
        self.assertEqual(json.loads(stdout.getvalue())["error"]["code"], "INVALID_PROMOTION_REVIEW")

    def test_prepare_cli_prints_failure_json_for_output_write_error(self) -> None:
        from temu_y2_women.evidence_promotion_cli import main

        stdout = io.StringIO()
        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "missing-dir" / "review.json"
            with patch("sys.stdout", stdout):
                exit_code = main(
                    [
                        "prepare",
                        "--draft-elements",
                        str(_PROMOTION_FIXTURE_DIR / "create" / "draft_elements.json"),
                        "--draft-strategy-hints",
                        str(_PROMOTION_FIXTURE_DIR / "create" / "draft_strategy_hints.json"),
                        "--active-elements",
                        str(_PROMOTION_FIXTURE_DIR / "baseline" / "elements.json"),
                        "--active-strategies",
                        str(_PROMOTION_FIXTURE_DIR / "baseline" / "strategy_templates.json"),
                        "--output",
                        str(output_path),
                    ]
                )

        self.assertEqual(exit_code, 1)
        self.assertEqual(json.loads(stdout.getvalue())["error"]["code"], "PROMOTION_WRITE_FAILED")

    def test_prepare_cli_prints_failure_json_for_malformed_active_elements(self) -> None:
        from temu_y2_women.evidence_promotion_cli import main

        stdout = io.StringIO()
        with TemporaryDirectory() as temp_dir:
            broken_elements_path = Path(temp_dir) / "broken-elements.json"
            broken_elements_path.write_text("{bad", encoding="utf-8")
            output_path = Path(temp_dir) / "review.json"
            with patch("sys.stdout", stdout):
                exit_code = main(
                    [
                        "prepare",
                        "--draft-elements",
                        str(_PROMOTION_FIXTURE_DIR / "create" / "draft_elements.json"),
                        "--draft-strategy-hints",
                        str(_PROMOTION_FIXTURE_DIR / "create" / "draft_strategy_hints.json"),
                        "--active-elements",
                        str(broken_elements_path),
                        "--active-strategies",
                        str(_PROMOTION_FIXTURE_DIR / "baseline" / "strategy_templates.json"),
                        "--output",
                        str(output_path),
                    ]
                )

        self.assertEqual(exit_code, 1)
        self.assertEqual(json.loads(stdout.getvalue())["error"]["code"], "INVALID_EVIDENCE_STORE")

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
                    "temu_y2_women.evidence_promotion_cli",
                    "prepare",
                    "--draft-elements",
                    str((repo_root / _PROMOTION_FIXTURE_DIR / "create" / "draft_elements.json").resolve()),
                    "--draft-strategy-hints",
                    str((repo_root / _PROMOTION_FIXTURE_DIR / "create" / "draft_strategy_hints.json").resolve()),
                    "--active-elements",
                    str((repo_root / _PROMOTION_FIXTURE_DIR / "baseline" / "elements.json").resolve()),
                    "--active-strategies",
                    str((repo_root / _PROMOTION_FIXTURE_DIR / "baseline" / "strategy_templates.json").resolve()),
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
        self.assertEqual(
            json.loads(completed.stdout),
            _read_json(_PROMOTION_FIXTURE_DIR / "create" / "expected_review_template.json"),
        )
        self.assertEqual(written_payload, _read_json(_PROMOTION_FIXTURE_DIR / "create" / "expected_review_template.json"))


class EvidencePromotionRunDirCliTest(unittest.TestCase):
    def test_prepare_cli_run_dir_defaults_output_to_promotion_review(self) -> None:
        from temu_y2_women.evidence_promotion_cli import main

        stdout = io.StringIO()
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            run_dir = _seed_refresh_run(temp_root, scenario="create")
            elements_path, strategies_path = _seed_active_evidence(temp_root)
            with patch("sys.stdout", stdout):
                exit_code = main(
                    [
                        "prepare",
                        "--run-dir",
                        str(run_dir),
                        "--active-elements",
                        str(elements_path),
                        "--active-strategies",
                        str(strategies_path),
                    ]
                )
            self.assertEqual(exit_code, 0)
            expected = _read_json(_PROMOTION_FIXTURE_DIR / "create" / "expected_review_template.json")
            self.assertEqual(json.loads(stdout.getvalue()), expected)
            self.assertEqual(_read_json(run_dir / "promotion_review.json"), expected)

    def test_apply_cli_run_dir_defaults_reviewed_and_report_paths(self) -> None:
        from temu_y2_women.evidence_promotion_cli import main

        stdout = io.StringIO()
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            run_dir = _seed_refresh_run(temp_root, scenario="create")
            elements_path, strategies_path = _seed_active_evidence(temp_root)
            review_payload = _read_json(_PROMOTION_FIXTURE_DIR / "create" / "reviewed_decisions.json")
            _write_json(run_dir / "promotion_review.json", review_payload)
            with patch("sys.stdout", stdout):
                exit_code = main(
                    [
                        "apply",
                        "--run-dir",
                        str(run_dir),
                        "--active-elements",
                        str(elements_path),
                        "--active-strategies",
                        str(strategies_path),
                    ]
                )
            self.assertEqual(exit_code, 0)
            expected = _read_json(_PROMOTION_FIXTURE_DIR / "create" / "expected_promotion_report.json")
            expected["source_artifacts"]["reviewed_decisions"] = "promotion_review.json"
            self.assertEqual(json.loads(stdout.getvalue()), expected)
            self.assertEqual(_read_json(run_dir / "promotion_report.json"), expected)
            self.assertEqual(
                _read_json(elements_path),
                _read_json(_PROMOTION_FIXTURE_DIR / "create" / "expected_elements_after_apply.json"),
            )
            self.assertEqual(
                _read_json(strategies_path),
                _read_json(_PROMOTION_FIXTURE_DIR / "create" / "expected_strategy_templates_after_apply.json"),
            )

    def test_prepare_cli_rejects_run_dir_and_staged_inputs_together(self) -> None:
        from temu_y2_women.evidence_promotion_cli import main

        stdout = io.StringIO()
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            run_dir = _seed_refresh_run(temp_root, scenario="create")
            elements_path, strategies_path = _seed_active_evidence(temp_root)
            with patch("sys.stdout", stdout):
                exit_code = main(
                    [
                        "prepare",
                        "--run-dir",
                        str(run_dir),
                        "--draft-elements",
                        str(run_dir / "draft_elements.json"),
                        "--draft-strategy-hints",
                        str(run_dir / "draft_strategy_hints.json"),
                        "--active-elements",
                        str(elements_path),
                        "--active-strategies",
                        str(strategies_path),
                    ]
                )

        self.assertEqual(exit_code, 1)
        self.assertEqual(json.loads(stdout.getvalue())["error"]["code"], "INVALID_REFRESH_RUN")

    def test_apply_cli_rejects_run_dir_and_staged_inputs_together(self) -> None:
        from temu_y2_women.evidence_promotion_cli import main

        stdout = io.StringIO()
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            run_dir = _seed_refresh_run(temp_root, scenario="create")
            elements_path, strategies_path = _seed_active_evidence(temp_root)
            with patch("sys.stdout", stdout):
                exit_code = main(
                    [
                        "apply",
                        "--run-dir",
                        str(run_dir),
                        "--draft-elements",
                        str(run_dir / "draft_elements.json"),
                        "--draft-strategy-hints",
                        str(run_dir / "draft_strategy_hints.json"),
                        "--active-elements",
                        str(elements_path),
                        "--active-strategies",
                        str(strategies_path),
                    ]
                )

        self.assertEqual(exit_code, 1)
        self.assertEqual(json.loads(stdout.getvalue())["error"]["code"], "INVALID_REFRESH_RUN")


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _seed_refresh_run(temp_root: Path, scenario: str) -> Path:
    run_dir = temp_root / "refresh-run"
    run_dir.mkdir()
    for filename in ("draft_elements.json", "draft_strategy_hints.json"):
        (run_dir / filename).write_text(
            (_PROMOTION_FIXTURE_DIR / scenario / filename).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    (run_dir / "ingestion_report.json").write_text(
        json.dumps({"schema_version": "signal-ingestion-v1"}),
        encoding="utf-8",
    )
    (run_dir / "refresh_report.json").write_text(
        json.dumps({"schema_version": "public-signal-refresh-v1"}),
        encoding="utf-8",
    )
    return run_dir


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _seed_active_evidence(temp_root: Path) -> tuple[Path, Path]:
    elements_path = temp_root / "elements.json"
    strategies_path = temp_root / "strategy_templates.json"
    elements_path.write_text(
        (_PROMOTION_FIXTURE_DIR / "baseline" / "elements.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    strategies_path.write_text(
        (_PROMOTION_FIXTURE_DIR / "baseline" / "strategy_templates.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return elements_path, strategies_path
