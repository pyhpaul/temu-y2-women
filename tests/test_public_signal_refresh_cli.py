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
            source_ids=None,
            cache_root=None,
        )
        self.assertEqual(payload["schema_version"], "public-refresh-report-v1")
        self.assertEqual(payload["source_summary"]["succeeded"], 3)

    def test_cli_forwards_cache_root(self) -> None:
        from temu_y2_women.public_signal_refresh_cli import main

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            cache_root = temp_root / "fetch-cache"
            stdout = StringIO()
            runner = _runner_patch(_success_report())
            with patch(
                "temu_y2_women.public_signal_refresh_cli.run_public_signal_refresh",
                runner,
            ), patch("sys.stdout", stdout):
                exit_code = main(
                    [
                        "run",
                        "--fetched-at",
                        "2026-04-28T00:00:00Z",
                        "--cache-root",
                        str(cache_root),
                    ]
                )

        self.assertEqual(exit_code, 0)
        runner.assert_called_once_with(
            registry_path=Path("data/refresh/dress/source_registry.json"),
            output_root=Path("data/refresh/dress"),
            fetched_at="2026-04-28T00:00:00Z",
            source_ids=None,
            cache_root=cache_root,
        )

    def test_cli_forwards_repeated_source_ids(self) -> None:
        from temu_y2_women.public_signal_refresh_cli import main

        stdout = StringIO()
        runner = _runner_patch(_success_report(selected_source_ids=["marieclaire-summer-2025-dress-trends"]))
        with patch(
            "temu_y2_women.public_signal_refresh_cli.run_public_signal_refresh",
            runner,
        ), patch("sys.stdout", stdout):
            exit_code = main(
                [
                    "run",
                    "--fetched-at",
                    "2026-04-28T00:00:00Z",
                    "--source-id",
                    "marieclaire-summer-2025-dress-trends",
                    "--source-id",
                    "whowhatwear-summer-dress-trends-2025",
                ]
            )

        self.assertEqual(exit_code, 0)
        runner.assert_called_once_with(
            registry_path=Path("data/refresh/dress/source_registry.json"),
            output_root=Path("data/refresh/dress"),
            fetched_at="2026-04-28T00:00:00Z",
            source_ids=[
                "marieclaire-summer-2025-dress-trends",
                "whowhatwear-summer-dress-trends-2025",
            ],
            cache_root=None,
        )

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

    def test_cli_returns_nonzero_for_unknown_source_id(self) -> None:
        from temu_y2_women.public_signal_refresh_cli import main

        registry_payload = {
            "schema_version": "public-source-registry-v1",
            "sources": [
                {
                    "source_id": "whowhatwear-summer-2025-dress-trends",
                    "source_type": "public_editorial_web",
                    "source_url": "https://www.whowhatwear.com/fashion/summer/summer-2025-dress-trends",
                    "target_market": "US",
                    "category": "dress",
                    "fetch_mode": "html",
                    "adapter_id": "whowhatwear_editorial_v1",
                    "default_price_band": "mid",
                    "pipeline_mode": "editorial_text",
                    "priority": 100,
                    "weight": 1.0,
                    "enabled": True,
                }
            ],
        }

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            registry_path = temp_root / "registry.json"
            registry_path.write_text(json.dumps(registry_payload), encoding="utf-8")
            stdout = StringIO()
            with patch("sys.stdout", stdout):
                exit_code = main(
                    [
                        "run",
                        "--registry",
                        str(registry_path),
                        "--output-root",
                        str(temp_root),
                        "--fetched-at",
                        "2026-04-28T00:00:00Z",
                        "--source-id",
                        "unknown-source",
                    ]
                )

        self.assertEqual(exit_code, 1)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["error"]["code"], "INVALID_PUBLIC_SOURCE_SELECTION")

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


def _success_report(selected_source_ids: list[str] | None = None) -> dict[str, object]:
    source_ids = selected_source_ids or [
        "whowhatwear-summer-2025-dress-trends",
        "whowhatwear-summer-dress-trends-2025",
        "marieclaire-summer-2025-dress-trends",
    ]
    return {
        "schema_version": "public-refresh-report-v1",
        "run_id": "2026-04-28T00-00-00Z-3sources-abc123",
        "selected_source_ids": source_ids,
        "source_summary": {"total": 3, "succeeded": 3, "failed": 0},
        "canonical_signal_count": 9,
        "signal_bundle_count": 9,
        "fallback_price_band_count": 9,
        "warnings": [],
        "errors": [],
    }


def _runner_patch(return_value: dict[str, object]):
    from unittest.mock import Mock

    return Mock(return_value=return_value)
