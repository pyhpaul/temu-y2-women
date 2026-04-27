from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


class PublicSignalRefreshCliTest(unittest.TestCase):
    def test_cli_runs_refresh_and_prints_report(self) -> None:
        from temu_y2_women.public_signal_refresh_cli import main

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            stdout = StringIO()
            runner = _runner_patch(_success_report())
            with patch(
                "temu_y2_women.public_signal_refresh_cli.run_public_signal_refresh",
                runner,
            ), patch("sys.stdout", stdout):
                exit_code = main(
                    [
                        "run",
                        "--registry",
                        "data/refresh/dress/source_registry.json",
                        "--output-root",
                        str(temp_root),
                        "--fetched-at",
                        "2026-04-28T00:00:00Z",
                    ]
                )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        runner.assert_called_once_with(
            registry_path=Path("data/refresh/dress/source_registry.json"),
            output_root=temp_root,
            fetched_at="2026-04-28T00:00:00Z",
        )
        self.assertEqual(payload["schema_version"], "public-refresh-report-v1")
        self.assertEqual(payload["source_summary"]["succeeded"], 1)

    def test_cli_returns_nonzero_when_runner_returns_error(self) -> None:
        from temu_y2_women.public_signal_refresh_cli import main

        stdout = StringIO()
        with patch(
            "temu_y2_women.public_signal_refresh_cli.run_public_signal_refresh",
            return_value={"error": {"code": "INVALID_PUBLIC_SIGNAL_REFRESH", "message": "failed", "details": {}}},
        ), patch("sys.stdout", stdout):
            exit_code = main(
                [
                    "run",
                    "--registry",
                    "data/refresh/dress/source_registry.json",
                    "--output-root",
                    "data/refresh/dress",
                    "--fetched-at",
                    "2026-04-28T00:00:00Z",
                ]
            )

        self.assertEqual(exit_code, 1)
        self.assertEqual(json.loads(stdout.getvalue())["error"]["code"], "INVALID_PUBLIC_SIGNAL_REFRESH")

    def test_cli_requires_subcommand(self) -> None:
        from temu_y2_women.public_signal_refresh_cli import main

        stderr = StringIO()
        with patch("sys.stderr", stderr):
            with self.assertRaises(SystemExit) as error:
                main([])

        self.assertEqual(error.exception.code, 2)
        self.assertIn("usage:", stderr.getvalue())

    def test_cli_requires_fetched_at(self) -> None:
        from temu_y2_women.public_signal_refresh_cli import main

        stderr = StringIO()
        with patch("sys.stderr", stderr):
            with self.assertRaises(SystemExit) as error:
                main(["run"])

        self.assertEqual(error.exception.code, 2)
        self.assertIn("--fetched-at", stderr.getvalue())


def _success_report() -> dict[str, object]:
    return {
        "schema_version": "public-refresh-report-v1",
        "run_id": "2026-04-28T00-00-00Z-whowhatwear-summer-2025-dress-trends",
        "source_summary": {"total": 1, "succeeded": 1, "failed": 0},
        "canonical_signal_count": 5,
        "signal_bundle_count": 5,
        "fallback_price_band_count": 5,
        "warnings": [],
        "errors": [],
    }


def _runner_patch(return_value: dict[str, object]):
    from unittest.mock import Mock

    return Mock(return_value=return_value)
