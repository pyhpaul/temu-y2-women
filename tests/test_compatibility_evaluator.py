from __future__ import annotations

import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from temu_y2_women.models import CandidateElement


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

    def test_loads_v2_compatibility_rules_with_evidence_metadata(self) -> None:
        from temu_y2_women.compatibility_evaluator import load_compatibility_rules

        rules = load_compatibility_rules(
            Path("tests/fixtures/evidence/dress/compatibility-rules-v2-valid.json")
        )

        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0].rule_id, "dress-pattern-floral-print__detail-smocked-bodice")
        self.assertEqual(rules[0].scope, {"category": "dress", "target_market": "US", "season_tags": ["summer"], "occasion_tags": ["vacation"], "price_bands": ["mid"]})
        self.assertEqual(rules[0].confidence, 0.74)
        self.assertEqual(rules[0].decision_source, "reviewed_heuristic")
        self.assertEqual(rules[0].status, "active")

    def test_v1_rule_shape_remains_supported(self) -> None:
        from temu_y2_women.compatibility_evaluator import load_compatibility_rules

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
                                "penalty": 0.08,
                                "reason": "fixture",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            rules = load_compatibility_rules(path)

        self.assertEqual(rules[0].rule_id, None)
        self.assertEqual(rules[0].scope, None)
        self.assertEqual(rules[0].confidence, None)
        self.assertEqual(rules[0].decision_source, None)
        self.assertEqual(rules[0].status, "active")

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

    def test_rejects_negative_penalty(self) -> None:
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
                                "penalty": -0.01,
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

    def test_rejects_non_zero_penalty_for_strong_rule(self) -> None:
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
                                "severity": "strong",
                                "penalty": 0.01,
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

    def test_rejects_invalid_severity_value(self) -> None:
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
                                "severity": "medium",
                                "penalty": 0.08,
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
        self.assertEqual(error_context.exception.details["field"], "severity")

    def test_rejects_v2_rule_with_invalid_scope_shape(self) -> None:
        from temu_y2_women.compatibility_evaluator import load_compatibility_rules
        from temu_y2_women.errors import GenerationError

        with self.assertRaises(GenerationError) as error_context:
            load_compatibility_rules(
                Path("tests/fixtures/evidence/dress/compatibility-rules-v2-invalid-scope.json")
            )

        self.assertEqual(error_context.exception.code, "INVALID_EVIDENCE_STORE")
        self.assertEqual(error_context.exception.details["field"], "scope.season_tags")

    def test_rejects_v2_rule_with_invalid_confidence(self) -> None:
        from temu_y2_women.compatibility_evaluator import load_compatibility_rules
        from temu_y2_women.errors import GenerationError

        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "compatibility_rules.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": "compatibility-rules-v2",
                        "rules": [
                            {
                                "rule_id": "dress-pattern-floral-print__detail-smocked-bodice",
                                "left_slot": "pattern",
                                "left_value": "floral print",
                                "right_slot": "detail",
                                "right_value": "smocked bodice",
                                "severity": "weak",
                                "penalty": 0.08,
                                "reason": "fixture",
                                "scope": {"category": "dress"},
                                "confidence": 1.2,
                                "status": "active",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(GenerationError) as error_context:
                load_compatibility_rules(path)

        self.assertEqual(error_context.exception.code, "INVALID_EVIDENCE_STORE")
        self.assertEqual(error_context.exception.details["field"], "confidence")


class CompatibilityEvaluationTest(unittest.TestCase):
    def test_returns_empty_evaluation_when_required_slots_missing(self) -> None:
        from temu_y2_women.compatibility_evaluator import CompatibilityRule, evaluate_selection_compatibility

        selected = {
            "detail": CandidateElement(
                element_id="detail-1",
                category="dress",
                slot="detail",
                value="smocked bodice",
                tags=(),
                base_score=0.0,
                effective_score=0.0,
                risk_flags=(),
                evidence_summary="",
            ),
        }
        rules = (
            CompatibilityRule("pattern", "floral print", "detail", "smocked bodice", "weak", 0.08, ""),
        )

        evaluation = evaluate_selection_compatibility(selected, rules)

        self.assertEqual(evaluation.hard_conflicts, ())
        self.assertEqual(evaluation.soft_conflicts, ())
        self.assertEqual(evaluation.compatibility_penalty, 0.0)
        self.assertEqual(evaluation.compatibility_notes, ())

    def test_applies_weak_conflict_penalty_and_note(self) -> None:
        from temu_y2_women.compatibility_evaluator import CompatibilityRule, evaluate_selection_compatibility

        selected = {
            "pattern": CandidateElement(
                element_id="pattern-1",
                category="dress",
                slot="pattern",
                value="floral print",
                tags=(),
                base_score=0.0,
                effective_score=0.0,
                risk_flags=(),
                evidence_summary="",
            ),
            "detail": CandidateElement(
                element_id="detail-1",
                category="dress",
                slot="detail",
                value="smocked bodice",
                tags=(),
                base_score=0.0,
                effective_score=0.0,
                risk_flags=(),
                evidence_summary="",
            ),
        }
        rules = (
            CompatibilityRule(
                left_slot="pattern",
                left_value="floral print",
                right_slot="detail",
                right_value="smocked bodice",
                severity="weak",
                penalty=0.08,
                reason="floral print is paired with smocked bodice in the MVP rule set",
            ),
        )

        evaluation = evaluate_selection_compatibility(selected, rules)

        self.assertEqual(evaluation.compatibility_penalty, 0.08)
        self.assertEqual(evaluation.hard_conflicts, ())
        self.assertEqual(
            evaluation.compatibility_notes,
            ("style compatibility penalty applied: floral print + smocked bodice (0.08)",),
        )

    def test_rounds_accumulated_penalty_to_four_decimals(self) -> None:
        from temu_y2_women.compatibility_evaluator import CompatibilityRule, evaluate_selection_compatibility

        selected = {
            "pattern": CandidateElement(
                element_id="pattern-1",
                category="dress",
                slot="pattern",
                value="floral print",
                tags=(),
                base_score=0.0,
                effective_score=0.0,
                risk_flags=(),
                evidence_summary="",
            ),
            "detail": CandidateElement(
                element_id="detail-1",
                category="dress",
                slot="detail",
                value="smocked bodice",
                tags=(),
                base_score=0.0,
                effective_score=0.0,
                risk_flags=(),
                evidence_summary="",
            ),
        }
        rules = (
            CompatibilityRule("pattern", "floral print", "detail", "smocked bodice", "weak", 0.33335, ""),
            CompatibilityRule("pattern", "floral print", "detail", "smocked bodice", "weak", 0.00006, ""),
        )

        evaluation = evaluate_selection_compatibility(selected, rules)

        self.assertEqual(evaluation.compatibility_penalty, 0.3334)
        self.assertEqual(
            evaluation.compatibility_notes,
            (
                "style compatibility penalty applied: floral print + smocked bodice (0.33)",
                "style compatibility penalty applied: floral print + smocked bodice (0.00)",
            ),
        )

    def test_marks_strong_conflict_as_hard_conflict(self) -> None:
        from temu_y2_women.compatibility_evaluator import CompatibilityRule, evaluate_selection_compatibility

        selected = {
            "pattern": CandidateElement(
                element_id="pattern-1",
                category="dress",
                slot="pattern",
                value="floral print",
                tags=(),
                base_score=0.0,
                effective_score=0.0,
                risk_flags=(),
                evidence_summary="",
            ),
            "detail": CandidateElement(
                element_id="detail-1",
                category="dress",
                slot="detail",
                value="smocked bodice",
                tags=(),
                base_score=0.0,
                effective_score=0.0,
                risk_flags=(),
                evidence_summary="",
            ),
        }
        rules = (
            CompatibilityRule(
                left_slot="pattern",
                left_value="floral print",
                right_slot="detail",
                right_value="smocked bodice",
                severity="strong",
                penalty=0.08,
                reason="floral print is paired with smocked bodice in the MVP rule set",
            ),
        )

        evaluation = evaluate_selection_compatibility(selected, rules)

        self.assertEqual(evaluation.hard_conflicts, ("floral print + smocked bodice",))
        self.assertEqual(evaluation.compatibility_penalty, 0.0)
        self.assertEqual(
            evaluation.compatibility_notes,
            ("style conflict avoided: floral print + smocked bodice",),
        )

    def test_ignores_rule_when_candidate_slots_do_not_match_rule_slots(self) -> None:
        from temu_y2_women.compatibility_evaluator import CompatibilityRule, evaluate_selection_compatibility

        selected = {
            "pattern": CandidateElement(
                element_id="pattern-1",
                category="dress",
                slot="detail",
                value="floral print",
                tags=(),
                base_score=0.0,
                effective_score=0.0,
                risk_flags=(),
                evidence_summary="",
            ),
            "detail": CandidateElement(
                element_id="detail-1",
                category="dress",
                slot="detail",
                value="smocked bodice",
                tags=(),
                base_score=0.0,
                effective_score=0.0,
                risk_flags=(),
                evidence_summary="",
            ),
        }
        rules = (
            CompatibilityRule("pattern", "floral print", "detail", "smocked bodice", "weak", 0.08, ""),
        )

        evaluation = evaluate_selection_compatibility(selected, rules)

        self.assertEqual(evaluation.soft_conflicts, ())
        self.assertEqual(evaluation.compatibility_penalty, 0.0)

    def test_v2_rule_metadata_does_not_change_runtime_scoring(self) -> None:
        from temu_y2_women.compatibility_evaluator import evaluate_selection_compatibility, load_compatibility_rules

        selected = {
            "pattern": CandidateElement(
                element_id="pattern-1",
                category="dress",
                slot="pattern",
                value="floral print",
                tags=(),
                base_score=0.0,
                effective_score=0.0,
                risk_flags=(),
                evidence_summary="",
            ),
            "detail": CandidateElement(
                element_id="detail-1",
                category="dress",
                slot="detail",
                value="smocked bodice",
                tags=(),
                base_score=0.0,
                effective_score=0.0,
                risk_flags=(),
                evidence_summary="",
            ),
        }
        rules = load_compatibility_rules(
            Path("tests/fixtures/evidence/dress/compatibility-rules-v2-valid.json")
        )

        evaluation = evaluate_selection_compatibility(selected, rules)

        self.assertEqual(evaluation.hard_conflicts, ())
        self.assertEqual(evaluation.soft_conflicts, ("floral print + smocked bodice",))
        self.assertEqual(evaluation.compatibility_penalty, 0.08)


if __name__ == "__main__":
    unittest.main()
