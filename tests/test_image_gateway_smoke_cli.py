from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import io
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


class ImageGatewaySmokeCliTest(unittest.TestCase):
    def test_cli_reads_provider_config_and_prints_smoke_report(self) -> None:
        from temu_y2_women.image_gateway_smoke_cli import main

        stdout = io.StringIO()
        captured: list[object] = []
        with TemporaryDirectory() as temp_dir:
            codex_home = Path(temp_dir) / ".codex"
            codex_home.mkdir()
            _write_auth_json(codex_home / "auth.json", "anchor-key")
            _write_config_toml(codex_home / "config.toml", "https://compat.test/v1")
            with patch.dict(
                os.environ,
                {
                    "CODEX_HOME": str(codex_home),
                    "OPENAI_COMPAT_EXPANSION_API_KEY": "expansion-key",
                },
                clear=True,
            ):
                with _isolated_dotenv(temp_dir):
                    with patch(
                        "temu_y2_women.image_gateway_smoke_cli.run_gateway_smoke",
                        side_effect=_capture_smoke_runner(captured),
                    ):
                        with patch("sys.stdout", stdout):
                            exit_code = main(["run", "--timeout-sec", "12.5"])

        payload = json.loads(stdout.getvalue())
        settings = captured[0]
        self.assertEqual(exit_code, 0)
        self.assertEqual(settings.base_url, "https://compat.test/v1")
        self.assertEqual(settings.anchor_api_key, "anchor-key")
        self.assertEqual(settings.expansion_api_key, "expansion-key")
        self.assertEqual(settings.timeout_sec, 12.5)
        self.assertEqual(payload["summary"]["failed"], 0)
        self.assertNotIn("anchor-key", stdout.getvalue())

    def test_cli_explicit_values_override_local_config(self) -> None:
        from temu_y2_women.image_gateway_smoke_cli import main

        stdout = io.StringIO()
        captured: list[object] = []
        with TemporaryDirectory() as temp_dir:
            codex_home = Path(temp_dir) / ".codex"
            codex_home.mkdir()
            _write_auth_json(codex_home / "auth.json", "file-key")
            _write_config_toml(codex_home / "config.toml", "https://file.test/v1")
            with patch.dict(os.environ, {"CODEX_HOME": str(codex_home)}, clear=True):
                with _isolated_dotenv(temp_dir):
                    with patch(
                        "temu_y2_women.image_gateway_smoke_cli.run_gateway_smoke",
                        side_effect=_capture_smoke_runner(captured),
                    ):
                        with patch("sys.stdout", stdout):
                            exit_code = main(
                                [
                                    "run",
                                    "--base-url",
                                    "https://cli.test/v1",
                                    "--anchor-api-key",
                                    "cli-anchor",
                                    "--expansion-api-key",
                                    "cli-expansion",
                                    "--model",
                                    "gpt-image-2",
                                    "--check",
                                    "models",
                                ]
                            )

        payload = json.loads(stdout.getvalue())
        settings = captured[0]
        self.assertEqual(exit_code, 0)
        self.assertEqual(settings.base_url, "https://cli.test/v1")
        self.assertEqual(settings.anchor_api_key, "cli-anchor")
        self.assertEqual(settings.expansion_api_key, "cli-expansion")
        self.assertEqual(payload["requested_checks"], ["models"])

    def test_cli_uses_curl_http_client_for_callxyq_base_url(self) -> None:
        from temu_y2_women.image_gateway_smoke_cli import main
        from temu_y2_women.image_gateway_smoke_http import GatewaySmokeCurlHttpClient

        stdout = io.StringIO()
        captured: list[dict[str, object]] = []
        with TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"CODEX_HOME": str(Path(temp_dir) / ".codex")}, clear=True):
                with _isolated_dotenv(temp_dir):
                    with patch(
                        "temu_y2_women.image_gateway_smoke_cli.run_gateway_smoke",
                        side_effect=_capture_smoke_runner_with_client(captured),
                    ):
                        with patch("sys.stdout", stdout):
                            exit_code = main(
                                [
                                    "run",
                                    "--base-url",
                                    "https://callxyq.xyz/v1",
                                    "--anchor-api-key",
                                    "anchor-key",
                                    "--expansion-api-key",
                                    "expansion-key",
                                    "--check",
                                    "models",
                                ]
                            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertIsInstance(captured[0]["http_client"], GatewaySmokeCurlHttpClient)
        self.assertEqual(payload["requested_checks"], ["models"])

    def test_cli_returns_structured_provider_config_error(self) -> None:
        from temu_y2_women.image_gateway_smoke_cli import main

        stdout = io.StringIO()
        with TemporaryDirectory() as temp_dir:
            codex_home = Path(temp_dir) / ".codex"
            codex_home.mkdir()
            with patch.dict(os.environ, {"CODEX_HOME": str(codex_home)}, clear=True):
                with _isolated_dotenv(temp_dir):
                    with patch("sys.stdout", stdout):
                        exit_code = main(["run"])

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(payload["error"]["code"], "INVALID_IMAGE_PROVIDER_CONFIG")


def _capture_smoke_runner(captured: list[object]) -> object:
    def run_smoke(settings: object, *, check_ids: list[str] | None = None, http_client: object = None) -> dict[str, object]:
        captured.append(settings)
        return {
            "schema_version": "image-gateway-smoke-report-v1",
            "model": getattr(settings, "model"),
            "base_url": getattr(settings, "base_url"),
            "timeout_sec": getattr(settings, "timeout_sec"),
            "requested_checks": check_ids or [
                "models",
                "generate-anchor",
                "generate-expansion",
                "edit-anchor",
                "edit-expansion",
            ],
            "checks": [],
            "summary": {"total": 0, "passed": 0, "failed": 0},
        }

    return run_smoke


def _capture_smoke_runner_with_client(captured: list[dict[str, object]]) -> object:
    def run_smoke(settings: object, *, check_ids: list[str] | None = None, http_client: object = None) -> dict[str, object]:
        captured.append({"settings": settings, "http_client": http_client})
        return {
            "schema_version": "image-gateway-smoke-report-v1",
            "model": getattr(settings, "model"),
            "base_url": getattr(settings, "base_url"),
            "timeout_sec": getattr(settings, "timeout_sec"),
            "requested_checks": check_ids or [
                "models",
                "generate-anchor",
                "generate-expansion",
                "edit-anchor",
                "edit-expansion",
            ],
            "checks": [],
            "summary": {"total": 0, "passed": 0, "failed": 0},
        }

    return run_smoke


@contextmanager
def _isolated_dotenv(temp_dir: str) -> Iterator[None]:
    with patch(
        "temu_y2_women.image_provider_config._default_env_path",
        return_value=Path(temp_dir) / "missing.env",
    ):
        yield


def _write_auth_json(path: Path, api_key: str) -> None:
    path.write_text(json.dumps({"OPENAI_API_KEY": api_key}), encoding="utf-8")


def _write_config_toml(path: Path, base_url: str) -> None:
    path.write_text(f'base_url = "{base_url}"\n', encoding="utf-8")
