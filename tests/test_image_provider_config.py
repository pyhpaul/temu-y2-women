from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from temu_y2_women.errors import GenerationError


class ImageProviderConfigTest(unittest.TestCase):
    def test_resolve_openai_provider_config_reads_auth_json_and_config_toml(self) -> None:
        from temu_y2_women.image_provider_config import ProviderCliOptions, resolve_openai_provider_config

        with TemporaryDirectory() as temp_dir:
            codex_home = Path(temp_dir) / ".codex"
            codex_home.mkdir()
            _write_auth_json(codex_home / "auth.json", "fixture-key")
            _write_config_toml(codex_home / "config.toml", "https://example.test")

            resolved = resolve_openai_provider_config(
                ProviderCliOptions(model="gpt-image-2"),
                codex_home=codex_home,
                environ={},
            )

        self.assertEqual(resolved.api_key, "fixture-key")
        self.assertEqual(resolved.base_url, "https://example.test")
        self.assertEqual(resolved.model, "gpt-image-2")

    def test_resolve_openai_provider_config_reads_selected_model_provider_base_url(self) -> None:
        from temu_y2_women.image_provider_config import ProviderCliOptions, resolve_openai_provider_config

        with TemporaryDirectory() as temp_dir:
            codex_home = Path(temp_dir) / ".codex"
            codex_home.mkdir()
            _write_auth_json(codex_home / "auth.json", "fixture-key")
            (codex_home / "config.toml").write_text(
                'model_provider = "codex"\n\n[model_providers.codex]\nbase_url = "https://provider.test"\n',
                encoding="utf-8",
            )

            resolved = resolve_openai_provider_config(
                ProviderCliOptions(),
                codex_home=codex_home,
                environ={},
            )

        self.assertEqual(resolved.base_url, "https://provider.test")

    def test_resolve_openai_provider_config_appends_v1_for_current_aerorelay_url(self) -> None:
        from temu_y2_women.image_provider_config import ProviderCliOptions, resolve_openai_provider_config

        with TemporaryDirectory() as temp_dir:
            codex_home = Path(temp_dir) / ".codex"
            codex_home.mkdir()
            _write_auth_json(codex_home / "auth.json", "fixture-key")
            (codex_home / "config.toml").write_text(
                'model_provider = "codex"\n\n[model_providers.codex]\nbase_url = "https://www.aerorelay.one"\n',
                encoding="utf-8",
            )

            resolved = resolve_openai_provider_config(
                ProviderCliOptions(),
                codex_home=codex_home,
                environ={},
            )

        self.assertEqual(resolved.base_url, "https://www.aerorelay.one/v1")

    def test_cli_values_override_environment_and_codex_files(self) -> None:
        from temu_y2_women.image_provider_config import ProviderCliOptions, resolve_openai_provider_config

        with TemporaryDirectory() as temp_dir:
            codex_home = Path(temp_dir) / ".codex"
            codex_home.mkdir()
            _write_auth_json(codex_home / "auth.json", "file-key")
            _write_config_toml(codex_home / "config.toml", "https://file.test")

            resolved = resolve_openai_provider_config(
                ProviderCliOptions(
                    api_key="cli-key",
                    base_url="https://cli.test",
                ),
                codex_home=codex_home,
                environ={"OPENAI_API_KEY": "env-key"},
            )

        self.assertEqual(resolved.api_key, "cli-key")
        self.assertEqual(resolved.base_url, "https://cli.test")

    def test_environment_api_key_overrides_auth_json(self) -> None:
        from temu_y2_women.image_provider_config import ProviderCliOptions, resolve_openai_provider_config

        with TemporaryDirectory() as temp_dir:
            codex_home = Path(temp_dir) / ".codex"
            codex_home.mkdir()
            _write_auth_json(codex_home / "auth.json", "file-key")

            resolved = resolve_openai_provider_config(
                ProviderCliOptions(),
                codex_home=codex_home,
                environ={"OPENAI_API_KEY": "env-key"},
            )

        self.assertEqual(resolved.api_key, "env-key")

    def test_resolve_openai_provider_config_allows_missing_base_url(self) -> None:
        from temu_y2_women.image_provider_config import ProviderCliOptions, resolve_openai_provider_config

        with TemporaryDirectory() as temp_dir:
            codex_home = Path(temp_dir) / ".codex"
            codex_home.mkdir()
            _write_auth_json(codex_home / "auth.json", "fixture-key")

            resolved = resolve_openai_provider_config(
                ProviderCliOptions(),
                codex_home=codex_home,
                environ={},
            )

        self.assertEqual(resolved.api_key, "fixture-key")
        self.assertIsNone(resolved.base_url)

    def test_resolve_openai_provider_config_rejects_missing_api_key(self) -> None:
        from temu_y2_women.image_provider_config import ProviderCliOptions, resolve_openai_provider_config

        with TemporaryDirectory() as temp_dir:
            codex_home = Path(temp_dir) / ".codex"
            codex_home.mkdir()

            with self.assertRaises(GenerationError) as error_context:
                resolve_openai_provider_config(
                    ProviderCliOptions(),
                    codex_home=codex_home,
                    environ={},
                )

        self.assertEqual(error_context.exception.code, "INVALID_IMAGE_PROVIDER_CONFIG")
        self.assertEqual(error_context.exception.details["field"], "api_key")
        self.assertIn("env:OPENAI_API_KEY", error_context.exception.details["sources_tried"])

    def test_resolve_openai_provider_config_rejects_invalid_auth_json(self) -> None:
        from temu_y2_women.image_provider_config import ProviderCliOptions, resolve_openai_provider_config

        with TemporaryDirectory() as temp_dir:
            codex_home = Path(temp_dir) / ".codex"
            codex_home.mkdir()
            (codex_home / "auth.json").write_text("{broken", encoding="utf-8")

            with self.assertRaises(GenerationError) as error_context:
                resolve_openai_provider_config(
                    ProviderCliOptions(),
                    codex_home=codex_home,
                    environ={},
                )

        self.assertEqual(error_context.exception.code, "INVALID_IMAGE_PROVIDER_CONFIG")
        self.assertEqual(error_context.exception.details["field"], "auth.json")


def _write_auth_json(path: Path, api_key: str) -> None:
    path.write_text(json.dumps({"OPENAI_API_KEY": api_key}), encoding="utf-8")


def _write_config_toml(path: Path, base_url: str) -> None:
    path.write_text(f'base_url = "{base_url}"\n', encoding="utf-8")
