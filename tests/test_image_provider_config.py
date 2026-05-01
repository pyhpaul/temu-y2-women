from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from temu_y2_women.errors import GenerationError


class ImageProviderConfigTest(unittest.TestCase):
    def test_diagnostics_show_process_env_overrides_dotenv_without_secrets(self) -> None:
        from temu_y2_women.image_provider_config import ProviderCliOptions, diagnose_openai_provider_config

        with TemporaryDirectory() as temp_dir:
            codex_home = Path(temp_dir) / ".codex"
            codex_home.mkdir()
            dotenv_path = Path(temp_dir) / ".env"
            dotenv_path.write_text(
                "\n".join(
                    [
                        "OPENAI_COMPAT_BASE_URL=https://dotenv.test/v1?token=dotenv-secret",
                        "OPENAI_COMPAT_ANCHOR_API_KEY=dotenv-anchor-secret",
                    ]
                ),
                encoding="utf-8",
            )

            diagnostics = diagnose_openai_provider_config(
                ProviderCliOptions(model="gpt-image-2"),
                codex_home=codex_home,
                environ={
                    "OPENAI_COMPAT_BASE_URL": "https://process.test/v1/images?token=process-secret",
                    "OPENAI_COMPAT_ANCHOR_API_KEY": "process-anchor-secret",
                },
                env_path=dotenv_path,
            )

        serialized = json.dumps(diagnostics, sort_keys=True)
        api_key_candidates = diagnostics["api_key"]["candidates"]
        dotenv_candidate = _candidate_by_source(api_key_candidates, "dotenv:OPENAI_COMPAT_ANCHOR_API_KEY")
        self.assertEqual(diagnostics["api_key"]["source"], "process_env:OPENAI_COMPAT_ANCHOR_API_KEY")
        self.assertEqual(diagnostics["api_key"]["length"], len("process-anchor-secret"))
        self.assertEqual(
            diagnostics["api_key"]["fingerprint_prefix"],
            _fingerprint_prefix("process-anchor-secret"),
        )
        self.assertEqual(dotenv_candidate["overridden_by"], "process_env:OPENAI_COMPAT_ANCHOR_API_KEY")
        self.assertEqual(diagnostics["base_url"]["source"], "process_env:OPENAI_COMPAT_BASE_URL")
        self.assertEqual(diagnostics["base_url"]["host"], "process.test")
        self.assertEqual(diagnostics["base_url"]["path"], "/v1/images")
        self.assertNotIn("process-anchor-secret", serialized)
        self.assertNotIn("dotenv-anchor-secret", serialized)
        self.assertNotIn("process-secret", serialized)
        self.assertNotIn("dotenv-secret", serialized)

    def test_diagnostics_report_missing_api_key_without_raising(self) -> None:
        from temu_y2_women.image_provider_config import ProviderCliOptions, diagnose_openai_provider_config

        with TemporaryDirectory() as temp_dir:
            codex_home = Path(temp_dir) / ".codex"
            codex_home.mkdir()

            diagnostics = diagnose_openai_provider_config(
                ProviderCliOptions(),
                codex_home=codex_home,
                environ={},
                env_path=Path(temp_dir) / "missing.env",
            )

        self.assertIsNone(diagnostics["api_key"]["source"])
        self.assertFalse(diagnostics["api_key"]["present"])
        self.assertEqual(diagnostics["model"]["value"], "gpt-image-2")

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
                env_path=Path(temp_dir) / "missing.env",
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
                env_path=Path(temp_dir) / "missing.env",
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
                env_path=Path(temp_dir) / "missing.env",
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
                env_path=Path(temp_dir) / "missing.env",
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
                env_path=Path(temp_dir) / "missing.env",
            )

        self.assertEqual(resolved.api_key, "env-key")

    def test_process_openai_api_key_overrides_dotenv_openai_api_key(self) -> None:
        from temu_y2_women.image_provider_config import ProviderCliOptions, resolve_openai_provider_config

        with TemporaryDirectory() as temp_dir:
            codex_home = Path(temp_dir) / ".codex"
            codex_home.mkdir()
            dotenv_path = Path(temp_dir) / ".env"
            dotenv_path.write_text("OPENAI_API_KEY=dotenv-openai-key\n", encoding="utf-8")

            resolved = resolve_openai_provider_config(
                ProviderCliOptions(),
                codex_home=codex_home,
                environ={"OPENAI_API_KEY": "process-openai-key"},
                env_path=dotenv_path,
            )

        self.assertEqual(resolved.api_key, "process-openai-key")

    def test_resolve_openai_provider_configs_reads_dual_keys_from_dotenv(self) -> None:
        from temu_y2_women.image_provider_config import ProviderCliOptions, resolve_openai_provider_configs

        with TemporaryDirectory() as temp_dir:
            codex_home = Path(temp_dir) / ".codex"
            codex_home.mkdir()
            dotenv_path = Path(temp_dir) / ".env"
            dotenv_path.write_text(
                "\n".join(
                    [
                        "OPENAI_COMPAT_BASE_URL=https://compat.test/v1",
                        "OPENAI_COMPAT_ANCHOR_API_KEY=anchor-key",
                        "OPENAI_COMPAT_EXPANSION_API_KEY=expansion-key",
                    ]
                ),
                encoding="utf-8",
            )

            resolved = resolve_openai_provider_configs(
                ProviderCliOptions(model="gpt-image-2"),
                codex_home=codex_home,
                environ={},
                env_path=dotenv_path,
            )

        self.assertEqual(resolved.default_config.api_key, "anchor-key")
        self.assertEqual(resolved.default_config.base_url, "https://compat.test/v1")
        self.assertIsNotNone(resolved.expansion_config)
        self.assertEqual(resolved.expansion_config.api_key, "expansion-key")

    def test_dotenv_compat_anchor_key_beats_ambient_openai_api_key(self) -> None:
        from temu_y2_women.image_provider_config import ProviderCliOptions, resolve_openai_provider_configs

        with TemporaryDirectory() as temp_dir:
            codex_home = Path(temp_dir) / ".codex"
            codex_home.mkdir()
            dotenv_path = Path(temp_dir) / ".env"
            dotenv_path.write_text(
                "\n".join(
                    [
                        "OPENAI_COMPAT_BASE_URL=https://compat.test/v1",
                        "OPENAI_COMPAT_ANCHOR_API_KEY=anchor-key",
                    ]
                ),
                encoding="utf-8",
            )

            resolved = resolve_openai_provider_configs(
                ProviderCliOptions(),
                codex_home=codex_home,
                environ={"OPENAI_API_KEY": "ambient-openai-key"},
                env_path=dotenv_path,
            )

        self.assertEqual(resolved.default_config.base_url, "https://compat.test/v1")
        self.assertEqual(resolved.default_config.api_key, "anchor-key")

    def test_cli_api_key_disables_expansion_route(self) -> None:
        from temu_y2_women.image_provider_config import ProviderCliOptions, resolve_openai_provider_configs

        with TemporaryDirectory() as temp_dir:
            codex_home = Path(temp_dir) / ".codex"
            codex_home.mkdir()
            dotenv_path = Path(temp_dir) / ".env"
            dotenv_path.write_text(
                "OPENAI_COMPAT_EXPANSION_API_KEY=expansion-key\n",
                encoding="utf-8",
            )

            resolved = resolve_openai_provider_configs(
                ProviderCliOptions(api_key="cli-key"),
                codex_home=codex_home,
                environ={},
                env_path=dotenv_path,
            )

        self.assertEqual(resolved.default_config.api_key, "cli-key")
        self.assertIsNone(resolved.expansion_config)

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
                env_path=Path(temp_dir) / "missing.env",
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
                    env_path=Path(temp_dir) / "missing.env",
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
                    env_path=Path(temp_dir) / "missing.env",
                )

        self.assertEqual(error_context.exception.code, "INVALID_IMAGE_PROVIDER_CONFIG")
        self.assertEqual(error_context.exception.details["field"], "auth.json")


def _write_auth_json(path: Path, api_key: str) -> None:
    path.write_text(json.dumps({"OPENAI_API_KEY": api_key}), encoding="utf-8")


def _write_config_toml(path: Path, base_url: str) -> None:
    path.write_text(f'base_url = "{base_url}"\n', encoding="utf-8")


def _candidate_by_source(candidates: object, source: str) -> dict[str, object]:
    for candidate in candidates:
        if candidate["source"] == source:
            return candidate
    raise AssertionError(f"missing candidate source: {source}")


def _fingerprint_prefix(api_key: str) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:12]
