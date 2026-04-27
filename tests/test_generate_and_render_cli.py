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


_REQUEST_FIXTURE_PATH = Path("tests/fixtures/requests/dress-generation-mvp/success-summer-vacation-mode-a.json")


class GenerateAndRenderCliTest(unittest.TestCase):
    def test_cli_prints_render_report_and_writes_outputs_with_fake_provider(self) -> None:
        from temu_y2_women.generate_and_render_cli import main

        stdout = io.StringIO()
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "render-output"
            with patch("sys.stdout", stdout):
                exit_code = main(
                    [
                        "--input",
                        str(_REQUEST_FIXTURE_PATH),
                        "--output-dir",
                        str(output_dir),
                        "--provider",
                        "fake",
                    ]
                )

            payload = json.loads(stdout.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["provider"], "fake")
            concept_result = _read_json(output_dir / "concept_result.json")
            self.assertEqual(concept_result["factory_spec"]["schema_version"], "factory-spec-v1")
            self.assertTrue((output_dir / "concept_result.json").exists())
            self.assertTrue((output_dir / "rendered_image.png").exists())

    def test_cli_returns_provider_config_error_after_persisting_concept_result(self) -> None:
        from temu_y2_women.generate_and_render_cli import main

        stdout = io.StringIO()
        with TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True):
            output_dir = Path(temp_dir) / "render-output"
            with patch("sys.stdout", stdout):
                exit_code = main(
                    [
                        "--input",
                        str(_REQUEST_FIXTURE_PATH),
                        "--output-dir",
                        str(output_dir),
                        "--provider",
                        "openai",
                    ]
                )

            payload = json.loads(stdout.getvalue())
            self.assertEqual(exit_code, 1)
            self.assertEqual(payload["error"]["code"], "INVALID_IMAGE_PROVIDER_CONFIG")
            self.assertTrue((output_dir / "concept_result.json").exists())
            self.assertFalse((output_dir / "rendered_image.png").exists())
            self.assertFalse((output_dir / "image_render_report.json").exists())

    def test_cli_module_entrypoint_runs_outside_repo_root_with_fake_provider(self) -> None:
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "render-output"
            env = dict(os.environ)
            repo_root = Path.cwd()
            env["PYTHONPATH"] = str(repo_root)
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "temu_y2_women.generate_and_render_cli",
                    "--input",
                    str((repo_root / _REQUEST_FIXTURE_PATH).resolve()),
                    "--output-dir",
                    str(output_dir),
                    "--provider",
                    "fake",
                ],
                capture_output=True,
                cwd=temp_dir,
                env=env,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0)
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["provider"], "fake")
            concept_result = _read_json(output_dir / "concept_result.json")
            self.assertEqual(concept_result["factory_spec"]["schema_version"], "factory-spec-v1")


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))
