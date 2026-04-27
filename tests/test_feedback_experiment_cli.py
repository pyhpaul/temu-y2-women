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


_REQUEST_FIXTURE_PATH = Path("tests/fixtures/requests/dress-generation-mvp/success-baseline-transitional-mode-a.json")


class FeedbackExperimentCliTest(unittest.TestCase):
    def test_prepare_cli_prints_manifest_summary_and_writes_workspace(self) -> None:
        from temu_y2_women.feedback_experiment_cli import main

        stdout = io.StringIO()
        with TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir) / "experiments"
            with patch("sys.stdout", stdout), patch(
                "temu_y2_women.feedback_experiment_runner._next_experiment_id",
                return_value="exp-cli-001",
            ), patch(
                "temu_y2_women.feedback_experiment_runner._current_timestamp",
                return_value="2026-04-27T16:00:00Z",
            ):
                exit_code = main(
                    [
                        "prepare",
                        "--request",
                        str(_REQUEST_FIXTURE_PATH),
                        "--experiment-root",
                        str(workspace_root),
                        "--workspace-name",
                        "cli-prepare",
                    ]
                )

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["experiment_id"], "exp-cli-001")
            self.assertTrue((workspace_root / "cli-prepare" / "experiment_manifest.json").exists())

    def test_apply_cli_prints_report_summary(self) -> None:
        from temu_y2_women.feedback_experiment_cli import main
        from temu_y2_women.feedback_experiment_runner import prepare_feedback_experiment

        stdout = io.StringIO()
        with TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir) / "experiments"
            with patch(
                "temu_y2_women.feedback_experiment_runner._next_experiment_id",
                return_value="exp-cli-002",
            ), patch(
                "temu_y2_women.feedback_experiment_runner._current_timestamp",
                return_value="2026-04-27T16:10:00Z",
            ):
                prepared = prepare_feedback_experiment(
                    request_path=_REQUEST_FIXTURE_PATH,
                    experiment_root=workspace_root,
                    workspace_name="cli-apply",
                )

            review_path = Path(prepared["feedback_review_path"])
            review_payload = json.loads(review_path.read_text(encoding="utf-8"))
            review_payload["decision"] = "keep"
            review_payload["notes"] = "cli apply"
            review_path.write_text(json.dumps(review_payload, ensure_ascii=False, indent=2), encoding="utf-8")

            with patch("sys.stdout", stdout), patch(
                "temu_y2_women.feedback_loop._current_timestamp",
                return_value="2026-04-27T16:11:00Z",
            ), patch(
                "temu_y2_women.feedback_experiment_runner._current_timestamp",
                return_value="2026-04-27T16:12:00Z",
            ):
                exit_code = main(
                    [
                        "apply",
                        "--reviewed",
                        str(review_path),
                        "--manifest",
                        str(prepared["manifest_path"]),
                    ]
                )

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertIn("experiment_report_path", payload)

    def test_prepare_cli_module_entrypoint_runs_outside_repo_root(self) -> None:
        with TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "experiments"
            env = dict(os.environ)
            repo_root = Path.cwd()
            env["PYTHONPATH"] = str(repo_root)
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "temu_y2_women.feedback_experiment_cli",
                    "prepare",
                    "--request",
                    str((repo_root / _REQUEST_FIXTURE_PATH).resolve()),
                    "--experiment-root",
                    str(output_root),
                    "--workspace-name",
                    "module-entrypoint",
                ],
                capture_output=True,
                cwd=temp_dir,
                env=env,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0)
            payload = json.loads(completed.stdout)
            self.assertTrue((output_root / "module-entrypoint" / "experiment_manifest.json").exists())
            self.assertIn("feedback_review_path", payload)
