from __future__ import annotations

import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch


_REQUEST_FIXTURE_DIR = Path("tests/fixtures/requests/dress-generation-mvp")


class CliTest(unittest.TestCase):
    def test_cli_prints_success_json(self) -> None:
        from temu_y2_women.cli import main

        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            exit_code = main(
                [
                    "--input",
                    str(_REQUEST_FIXTURE_DIR / "success-summer-vacation-mode-a.json"),
                ]
            )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["prompt_bundle"]["mode"], "A")
        self.assertEqual(payload["factory_spec"]["schema_version"], "factory-spec-v1")

    def test_cli_prints_failure_json(self) -> None:
        from temu_y2_women.cli import main

        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            exit_code = main(
                [
                    "--input",
                    str(_REQUEST_FIXTURE_DIR / "failure-no-candidates-summer-vacation.json"),
                ]
            )

        self.assertEqual(exit_code, 1)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["error"]["code"], "NO_CANDIDATES")
