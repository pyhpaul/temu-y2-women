from __future__ import annotations

import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


_FIXTURE_DIR = Path("tests/fixtures/compatibility_rules")


class CompatibilityRulePromotionTest(unittest.TestCase):
    def test_prepare_rule_review_builds_expected_template(self) -> None:
        from temu_y2_women.compatibility_rule_promotion import prepare_compatibility_rule_review

        with TemporaryDirectory() as temp_dir:
            active_rules_path = _seed_active_rules(Path(temp_dir))
            result = prepare_compatibility_rule_review(
                draft_rules_path=_FIXTURE_DIR / "draft_conflict_rules_valid.json",
                active_rules_path=active_rules_path,
            )

        self.assertEqual(result, _expected_review_template())

    def test_validate_reviewed_rule_promotion_accepts_valid_review(self) -> None:
        from temu_y2_women.compatibility_rule_promotion import (
            validate_reviewed_compatibility_rule_promotion,
        )

        with TemporaryDirectory() as temp_dir:
            active_rules_path = _seed_active_rules(Path(temp_dir))
            result = validate_reviewed_compatibility_rule_promotion(
                reviewed_path=_FIXTURE_DIR / "reviewed_conflict_rules_valid.json",
                draft_rules_path=_FIXTURE_DIR / "draft_conflict_rules_valid.json",
                active_rules_path=active_rules_path,
            )

        self.assertEqual(result, _read_json(_FIXTURE_DIR / "reviewed_conflict_rules_valid.json"))

    def test_apply_reviewed_rule_promotion_writes_active_rules_and_report(self) -> None:
        from temu_y2_women.compatibility_rule_promotion import (
            apply_reviewed_compatibility_rule_promotion,
        )

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            active_rules_path = _seed_active_rules(temp_root)
            report_path = temp_root / "promotion_report.json"

            result = apply_reviewed_compatibility_rule_promotion(
                reviewed_path=_FIXTURE_DIR / "reviewed_conflict_rules_valid.json",
                draft_rules_path=_FIXTURE_DIR / "draft_conflict_rules_valid.json",
                active_rules_path=active_rules_path,
                report_path=report_path,
            )

            self.assertEqual(result, _expected_promotion_report("reviewed_conflict_rules_valid.json"))
            self.assertEqual(_read_json(active_rules_path), _expected_active_rules())
            self.assertEqual(_read_json(report_path), _expected_promotion_report("reviewed_conflict_rules_valid.json"))

    def test_invalid_review_fails_before_mutation(self) -> None:
        from temu_y2_women.compatibility_rule_promotion import (
            apply_reviewed_compatibility_rule_promotion,
        )

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            active_rules_path = _seed_active_rules(temp_root)
            before_rules = active_rules_path.read_text(encoding="utf-8")
            report_path = temp_root / "promotion_report.json"

            result = apply_reviewed_compatibility_rule_promotion(
                reviewed_path=_FIXTURE_DIR / "reviewed_conflict_rules_invalid.json",
                draft_rules_path=_FIXTURE_DIR / "draft_conflict_rules_valid.json",
                active_rules_path=active_rules_path,
                report_path=report_path,
            )

            self.assertEqual(result["error"]["code"], "INVALID_PROMOTION_REVIEW")
            self.assertEqual(result["error"]["details"]["field"], "decision")
            self.assertEqual(active_rules_path.read_text(encoding="utf-8"), before_rules)
            self.assertFalse(report_path.exists())

    def test_rejected_rule_is_excluded_from_active_output(self) -> None:
        from temu_y2_women.compatibility_rule_promotion import (
            apply_reviewed_compatibility_rule_promotion,
        )

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            active_rules_path = _seed_active_rules(temp_root)
            reviewed = _read_json(_FIXTURE_DIR / "reviewed_conflict_rules_valid.json")
            reviewed["rules"][0]["decision"] = "reject"
            reviewed["rules"][0]["proposed_rule"] = None
            reviewed_path = temp_root / "reviewed_reject.json"
            _write_json(reviewed_path, reviewed)
            report_path = temp_root / "promotion_report.json"

            result = apply_reviewed_compatibility_rule_promotion(
                reviewed_path=reviewed_path,
                draft_rules_path=_FIXTURE_DIR / "draft_conflict_rules_valid.json",
                active_rules_path=active_rules_path,
                report_path=report_path,
            )

            self.assertEqual(result["summary"], {"accepted": 0, "rejected": 1, "created": 0, "updated": 0})
            self.assertEqual(_read_json(active_rules_path), _expected_empty_promoted_rules())
            self.assertEqual(_read_json(report_path), _expected_promotion_report("reviewed_reject.json", "reject"))


class CompatibilityRulePromotionCliTest(unittest.TestCase):
    def test_prepare_cli_prints_review_template_and_writes_output(self) -> None:
        from temu_y2_women.compatibility_rule_promotion_cli import main

        stdout = io.StringIO()
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            active_rules_path = _seed_active_rules(temp_root)
            output_path = temp_root / "review.json"
            with patch("sys.stdout", stdout):
                exit_code = main(
                    [
                        "prepare",
                        "--draft-rules",
                        str(_FIXTURE_DIR / "draft_conflict_rules_valid.json"),
                        "--active-rules",
                        str(active_rules_path),
                        "--output",
                        str(output_path),
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(json.loads(stdout.getvalue()), _expected_review_template())
            self.assertEqual(_read_json(output_path), _expected_review_template())

    def test_apply_cli_prints_report_and_writes_outputs(self) -> None:
        from temu_y2_women.compatibility_rule_promotion_cli import main

        stdout = io.StringIO()
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            active_rules_path = _seed_active_rules(temp_root)
            report_path = temp_root / "promotion_report.json"
            with patch("sys.stdout", stdout):
                exit_code = main(
                    [
                        "apply",
                        "--reviewed",
                        str(_FIXTURE_DIR / "reviewed_conflict_rules_valid.json"),
                        "--draft-rules",
                        str(_FIXTURE_DIR / "draft_conflict_rules_valid.json"),
                        "--active-rules",
                        str(active_rules_path),
                        "--report-output",
                        str(report_path),
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(json.loads(stdout.getvalue()), _expected_promotion_report("reviewed_conflict_rules_valid.json"))
            self.assertEqual(_read_json(active_rules_path), _expected_active_rules())
            self.assertEqual(_read_json(report_path), _expected_promotion_report("reviewed_conflict_rules_valid.json"))


def _expected_review_template() -> dict[str, object]:
    return {
        "schema_version": "compatibility-rule-review-v1",
        "category": "dress",
        "rules": [
            {
                "draft_rule_id": "draft-conflict-pattern-floral-print__detail-smocked-bodice",
                "merge_action": "create",
                "matched_active_rule_id": None,
                "canonical_identity": {
                    "left_slot": "pattern",
                    "left_value": "floral print",
                    "right_slot": "detail",
                    "right_value": "smocked bodice",
                },
                "merge_rationale": {
                    "rule": "canonical-pair",
                    "resolved_rule_id": "dress-pattern-floral-print__detail-smocked-bodice",
                    "matched_active_rule_id": None,
                },
                "source_feedback_ids": ["fb-001", "fb-004"],
                "decision": "pending",
                "proposed_rule": _expected_active_rules()["rules"][0],
            }
        ],
    }


def _expected_active_rules() -> dict[str, object]:
    return {
        "schema_version": "compatibility-rules-v2",
        "rules": [
            {
                "rule_id": "dress-pattern-floral-print__detail-smocked-bodice",
                "category": "dress",
                "left_slot": "pattern",
                "left_value": "floral print",
                "right_slot": "detail",
                "right_value": "smocked bodice",
                "severity": "weak",
                "penalty": 0.08,
                "reason": "visual density rises when both are emphasized in the same dress direction",
                "scope": {
                    "category": "dress",
                    "target_market": "US",
                    "season_tags": ["summer"],
                    "occasion_tags": ["vacation"],
                    "price_bands": ["mid"],
                },
                "evidence_summary": "Low-confidence curated starter rule promoted from reviewed style feedback.",
                "evidence": {
                    "review_reject_rate": 0.61,
                    "pair_presence_count": 9,
                    "source_feedback_ids": ["fb-001", "fb-004"],
                },
                "confidence": 0.74,
                "decision_source": "reviewed_heuristic",
                "status": "active",
            }
        ],
    }


def _expected_promotion_report(reviewed_name: str, decision: str = "accept") -> dict[str, object]:
    return {
        "schema_version": "compatibility-rule-promotion-report-v1",
        "category": "dress",
        "source_artifacts": {
            "draft_rules": "draft_conflict_rules_valid.json",
            "reviewed_decisions": reviewed_name,
        },
        "summary": {
            "accepted": 1 if decision == "accept" else 0,
            "rejected": 0 if decision == "accept" else 1,
            "created": 1 if decision == "accept" else 0,
            "updated": 0,
        },
        "rules": [
            {
                "draft_rule_id": "draft-conflict-pattern-floral-print__detail-smocked-bodice",
                "decision": decision,
                "merge_action": "create",
                "rule_id": "dress-pattern-floral-print__detail-smocked-bodice" if decision == "accept" else None,
                "source_feedback_ids": ["fb-001", "fb-004"],
            }
        ],
        "warnings": [],
    }


def _empty_active_rules() -> dict[str, object]:
    return {"schema_version": "mvp-v1", "rules": []}


def _expected_empty_promoted_rules() -> dict[str, object]:
    return {"schema_version": "compatibility-rules-v2", "rules": []}


def _seed_active_rules(temp_root: Path) -> Path:
    active_rules_path = temp_root / "compatibility_rules.json"
    _write_json(active_rules_path, _empty_active_rules())
    return active_rules_path


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
