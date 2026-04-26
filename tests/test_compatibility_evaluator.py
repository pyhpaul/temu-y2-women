from __future__ import annotations

import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


class CompatibilityRulesTest(unittest.TestCase):
    def test_loads_valid_compatibility_rules(self) -> None:
        from temu_y2_women.compatibility_evaluator import load_compatibility_rules

        rules = load_compatibility_rules()

        self.assertGreaterEqual(len(rules), 1)
        self.assertEqual(rules[0].severity, "weak")
        self.assertEqual(rules[0].penalty, 0.08)
        self.assertEqual(rules[0].reason, "floral print is paired with smocked bodice in the MVP rule set")
        self.assertEqual(rules[0].left_slot, "pattern")
        self.assertEqual(rules[0].left_value, "floral print")
        self.assertEqual(rules[0].right_slot, "detail")
        self.assertEqual(rules[0].right_value, "smocked bodice")

    def test_loads_canonicalized_compatibility_rules(self) -> None:
        from temu_y2_women.compatibility_evaluator import load_compatibility_rules

        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "compatibility_rules.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": "mvp-v1",
                        "rules": [
                            {
                                "left_slot": " Pattern ",
                                "left_value": " Floral Print ",
                                "right_slot": " DETAIL ",
                                "right_value": " Smocked Bodice ",
                                "severity": "weak",
                                "penalty": 0.08,
                                "reason": "floral print is paired with smocked bodice in the MVP rule set",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            rules = load_compatibility_rules(path)

        self.assertEqual(rules[0].left_slot, "pattern")
        self.assertEqual(rules[0].left_value, "floral print")
        self.assertEqual(rules[0].right_slot, "detail")
        self.assertEqual(rules[0].right_value, "smocked bodice")

    def test_rejects_unknown_detail_value(self) -> None:
        from temu_y2_women.compatibility_evaluator import load_compatibility_rules
        from temu_y2_women.errors import GenerationError

        with self.assertRaises(GenerationError) as error_context:
            load_compatibility_rules(
                Path("tests/fixtures/evidence/dress/invalid-compatibility-rules-unknown-value.json")
            )

        self.assertEqual(error_context.exception.code, "INVALID_EVIDENCE_STORE")
        self.assertEqual(error_context.exception.details["field"], "right_value")

    def test_rejects_non_dict_rule_record(self) -> None:
        from temu_y2_women.compatibility_evaluator import load_compatibility_rules
        from temu_y2_women.errors import GenerationError

        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "compatibility_rules.json"
            path.write_text(
                json.dumps({"schema_version": "mvp-v1", "rules": [None]}),
                encoding="utf-8",
            )

            with self.assertRaises(GenerationError) as error_context:
                load_compatibility_rules(path)

        self.assertEqual(error_context.exception.code, "INVALID_EVIDENCE_STORE")
        self.assertEqual(error_context.exception.details["index"], 0)
        self.assertIn("must be an object", error_context.exception.message)

    def test_rejects_malformed_json(self) -> None:
        from temu_y2_women.compatibility_evaluator import load_compatibility_rules
        from temu_y2_women.errors import GenerationError

        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "compatibility_rules.json"
            path.write_text("{", encoding="utf-8")

            with self.assertRaises(GenerationError) as error_context:
                load_compatibility_rules(path)

        self.assertEqual(error_context.exception.code, "INVALID_EVIDENCE_STORE")
        self.assertIn("invalid JSON", error_context.exception.message)

    def test_rejects_legacy_top_level_field_name(self) -> None:
        from temu_y2_women.compatibility_evaluator import load_compatibility_rules
        from temu_y2_women.errors import GenerationError

        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "compatibility_rules.json"
            path.write_text(
                json.dumps({"schema_version": "mvp-v1", "compatibility_rules": []}),
                encoding="utf-8",
            )

            with self.assertRaises(GenerationError) as error_context:
                load_compatibility_rules(path)

        self.assertEqual(error_context.exception.code, "INVALID_EVIDENCE_STORE")
        self.assertEqual(
            error_context.exception.message,
            "compatibility rule store must contain a 'rules' array",
        )

    def test_rejects_invalid_penalty(self) -> None:
        from temu_y2_women.compatibility_evaluator import load_compatibility_rules
        from temu_y2_women.errors import GenerationError

        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "compatibility_rules.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": "mvp-v1",
                        "rules": [
                            {
                                "left_slot": "pattern",
                                "left_value": "floral print",
                                "right_slot": "detail",
                                "right_value": "smocked bodice",
                                "severity": "weak",
                                "penalty": "bad",
                                "reason": "floral print is paired with smocked bodice in the MVP rule set",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(GenerationError) as error_context:
                load_compatibility_rules(path)

        self.assertEqual(error_context.exception.code, "INVALID_EVIDENCE_STORE")

    def test_rejects_non_string_severity_and_reason(self) -> None:
        from temu_y2_women.compatibility_evaluator import load_compatibility_rules
        from temu_y2_women.errors import GenerationError

        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "compatibility_rules.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": "mvp-v1",
                        "rules": [
                            {
                                "left_slot": "pattern",
                                "left_value": "floral print",
                                "right_slot": "detail",
                                "right_value": "smocked bodice",
                                "severity": 1,
                                "penalty": 0.08,
                                "reason": ["floral print is paired with smocked bodice in the MVP rule set"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(GenerationError) as error_context:
                load_compatibility_rules(path)

        self.assertEqual(error_context.exception.code, "INVALID_EVIDENCE_STORE")

    def test_rejects_string_penalty(self) -> None:
        from temu_y2_women.compatibility_evaluator import load_compatibility_rules
        from temu_y2_women.errors import GenerationError

        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "compatibility_rules.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": "mvp-v1",
                        "rules": [
                            {
                                "left_slot": "pattern",
                                "left_value": "floral print",
                                "right_slot": "detail",
                                "right_value": "smocked bodice",
                                "severity": "weak",
                                "penalty": "0.08",
                                "reason": "floral print is paired with smocked bodice in the MVP rule set",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(GenerationError) as error_context:
                load_compatibility_rules(path)

        self.assertEqual(error_context.exception.code, "INVALID_EVIDENCE_STORE")

    def test_rejects_boolean_penalty(self) -> None:
        from temu_y2_women.compatibility_evaluator import load_compatibility_rules
        from temu_y2_women.errors import GenerationError

        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "compatibility_rules.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": "mvp-v1",
                        "rules": [
                            {
                                "left_slot": "pattern",
                                "left_value": "floral print",
                                "right_slot": "detail",
                                "right_value": "smocked bodice",
                                "severity": "weak",
                                "penalty": True,
                                "reason": "floral print is paired with smocked bodice in the MVP rule set",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(GenerationError) as error_context:
                load_compatibility_rules(path)

        self.assertEqual(error_context.exception.code, "INVALID_EVIDENCE_STORE")

    def test_rejects_non_finite_penalty(self) -> None:
        from temu_y2_women.compatibility_evaluator import load_compatibility_rules
        from temu_y2_women.errors import GenerationError

        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "compatibility_rules.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": "mvp-v1",
                        "rules": [
                            {
                                "left_slot": "pattern",
                                "left_value": "floral print",
                                "right_slot": "detail",
                                "right_value": "smocked bodice",
                                "severity": "weak",
                                "penalty": math.nan,
                                "reason": "floral print is paired with smocked bodice in the MVP rule set",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(GenerationError) as error_context:
                load_compatibility_rules(path)

        self.assertEqual(error_context.exception.code, "INVALID_EVIDENCE_STORE")


if __name__ == "__main__":
    unittest.main()
