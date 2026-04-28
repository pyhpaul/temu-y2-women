from __future__ import annotations

import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


_FIXTURE_DIR = Path("tests/fixtures/compatibility_rules")


class ConflictRuleFeedbackDeriverTest(unittest.TestCase):
    def test_generates_draft_conflict_rules_from_feedback_ledger(self) -> None:
        from temu_y2_women.conflict_rule_feedback_deriver import derive_conflict_rules_from_feedback_ledger

        result = derive_conflict_rules_from_feedback_ledger(
            _FIXTURE_DIR / "feedback-ledger-sample.json"
        )

        self.assertEqual(
            result,
            _read_json(_FIXTURE_DIR / "draft_conflict_rules_expected.json"),
        )

    def test_ignores_pairs_below_minimum_sample_threshold(self) -> None:
        from temu_y2_women.conflict_rule_feedback_deriver import derive_conflict_rules_from_feedback_ledger

        with TemporaryDirectory() as temp_dir:
            ledger_path = Path(temp_dir) / "ledger.json"
            _write_json(ledger_path, _ledger_with_decisions(["reject", "keep"]))
            result = derive_conflict_rules_from_feedback_ledger(ledger_path)

        self.assertEqual(result["rules"], [])
        self.assertEqual(result["summary"]["evaluated_pair_count"], 1)
        self.assertEqual(result["summary"]["skipped_pair_count"], 1)

    def test_maps_high_reject_rate_to_strong_suggestion(self) -> None:
        from temu_y2_women.conflict_rule_feedback_deriver import derive_conflict_rules_from_feedback_ledger

        with TemporaryDirectory() as temp_dir:
            ledger_path = Path(temp_dir) / "ledger.json"
            _write_json(
                ledger_path,
                _ledger_with_decisions(["reject", "reject", "reject", "reject", "keep"]),
            )
            result = derive_conflict_rules_from_feedback_ledger(ledger_path)

        rule = result["rules"][0]
        self.assertEqual(rule["suggested_severity"], "strong")
        self.assertEqual(rule["suggested_penalty"], 0.0)
        self.assertEqual(rule["evidence"]["review_reject_rate"], 0.8)

    def test_maps_moderate_reject_rate_to_weak_suggestion(self) -> None:
        from temu_y2_women.conflict_rule_feedback_deriver import derive_conflict_rules_from_feedback_ledger

        with TemporaryDirectory() as temp_dir:
            ledger_path = Path(temp_dir) / "ledger.json"
            _write_json(
                ledger_path,
                _ledger_with_decisions(["reject", "reject", "keep", "keep"]),
            )
            result = derive_conflict_rules_from_feedback_ledger(ledger_path)

        rule = result["rules"][0]
        self.assertEqual(rule["suggested_severity"], "weak")
        self.assertEqual(rule["suggested_penalty"], 0.08)
        self.assertEqual(rule["left_value"], "floral print")

    def test_cli_writes_payload_and_prints_compact_report(self) -> None:
        from temu_y2_women.conflict_rule_feedback_cli import main

        stdout = io.StringIO()
        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "draft_conflict_rules.json"
            with patch("sys.stdout", stdout):
                exit_code = main(
                    [
                        "derive",
                        "--ledger",
                        str(_FIXTURE_DIR / "feedback-ledger-sample.json"),
                        "--output",
                        str(output_path),
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(
                _read_json(output_path),
                _read_json(_FIXTURE_DIR / "draft_conflict_rules_expected.json"),
            )
            self.assertEqual(
                json.loads(stdout.getvalue()),
                {
                    "draft_count": 1,
                    "output_path": str(output_path),
                    "skipped_pair_count": 0,
                },
            )


def _ledger_with_decisions(decisions: list[str]) -> dict[str, object]:
    records = [_record(index, decision) for index, decision in enumerate(decisions, start=1)]
    return {"schema_version": "feedback-ledger-v1", "records": records}


def _record(index: int, decision: str) -> dict[str, object]:
    return {
        "feedback_id": f"feedback-{index:03d}",
        "category": "dress",
        "decision": decision,
        "feedback_target": {
            "selected_elements": [
                {
                    "slot": "pattern",
                    "element_id": "dress-pattern-floral-001",
                    "value": "floral print",
                },
                {
                    "slot": "detail",
                    "element_id": "dress-detail-smocked-bodice-001",
                    "value": "smocked bodice",
                },
            ]
        },
    }


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
