from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


class EvidenceRepositoryValidationTest(unittest.TestCase):
    def test_reject_missing_elements_wrapper(self) -> None:
        from temu_y2_women.errors import GenerationError
        from temu_y2_women.evidence_repository import load_elements

        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "elements.json"
            path.write_text(json.dumps({"schema_version": "mvp-v1"}), encoding="utf-8")

            with self.assertRaises(GenerationError) as error_context:
                load_elements(path)

        self.assertEqual(error_context.exception.code, "INVALID_EVIDENCE_STORE")

    def test_reject_missing_strategy_templates_wrapper(self) -> None:
        from temu_y2_women.errors import GenerationError
        from temu_y2_women.evidence_repository import load_strategy_templates

        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "strategy_templates.json"
            path.write_text(json.dumps({"schema_version": "mvp-v1"}), encoding="utf-8")

            with self.assertRaises(GenerationError) as error_context:
                load_strategy_templates(path)

        self.assertEqual(error_context.exception.code, "INVALID_EVIDENCE_STORE")
