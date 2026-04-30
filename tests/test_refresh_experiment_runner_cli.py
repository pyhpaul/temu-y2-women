from __future__ import annotations

import json
from io import StringIO
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import types
import unittest
from unittest.mock import Mock, patch


class RefreshExperimentRunnerCliTest(unittest.TestCase):
    def test_prepare_returns_zero_and_prints_json(self) -> None:
        stdout = StringIO()
        prepare = Mock(
            return_value={
                "experiment_id": "exp-cli-001",
                "manifest_path": "C:/tmp/experiment_manifest.json",
            }
        )

        with patch.dict(
            sys.modules,
            {"temu_y2_women.refresh_experiment_runner": _runner_module(prepare=prepare)},
        ), patch("sys.stdout", stdout):
            from temu_y2_women.refresh_experiment_runner_cli import main

            exit_code = main(
                [
                    "prepare",
                    "--run-dir",
                    "data/refresh/run-001",
                    "--request-set",
                    "data/refresh/request-set.json",
                    "--experiment-root",
                    "data/experiments",
                    "--workspace-name",
                    "batch-a",
                ]
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(stdout.getvalue())["experiment_id"], "exp-cli-001")
        prepare.assert_called_once_with(
            run_dir=Path("data/refresh/run-001"),
            request_set_path=Path("data/refresh/request-set.json"),
            experiment_root=Path("data/experiments"),
            workspace_name="batch-a",
        )

    def test_apply_returns_one_when_payload_contains_error(self) -> None:
        stdout = StringIO()
        apply = Mock(
            return_value={
                "error": {
                    "code": "REFRESH_EXPERIMENT_FAILED",
                    "message": "failed",
                    "details": {},
                }
            }
        )

        with patch.dict(
            sys.modules,
            {"temu_y2_women.refresh_experiment_runner": _runner_module(apply=apply)},
        ), patch("sys.stdout", stdout):
            from temu_y2_women.refresh_experiment_runner_cli import main

            exit_code = main(
                [
                    "apply",
                    "--manifest",
                    "data/experiments/batch-a/experiment_manifest.json",
                    "--reviewed",
                    "data/experiments/batch-a/reviewed.json",
                ]
            )

        self.assertEqual(exit_code, 1)
        self.assertEqual(json.loads(stdout.getvalue())["error"]["code"], "REFRESH_EXPERIMENT_FAILED")
        apply.assert_called_once_with(
            manifest_path=Path("data/experiments/batch-a/experiment_manifest.json"),
            reviewed_path=Path("data/experiments/batch-a/reviewed.json"),
            auto_accept_pending=False,
        )

    def test_apply_passes_auto_accept_flag(self) -> None:
        stdout = StringIO()
        apply = Mock(return_value={"experiment_report_path": "C:/tmp/report.json"})

        with patch.dict(
            sys.modules,
            {"temu_y2_women.refresh_experiment_runner": _runner_module(apply=apply)},
        ), patch("sys.stdout", stdout):
            from temu_y2_women.refresh_experiment_runner_cli import main

            exit_code = main(
                [
                    "apply",
                    "--manifest",
                    "data/experiments/batch-a/experiment_manifest.json",
                    "--auto-accept-pending",
                ]
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(stdout.getvalue())["experiment_report_path"], "C:/tmp/report.json")
        apply.assert_called_once_with(
            manifest_path=Path("data/experiments/batch-a/experiment_manifest.json"),
            reviewed_path=None,
            auto_accept_pending=True,
        )

    def test_module_entrypoint_prepare_succeeds(self) -> None:
        repo_root = Path.cwd()
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            sitecustomize_path = temp_root / "sitecustomize.py"
            sitecustomize_path.write_text(_sitecustomize_source(), encoding="utf-8")
            env = dict(os.environ)
            env["PYTHONPATH"] = os.pathsep.join([str(temp_root), str(repo_root)])

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "temu_y2_women.refresh_experiment_runner_cli",
                    "prepare",
                    "--run-dir",
                    "data/refresh/run-002",
                    "--request-set",
                    "data/refresh/request-set.json",
                    "--experiment-root",
                    "data/experiments",
                ],
                capture_output=True,
                cwd=temp_dir,
                env=env,
                text=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 0)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["experiment_id"], "exp-module-001")
        self.assertEqual(payload["workspace_root"], "data/experiments/exp-module-001")


def _runner_module(prepare: Mock | None = None, apply: Mock | None = None) -> types.ModuleType:
    module = types.ModuleType("temu_y2_women.refresh_experiment_runner")
    module.prepare_refresh_experiment = prepare or Mock()
    module.apply_refresh_experiment = apply or Mock()
    return module


def _sitecustomize_source() -> str:
    return """
import sys
import types

module = types.ModuleType("temu_y2_women.refresh_experiment_runner")

def prepare_refresh_experiment(run_dir, request_set_path, experiment_root, workspace_name=None):
    return {
        "experiment_id": "exp-module-001",
        "workspace_root": "data/experiments/exp-module-001",
        "run_dir": str(run_dir),
        "request_set_path": str(request_set_path),
        "experiment_root": str(experiment_root),
        "workspace_name": workspace_name,
    }

def apply_refresh_experiment(manifest_path, reviewed_path=None):
    return {"manifest_path": str(manifest_path), "reviewed_path": str(reviewed_path)}

module.prepare_refresh_experiment = prepare_refresh_experiment
module.apply_refresh_experiment = apply_refresh_experiment
sys.modules["temu_y2_women.refresh_experiment_runner"] = module
""".strip()
