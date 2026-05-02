from __future__ import annotations

import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


class StyleFamilyVisualDriftTest(unittest.TestCase):
    def test_build_check_passes_when_family_and_selected_elements_match(self) -> None:
        from temu_y2_women.style_family_visual_drift import build_style_family_visual_drift_check

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_path = root / "manifest.json"
            _write_manifest(manifest_path)

            with patch(
                "temu_y2_women.style_family_visual_drift.generate_dress_concept",
                side_effect=[
                    _concept_result("vacation-romantic", {"silhouette": "a-line", "color_family": "white"}),
                    _concept_result("clean-minimal", {"silhouette": "shift", "color_family": "blue"}),
                ],
            ):
                report = build_style_family_visual_drift_check(manifest_path=manifest_path)

        self.assertEqual(report["schema_version"], "style-family-visual-drift-check-v1")
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["summary"], {"total": 2, "passed": 2, "failed": 0, "errors": 0, "family_mismatches": 0, "selected_element_drifts": 0})
        self.assertEqual(report["cases"][0]["status"], "passed")
        self.assertEqual(report["cases"][0]["changed_slots"], [])

    def test_build_check_fails_on_family_or_selected_element_drift(self) -> None:
        from temu_y2_women.style_family_visual_drift import build_style_family_visual_drift_check

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_path = root / "manifest.json"
            _write_manifest(manifest_path)

            with patch(
                "temu_y2_women.style_family_visual_drift.generate_dress_concept",
                side_effect=[
                    _concept_result("vacation-romantic", {"silhouette": "a-line", "color_family": "white"}),
                    _concept_result("city-polished", {"silhouette": "sheath", "color_family": "brown"}),
                ],
            ):
                report = build_style_family_visual_drift_check(manifest_path=manifest_path)

        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["summary"]["family_mismatches"], 1)
        self.assertEqual(report["summary"]["selected_element_drifts"], 1)
        failed = report["cases"][1]
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["actual_style_family_id"], "city-polished")
        self.assertEqual(
            failed["changed_slots"],
            [
                {"slot": "color_family", "expected": "blue", "actual": "brown"},
                {"slot": "silhouette", "expected": "shift", "actual": "sheath"},
            ],
        )


class StyleFamilyVisualDriftCliTest(unittest.TestCase):
    def test_cli_writes_report_and_returns_nonzero_for_drift(self) -> None:
        from temu_y2_women.style_family_visual_drift_cli import main

        stdout = io.StringIO()
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_path = root / "manifest.json"
            output_path = root / "drift.json"
            _write_manifest(manifest_path)

            with patch(
                "temu_y2_women.style_family_visual_drift.generate_dress_concept",
                side_effect=[
                    _concept_result("vacation-romantic", {"silhouette": "a-line", "color_family": "white"}),
                    _concept_result("city-polished", {"silhouette": "sheath", "color_family": "brown"}),
                ],
            ), patch("sys.stdout", stdout):
                exit_code = main(["check", "--manifest", str(manifest_path), "--output", str(output_path)])
            printed = json.loads(stdout.getvalue())
            written = _read_json(output_path)

        self.assertEqual(exit_code, 1)
        self.assertEqual(printed, written)
        self.assertEqual(written["status"], "failed")


def _write_manifest(path: Path) -> None:
    root = path.parent
    cases = [
        _manifest_case(root, "vacation-romantic", {"silhouette": "a-line", "color_family": "white"}),
        _manifest_case(root, "clean-minimal", {"silhouette": "shift", "color_family": "blue"}),
    ]
    _write_json(path, {"schema_version": "style-family-anchor-validation-v1", "cases": cases})


def _manifest_case(root: Path, family: str, selected_elements: dict[str, str]) -> dict[str, object]:
    request_path = root / f"{family}.json"
    _write_json(request_path, {"category": "dress", "style_family": family})
    return {
        "style_family_id": family,
        "request_path": str(request_path),
        "selected_elements": selected_elements,
    }


def _concept_result(family: str, selected_values: dict[str, str]) -> dict[str, object]:
    selected_elements = {
        slot: {"slot": slot, "element_id": f"{slot}-{value}", "value": value}
        for slot, value in selected_values.items()
    }
    return {
        "selected_style_family": {"style_family_id": family},
        "composed_concept": {"selected_elements": selected_elements, "concept_score": 0.8},
        "prompt_bundle": {"render_jobs": [{"prompt_id": "hero_front", "prompt": f"{family} prompt"}]},
    }


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))
