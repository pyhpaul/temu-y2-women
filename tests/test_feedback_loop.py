from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


_FEEDBACK_FIXTURE_DIR = Path("tests/fixtures/feedback/dress")
_ACTIVE_ELEMENTS_PATH = Path("data/mvp/dress/elements.json")
_LEDGER_SEED_PATH = Path("data/feedback/dress/feedback_ledger.json")
_FIXED_RECORDED_AT = "2026-04-27T12:00:00Z"
_TARGET_ELEMENT_IDS = {
    "dress-detail-smocked-bodice-001",
    "dress-fabric-cotton-poplin-001",
    "dress-neckline-square-001",
    "dress-pattern-floral-001",
    "dress-silhouette-a-line-001",
    "dress-sleeve-flutter-001",
}


class FeedbackPrepareTest(unittest.TestCase):
    def test_prepare_dress_concept_feedback_matches_expected_fixture(self) -> None:
        from temu_y2_women.feedback_loop import prepare_dress_concept_feedback

        result = prepare_dress_concept_feedback(
            result_path=_FEEDBACK_FIXTURE_DIR / "result_success.json",
        )

        self.assertEqual(result, _read_json(_FEEDBACK_FIXTURE_DIR / "expected_review_template.json"))

    def test_prepare_dress_concept_feedback_rejects_error_payload(self) -> None:
        from temu_y2_women.feedback_loop import prepare_dress_concept_feedback

        with TemporaryDirectory() as temp_dir:
            invalid_path = Path(temp_dir) / "error.json"
            invalid_path.write_text(
                json.dumps({"error": {"code": "NO_CANDIDATES", "message": "bad", "details": {}}}),
                encoding="utf-8",
            )
            result = prepare_dress_concept_feedback(result_path=invalid_path)

        self.assertEqual(result["error"]["code"], "INVALID_FEEDBACK_INPUT")
        self.assertEqual(result["error"]["details"]["field"], "result")


class FeedbackApplyTest(unittest.TestCase):
    def test_apply_reviewed_keep_feedback_updates_elements_ledger_and_report(self) -> None:
        from temu_y2_women.feedback_loop import apply_reviewed_dress_concept_feedback

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            elements_path, ledger_path = _seed_active_feedback_files(temp_root)
            elements_before = _read_json(elements_path)
            report_path = temp_root / "feedback_report.json"
            result = apply_reviewed_dress_concept_feedback(
                reviewed_path=_FEEDBACK_FIXTURE_DIR / "reviewed_keep.json",
                result_path=_FEEDBACK_FIXTURE_DIR / "result_success.json",
                active_elements_path=elements_path,
                ledger_path=ledger_path,
                report_path=report_path,
                recorded_at=_FIXED_RECORDED_AT,
            )

            self.assertEqual(result, _read_json(_FEEDBACK_FIXTURE_DIR / "expected_keep_report.json"))
            self.assertEqual(_read_json(report_path), _read_json(_FEEDBACK_FIXTURE_DIR / "expected_keep_report.json"))
            _assert_element_score_updates(self, before=elements_before, after=_read_json(elements_path), delta=0.02)
            self.assertEqual(_read_json(ledger_path), _read_json(_FEEDBACK_FIXTURE_DIR / "expected_ledger_after_keep.json"))

    def test_apply_reviewed_reject_feedback_updates_elements_ledger_and_report(self) -> None:
        from temu_y2_women.feedback_loop import apply_reviewed_dress_concept_feedback

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            elements_path, ledger_path = _seed_active_feedback_files(temp_root)
            elements_before = _read_json(elements_path)
            report_path = temp_root / "feedback_report.json"
            result = apply_reviewed_dress_concept_feedback(
                reviewed_path=_FEEDBACK_FIXTURE_DIR / "reviewed_reject.json",
                result_path=_FEEDBACK_FIXTURE_DIR / "result_success.json",
                active_elements_path=elements_path,
                ledger_path=ledger_path,
                report_path=report_path,
                recorded_at=_FIXED_RECORDED_AT,
            )

            self.assertEqual(result, _read_json(_FEEDBACK_FIXTURE_DIR / "expected_reject_report.json"))
            self.assertEqual(_read_json(report_path), _read_json(_FEEDBACK_FIXTURE_DIR / "expected_reject_report.json"))
            _assert_element_score_updates(self, before=elements_before, after=_read_json(elements_path), delta=-0.02)
            self.assertEqual(_read_json(ledger_path), _read_json(_FEEDBACK_FIXTURE_DIR / "expected_ledger_after_reject.json"))

    def test_apply_reviewed_feedback_rejects_tampered_selected_ids(self) -> None:
        from temu_y2_women.feedback_loop import apply_reviewed_dress_concept_feedback

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            reviewed = _read_json(_FEEDBACK_FIXTURE_DIR / "reviewed_keep.json")
            reviewed["feedback_target"]["selected_element_ids"] = ["tampered"]
            reviewed_path = temp_root / "tampered.json"
            _write_json(reviewed_path, reviewed)
            elements_path, ledger_path = _seed_active_feedback_files(temp_root)
            report_path = temp_root / "feedback_report.json"
            elements_before = _read_json(elements_path)
            ledger_before = _read_json(ledger_path)

            result = apply_reviewed_dress_concept_feedback(
                reviewed_path=reviewed_path,
                result_path=_FEEDBACK_FIXTURE_DIR / "result_success.json",
                active_elements_path=elements_path,
                ledger_path=ledger_path,
                report_path=report_path,
                recorded_at=_FIXED_RECORDED_AT,
            )

            self.assertEqual(result["error"]["code"], "INVALID_FEEDBACK_REVIEW")
            self.assertEqual(result["error"]["details"]["field"], "selected_element_ids")
            self.assertFalse(report_path.exists())
            self.assertEqual(_read_json(elements_path), elements_before)
            self.assertEqual(_read_json(ledger_path), ledger_before)

    def test_apply_reviewed_feedback_rejects_missing_active_element_target(self) -> None:
        from temu_y2_women.feedback_loop import apply_reviewed_dress_concept_feedback

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            elements_path, ledger_path = _seed_active_feedback_files(temp_root)
            report_path = temp_root / "feedback_report.json"
            elements = _read_json(elements_path)
            elements["elements"] = [
                item for item in elements["elements"] if item["element_id"] != "dress-pattern-floral-001"
            ]
            _write_json(elements_path, elements)
            elements_before = _read_json(elements_path)
            ledger_before = _read_json(ledger_path)

            result = apply_reviewed_dress_concept_feedback(
                reviewed_path=_FEEDBACK_FIXTURE_DIR / "reviewed_keep.json",
                result_path=_FEEDBACK_FIXTURE_DIR / "result_success.json",
                active_elements_path=elements_path,
                ledger_path=ledger_path,
                report_path=report_path,
                recorded_at=_FIXED_RECORDED_AT,
            )

            self.assertEqual(result["error"]["code"], "INVALID_FEEDBACK_REVIEW")
            self.assertEqual(result["error"]["details"]["field"], "selected_element_ids")
            self.assertFalse(report_path.exists())
            self.assertEqual(_read_json(elements_path), elements_before)
            self.assertEqual(_read_json(ledger_path), ledger_before)

    def test_apply_reviewed_feedback_clamps_scores_to_taxonomy_bounds(self) -> None:
        from temu_y2_women.feedback_loop import apply_reviewed_dress_concept_feedback

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            elements_path, ledger_path = _seed_active_feedback_files(temp_root)
            report_path = temp_root / "feedback_report.json"
            elements = _read_json(elements_path)
            for element in elements["elements"]:
                if element["element_id"] == "dress-silhouette-a-line-001":
                    element["base_score"] = 0.99
            _write_json(elements_path, elements)

            result = apply_reviewed_dress_concept_feedback(
                reviewed_path=_FEEDBACK_FIXTURE_DIR / "reviewed_keep.json",
                result_path=_FEEDBACK_FIXTURE_DIR / "result_success.json",
                active_elements_path=elements_path,
                ledger_path=ledger_path,
                report_path=report_path,
                recorded_at=_FIXED_RECORDED_AT,
            )

            self.assertEqual(result["summary"]["clamped_element_count"], 1)
            self.assertEqual(result["warnings"], ["base_score clamped for 1 selected elements"])
            affected = next(item for item in result["affected_elements"] if item["element_id"] == "dress-silhouette-a-line-001")
            self.assertEqual(affected["new_base_score"], 1.0)

    def test_apply_reviewed_feedback_rolls_back_on_write_stage_failure(self) -> None:
        from temu_y2_women.feedback_loop import apply_reviewed_dress_concept_feedback

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            elements_path, ledger_path = _seed_active_feedback_files(temp_root)
            report_path = temp_root / "missing-dir" / "feedback_report.json"
            elements_before = _read_json(elements_path)
            ledger_before = _read_json(ledger_path)

            result = apply_reviewed_dress_concept_feedback(
                reviewed_path=_FEEDBACK_FIXTURE_DIR / "reviewed_keep.json",
                result_path=_FEEDBACK_FIXTURE_DIR / "result_success.json",
                active_elements_path=elements_path,
                ledger_path=ledger_path,
                report_path=report_path,
                recorded_at=_FIXED_RECORDED_AT,
            )

            self.assertEqual(result["error"]["code"], "FEEDBACK_WRITE_FAILED")
            self.assertFalse(report_path.exists())
            self.assertEqual(_read_json(elements_path), elements_before)
            self.assertEqual(_read_json(ledger_path), ledger_before)


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _seed_active_feedback_files(temp_root: Path) -> tuple[Path, Path]:
    elements_path = temp_root / "elements.json"
    ledger_path = temp_root / "feedback_ledger.json"
    elements_path.write_text(_ACTIVE_ELEMENTS_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    ledger_path.write_text(_LEDGER_SEED_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    return elements_path, ledger_path


def _assert_element_score_updates(
    test_case: unittest.TestCase,
    *,
    before: dict[str, object],
    after: dict[str, object],
    delta: float,
) -> None:
    before_elements = before["elements"]
    after_elements = after["elements"]
    test_case.assertEqual(len(after_elements), len(before_elements))

    before_by_id = {item["element_id"]: item for item in before_elements}
    after_by_id = {item["element_id"]: item for item in after_elements}
    test_case.assertEqual(set(after_by_id), set(before_by_id))

    for element_id, before_item in before_by_id.items():
        after_item = after_by_id[element_id]
        expected_score = before_item["base_score"] + (delta if element_id in _TARGET_ELEMENT_IDS else 0.0)
        test_case.assertAlmostEqual(after_item["base_score"], expected_score, places=7, msg=element_id)

        before_without_score = {key: value for key, value in before_item.items() if key != "base_score"}
        after_without_score = {key: value for key, value in after_item.items() if key != "base_score"}
        test_case.assertEqual(after_without_score, before_without_score, msg=element_id)
