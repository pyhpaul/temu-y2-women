from __future__ import annotations

import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


_FEEDBACK_FIXTURE_DIR = Path("tests/fixtures/feedback/dress")
_ACTIVE_ELEMENTS_PATH = Path("data/mvp/dress/elements.json")
_LEDGER_PATH = Path("data/feedback/dress/feedback_ledger.json")
_TAXONOMY_PATH = Path("data/mvp/dress/evidence_taxonomy.json")
_TARGET_ELEMENT_ID = "dress-silhouette-a-line-001"


class StyleFamilyVisualFeedbackDryRunTest(unittest.TestCase):
    def test_dry_run_applies_visual_feedback_to_workspace_copy_only(self) -> None:
        from temu_y2_women.style_family_visual_feedback_dry_run import dry_run_visual_feedback_apply

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            batch_path = root / "visual_feedback_batch.json"
            workspace_dir = root / "dry-run"
            _write_batch(batch_path)
            before_active = _read_json(_ACTIVE_ELEMENTS_PATH)
            before_score = _element_score(before_active, _TARGET_ELEMENT_ID)

            report = dry_run_visual_feedback_apply(
                batch_path=batch_path,
                workspace_dir=workspace_dir,
                active_elements_path=_ACTIVE_ELEMENTS_PATH,
                ledger_path=_LEDGER_PATH,
                taxonomy_path=_TAXONOMY_PATH,
            )

            workspace_elements = _read_json(workspace_dir / "elements.json")

        self.assertEqual(_read_json(_ACTIVE_ELEMENTS_PATH), before_active)
        self.assertEqual(report["schema_version"], "style-family-visual-feedback-dry-run-v1")
        self.assertEqual(report["status"], "applied")
        self.assertEqual(report["summary"]["total"], 1)
        self.assertEqual(report["summary"]["applied"], 1)
        self.assertEqual(report["summary"]["errors"], 0)
        self.assertEqual(report["summary"]["keep"], 1)
        self.assertEqual(report["summary"]["net_changed_elements"], 6)
        self.assertEqual(report["cases"][0]["style_family_id"], "vacation-romantic")
        self.assertEqual(report["cases"][0]["affected_element_count"], 6)
        self.assertEqual(_element_score(workspace_elements, _TARGET_ELEMENT_ID), round(before_score + 0.02, 4))
        target_change = next(item for item in report["element_changes"] if item["element_id"] == _TARGET_ELEMENT_ID)
        self.assertEqual(target_change["delta"], 0.02)


class StyleFamilyVisualFeedbackDryRunCliTest(unittest.TestCase):
    def test_cli_writes_dry_run_report_and_prints_payload(self) -> None:
        from temu_y2_women.style_family_visual_feedback_dry_run_cli import main

        stdout = io.StringIO()
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            batch_path = root / "visual_feedback_batch.json"
            workspace_dir = root / "dry-run"
            output_path = root / "dry-run-report.json"
            _write_batch(batch_path)

            with patch("sys.stdout", stdout):
                exit_code = main(
                    [
                        "apply",
                        "--batch",
                        str(batch_path),
                        "--workspace-dir",
                        str(workspace_dir),
                        "--active-elements",
                        str(_ACTIVE_ELEMENTS_PATH),
                        "--ledger",
                        str(_LEDGER_PATH),
                        "--taxonomy",
                        str(_TAXONOMY_PATH),
                        "--output",
                        str(output_path),
                    ]
            )
            printed = json.loads(stdout.getvalue())
            written = _read_json(output_path)
            report_exists = (workspace_dir / "reports" / "vacation-romantic-feedback_report.json").exists()

        self.assertEqual(exit_code, 0)
        self.assertEqual(printed["status"], "applied")
        self.assertEqual(written, printed)
        self.assertTrue(report_exists)


def _write_batch(path: Path) -> None:
    _write_json(
        path,
        {
            "schema_version": "style-family-visual-feedback-batch-v1",
            "status": "ready",
            "cases": [
                {
                    "style_family_id": "vacation-romantic",
                    "feedback_decision": "keep",
                    "concept_path": str(_FEEDBACK_FIXTURE_DIR / "result_success.json"),
                    "feedback_review_path": str(_FEEDBACK_FIXTURE_DIR / "reviewed_keep.json"),
                }
            ],
        },
    )


def _element_score(payload: dict[str, object], element_id: str) -> float:
    elements = payload["elements"]
    for element in elements:
        if element["element_id"] == element_id:
            return float(element["base_score"])
    raise AssertionError(f"missing element {element_id}")


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))
