from __future__ import annotations

import io
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


class ImageProviderConfigCliTest(unittest.TestCase):
    def test_diagnose_prints_sanitized_json_and_returns_zero_with_api_key(self) -> None:
        from temu_y2_women.image_provider_config_cli import main

        stdout = io.StringIO()
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
            with patch.dict(
                os.environ,
                {
                    "OPENAI_COMPAT_BASE_URL": "https://process.test/v1?token=process-secret",
                    "OPENAI_COMPAT_ANCHOR_API_KEY": "process-anchor-secret",
                },
                clear=True,
            ):
                with patch("sys.stdout", stdout):
                    exit_code = main(
                        [
                            "diagnose",
                            "--codex-home",
                            str(codex_home),
                            "--env-path",
                            str(dotenv_path),
                            "--model",
                            "gpt-image-2",
                        ]
                    )

        output = stdout.getvalue()
        payload = json.loads(output)
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["api_key"]["source"], "process_env:OPENAI_COMPAT_ANCHOR_API_KEY")
        self.assertEqual(payload["base_url"]["host"], "process.test")
        self.assertEqual(payload["base_url"]["path"], "/v1")
        self.assertNotIn("process-anchor-secret", output)
        self.assertNotIn("dotenv-anchor-secret", output)
        self.assertNotIn("process-secret", output)
        self.assertNotIn("dotenv-secret", output)

    def test_diagnose_returns_one_when_api_key_is_missing(self) -> None:
        from temu_y2_women.image_provider_config_cli import main

        stdout = io.StringIO()
        with TemporaryDirectory() as temp_dir:
            codex_home = Path(temp_dir) / ".codex"
            codex_home.mkdir()
            with patch.dict(os.environ, {}, clear=True):
                with patch("sys.stdout", stdout):
                    exit_code = main(
                        [
                            "diagnose",
                            "--codex-home",
                            str(codex_home),
                            "--env-path",
                            str(Path(temp_dir) / "missing.env"),
                        ]
                    )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertIsNone(payload["api_key"]["source"])
        self.assertFalse(payload["api_key"]["present"])


if __name__ == "__main__":
    unittest.main()
