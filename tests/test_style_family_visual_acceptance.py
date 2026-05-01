from __future__ import annotations

import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


_FAMILIES = ("vacation-romantic", "clean-minimal", "city-polished", "party-fitted")


class StyleFamilyVisualAcceptanceTest(unittest.TestCase):
    def test_build_report_accepts_complete_four_family_render_set(self) -> None:
        from temu_y2_women.style_family_visual_acceptance import build_visual_acceptance_report

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_path = root / "manifest.json"
            renders_root = root / "renders"
            _write_manifest(manifest_path)
            _write_render_outputs(renders_root)

            report = build_visual_acceptance_report(
                manifest_path=manifest_path,
                renders_root=renders_root,
                status="accepted",
                notes=_acceptance_notes(),
            )

        self.assertEqual(report["schema_version"], "style-family-visual-acceptance-v1")
        self.assertEqual(report["status"], "accepted")
        self.assertEqual(report["summary"], {"total": 4, "ready": 4, "missing": 0})
        self.assertEqual([case["style_family_id"] for case in report["cases"]], list(_FAMILIES))
        self.assertTrue(all(case["image_exists"] for case in report["cases"]))
        self.assertTrue(all(case["report_exists"] for case in report["cases"]))
        self.assertEqual(report["cases"][0]["image_bytes"], len(b"vacation-romantic-image"))
        self.assertEqual(report["cases"][0]["note"], "white floral resort mini reads romantic vacation")
        self.assertEqual(report["cases"][0]["selected_elements"]["silhouette"], "a-line")

    def test_build_report_marks_missing_artifacts_incomplete(self) -> None:
        from temu_y2_women.style_family_visual_acceptance import build_visual_acceptance_report

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_path = root / "manifest.json"
            renders_root = root / "renders"
            _write_manifest(manifest_path)
            _write_render_outputs(renders_root, skip_family="party-fitted")

            report = build_visual_acceptance_report(
                manifest_path=manifest_path,
                renders_root=renders_root,
                status="accepted",
                notes=_acceptance_notes(),
            )

        self.assertEqual(report["status"], "incomplete")
        self.assertEqual(report["summary"], {"total": 4, "ready": 3, "missing": 1})
        missing_case = report["cases"][-1]
        self.assertEqual(missing_case["style_family_id"], "party-fitted")
        self.assertFalse(missing_case["image_exists"])
        self.assertFalse(missing_case["report_exists"])


class StyleFamilyVisualAcceptanceCliTest(unittest.TestCase):
    def test_cli_writes_report_and_prints_summary(self) -> None:
        from temu_y2_women.style_family_visual_acceptance_cli import main

        stdout = io.StringIO()
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_path = root / "manifest.json"
            renders_root = root / "renders"
            output_path = root / "visual_acceptance.json"
            _write_manifest(manifest_path)
            _write_render_outputs(renders_root)

            with patch("sys.stdout", stdout):
                exit_code = main(
                    [
                        "build",
                        "--manifest",
                        str(manifest_path),
                        "--renders-root",
                        str(renders_root),
                        "--output",
                        str(output_path),
                        "--status",
                        "accepted",
                        "--note",
                        "vacation-romantic=white floral resort mini reads romantic vacation",
                    ]
                )
            written = _read_json(output_path)

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "accepted")
        self.assertEqual(written, payload)
        self.assertEqual(written["summary"]["ready"], 4)


def _write_manifest(path: Path) -> None:
    cases = []
    for family in _FAMILIES:
        cases.append(
            {
                "style_family_id": family,
                "selected_elements": {
                    "silhouette": "a-line" if family == "vacation-romantic" else "shift",
                    "color_family": "white" if family == "vacation-romantic" else "blue",
                },
            }
        )
    _write_json(path, {"schema_version": "style-family-anchor-validation-v1", "cases": cases})


def _write_render_outputs(renders_root: Path, *, skip_family: str | None = None) -> None:
    for family in _FAMILIES:
        if family == skip_family:
            continue
        family_dir = renders_root / family
        family_dir.mkdir(parents=True)
        (family_dir / "hero_front.png").write_bytes(f"{family}-image".encode("utf-8"))
        _write_json(
            family_dir / "image_render_report.json",
            {
                "schema_version": "image-render-report-v1",
                "model": "gpt-image-2",
                "base_url": "https://provider.test/v1",
                "image_path": str(family_dir / "hero_front.png"),
                "images": [{"prompt_id": "hero_front", "prompt_fingerprint": f"{family}-fp"}],
            },
        )


def _acceptance_notes() -> dict[str, str]:
    return {
        "vacation-romantic": "white floral resort mini reads romantic vacation",
        "clean-minimal": "solid blue midi reads clean minimal",
        "city-polished": "brown tailored stripe reads city polished",
        "party-fitted": "red satin bodycon reads party fitted",
    }


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))
