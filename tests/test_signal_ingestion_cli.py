from __future__ import annotations

import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


_SIGNAL_FIXTURE_DIR = Path("tests/fixtures/signals/dress")
_EXPECTED_REPORT_PATH = _SIGNAL_FIXTURE_DIR / "expected-ingestion-report.json"


class SignalIngestionCliTest(unittest.TestCase):
    def test_cli_prints_success_report_json(self) -> None:
        from temu_y2_women.signal_ingestion_cli import main

        stdout = io.StringIO()
        with TemporaryDirectory() as temp_dir:
            with patch("sys.stdout", stdout):
                exit_code = main(
                    [
                        "--input",
                        str(_SIGNAL_FIXTURE_DIR / "valid-signal-bundle.json"),
                        "--output-dir",
                        temp_dir,
                    ]
                )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        expected_report = json.loads(_EXPECTED_REPORT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(payload["summary"]["accepted_signal_count"], 2)
        self.assertEqual(
            payload["summary"]["draft_element_count"],
            expected_report["summary"]["draft_element_count"],
        )

    def test_cli_prints_failure_json(self) -> None:
        from temu_y2_women.signal_ingestion_cli import main

        stdout = io.StringIO()
        with TemporaryDirectory() as temp_dir:
            with patch("sys.stdout", stdout):
                exit_code = main(
                    [
                        "--input",
                        str(_SIGNAL_FIXTURE_DIR / "invalid-signal-bundle.json"),
                        "--output-dir",
                        temp_dir,
                    ]
                )

        self.assertEqual(exit_code, 1)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["error"]["code"], "INVALID_SIGNAL_INPUT")
