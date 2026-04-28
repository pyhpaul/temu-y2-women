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
            self.assertTrue((output_dir / "hero_front.png").exists())
            self.assertTrue((output_dir / "hero_three_quarter.png").exists())
            self.assertTrue((output_dir / "hero_back.png").exists())
            self.assertTrue((output_dir / "construction_closeup.png").exists())
            self.assertTrue((output_dir / "fabric_print_closeup.png").exists())
            self.assertTrue((output_dir / "hem_and_drape_closeup.png").exists())
            self.assertEqual(len(payload["images"]), 6)

    def test_cli_reads_openai_config_from_codex_home(self) -> None:
        from temu_y2_women.generate_and_render_cli import main

        stdout = io.StringIO()
        captured: list[object] = []
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "render-output"
            codex_home = Path(temp_dir) / ".codex"
            codex_home.mkdir()
            _write_auth_json(codex_home / "auth.json", "file-key")
            _write_config_toml(codex_home / "config.toml", "https://file.test")
            with patch.dict(os.environ, {"CODEX_HOME": str(codex_home)}, clear=True):
                with patch(
                    "temu_y2_women.generate_and_render_cli.build_openai_image_provider",
                    side_effect=_capture_provider_factory(captured),
                ):
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
        config = captured[0]
        self.assertEqual(exit_code, 0)
        self.assertEqual(config.api_key, "file-key")
        self.assertEqual(config.base_url, "https://file.test")
        self.assertEqual(payload["provider"], "openai")
        self.assertEqual(payload["base_url"], "https://file.test")
        self.assertNotIn("file-key", stdout.getvalue())

    def test_cli_explicit_openai_values_override_local_config(self) -> None:
        from temu_y2_women.generate_and_render_cli import main

        stdout = io.StringIO()
        captured: list[object] = []
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "render-output"
            codex_home = Path(temp_dir) / ".codex"
            codex_home.mkdir()
            _write_auth_json(codex_home / "auth.json", "file-key")
            _write_config_toml(codex_home / "config.toml", "https://file.test")
            with patch.dict(os.environ, {"CODEX_HOME": str(codex_home)}, clear=True):
                with patch(
                    "temu_y2_women.generate_and_render_cli.build_openai_image_provider",
                    side_effect=_capture_provider_factory(captured),
                ):
                    with patch("sys.stdout", stdout):
                        exit_code = main(
                            [
                                "--input",
                                str(_REQUEST_FIXTURE_PATH),
                                "--output-dir",
                                str(output_dir),
                                "--provider",
                                "openai",
                                "--api-key",
                                "cli-key",
                                "--base-url",
                                "https://cli.test",
                                "--model",
                                "gpt-image-2",
                            ]
                        )

        payload = json.loads(stdout.getvalue())
        config = captured[0]
        self.assertEqual(exit_code, 0)
        self.assertEqual(config.api_key, "cli-key")
        self.assertEqual(config.base_url, "https://cli.test")
        self.assertEqual(config.model, "gpt-image-2")
        self.assertEqual(payload["base_url"], "https://cli.test")
        self.assertNotIn("cli-key", stdout.getvalue())

    def test_cli_returns_provider_config_error_after_persisting_concept_result(self) -> None:
        from temu_y2_women.generate_and_render_cli import main

        stdout = io.StringIO()
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "render-output"
            codex_home = Path(temp_dir) / ".codex"
            codex_home.mkdir()
            with patch.dict(os.environ, {"CODEX_HOME": str(codex_home)}, clear=True):
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
            self.assertFalse((output_dir / "hero_front.png").exists())
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


def _capture_provider_factory(captured: list[object]) -> object:
    def build_provider(config: object) -> object:
        captured.append(config)
        return _OpenAICompatibleFakeProvider(getattr(config, "model"), getattr(config, "base_url"))

    return build_provider


class _OpenAICompatibleFakeProvider:
    def __init__(self, model: str, base_url: str | None) -> None:
        self._model = model
        self._base_url = base_url

    def render(self, render_input: object) -> object:
        from temu_y2_women.image_generation_output import ImageProviderResult

        return ImageProviderResult(
            image_bytes=b"openai-compatible-output",
            mime_type="image/png",
            provider_name="openai",
            model=self._model,
            base_url=self._base_url,
        )


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_auth_json(path: Path, api_key: str) -> None:
    path.write_text(json.dumps({"OPENAI_API_KEY": api_key}), encoding="utf-8")


def _write_config_toml(path: Path, base_url: str) -> None:
    path.write_text(f'base_url = "{base_url}"\n', encoding="utf-8")
