from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
import unittest
from unittest.mock import patch


class ProductImageSignalCliTest(unittest.TestCase):
    def test_cli_runs_stage_and_prints_report(self) -> None:
        from temu_y2_women.product_image_signal_cli import main

        stdout = StringIO()
        with patch(
            "temu_y2_women.product_image_signal_cli.run_product_image_signal_ingestion",
            return_value={
                "schema_version": "product-image-run-report-v1",
                "run_id": "2026-04-29T00-00-00Z-1products-7529b1",
                "input_product_count": 1,
                "input_image_count": 2,
                "observed_product_count": 1,
                "signal_bundle_count": 1,
                "structured_candidate_count": 3,
                "draft_element_count": 3,
                "coverage": {"matched_signals": 1, "unmatched_signal_ids": []},
                "warnings": [],
                "errors": [],
            },
        ) as runner, patch("sys.stdout", stdout):
            exit_code = main(
                [
                    "run",
                    "--input",
                    "data/product_images/dress/manifest.json",
                    "--output-root",
                    "data/product_images/dress/runs",
                    "--observed-at",
                    "2026-04-29T00:00:00Z",
                ]
            )

        self.assertEqual(exit_code, 0)
        runner.assert_called_once_with(
            input_path=Path("data/product_images/dress/manifest.json"),
            output_root=Path("data/product_images/dress/runs"),
            observed_at="2026-04-29T00:00:00Z",
        )
        self.assertEqual(json.loads(stdout.getvalue())["schema_version"], "product-image-run-report-v1")

    def test_cli_returns_nonzero_when_runner_returns_error(self) -> None:
        from temu_y2_women.product_image_signal_cli import main

        stdout = StringIO()
        with patch(
            "temu_y2_women.product_image_signal_cli.run_product_image_signal_ingestion",
            return_value={"error": {"code": "INVALID_PRODUCT_IMAGE_INPUT", "message": "bad", "details": {}}},
        ), patch("sys.stdout", stdout):
            exit_code = main(
                [
                    "run",
                    "--input",
                    "data/product_images/dress/manifest.json",
                    "--output-root",
                    "data/product_images/dress/runs",
                    "--observed-at",
                    "2026-04-29T00:00:00Z",
                ]
            )

        self.assertEqual(exit_code, 1)
        self.assertEqual(json.loads(stdout.getvalue())["error"]["code"], "INVALID_PRODUCT_IMAGE_INPUT")
