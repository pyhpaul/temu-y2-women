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


_RESULT_FIXTURE_PATH = Path("tests/fixtures/feedback/dress/result_success.json")


class ImageGenerationCliTest(unittest.TestCase):
    def test_cli_prints_report_and_writes_outputs_with_fake_provider(self) -> None:
        from temu_y2_women.image_generation_cli import main

        stdout = io.StringIO()
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "render-output"
            with patch("sys.stdout", stdout):
                exit_code = main(
                    [
                        "--result",
                        str(_RESULT_FIXTURE_PATH),
                        "--output-dir",
                        str(output_dir),
                        "--provider",
                        "fake",
                    ]
                )

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertTrue((output_dir / "rendered_image.png").exists())
            self.assertEqual(payload["provider"], "fake")

    def test_cli_returns_structured_provider_config_error_for_openai_without_api_key(self) -> None:
        from temu_y2_women.image_generation_cli import main

        stdout = io.StringIO()
        with TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True):
            output_dir = Path(temp_dir) / "render-output"
            with patch("sys.stdout", stdout):
                exit_code = main(
                    [
                        "--result",
                        str(_RESULT_FIXTURE_PATH),
                        "--output-dir",
                        str(output_dir),
                        "--provider",
                        "openai",
                    ]
                )

            self.assertEqual(exit_code, 1)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["error"]["code"], "INVALID_IMAGE_PROVIDER_CONFIG")
            self.assertFalse((output_dir / "rendered_image.png").exists())

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
                    "temu_y2_women.image_generation_cli",
                    "--result",
                    str((repo_root / _RESULT_FIXTURE_PATH).resolve()),
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
            self.assertIn("image_path", payload)
            self.assertTrue((output_dir / "image_render_report.json").exists())
