from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


_FIXTURE_DIR = Path("tests/fixtures/product_image_signals/dress")


class ProductImageSignalRunTest(unittest.TestCase):
    def test_run_product_image_signal_ingestion_writes_expected_artifacts(self) -> None:
        from temu_y2_women.product_image_signal_run import run_product_image_signal_ingestion

        manifest = _read_json(_FIXTURE_DIR / "input-manifest.json")

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            resolved_manifest = _with_real_image_paths(manifest, temp_root)
            manifest_path = temp_root / "manifest.json"
            manifest_path.write_text(json.dumps(resolved_manifest), encoding="utf-8")

            report = run_product_image_signal_ingestion(
                input_path=manifest_path,
                output_root=temp_root / "runs",
                observed_at="2026-04-29T00:00:00Z",
                observe_image=_fake_observe_image,
            )
            run_dir = temp_root / "runs" / report["run_id"]

            self.assertTrue((run_dir / "signal_bundle.json").is_file())
            self.assertTrue((run_dir / "draft_elements.json").is_file())

        self.assertEqual(report, _read_json(_FIXTURE_DIR / "expected-run-report.json"))


def _fake_observe_image(image: dict[str, object]) -> dict[str, object]:
    if image["image_id"] == "dress-product-001-front":
        return {
            "observed_slots": [
                {"slot": "neckline", "value": "square neckline", "evidence_summary": "front view shows a flat squared neck opening"},
                {"slot": "dress_length", "value": "mini", "evidence_summary": "hemline sits above the knee"},
            ],
            "abstained_slots": ["opacity_level"],
            "warnings": [],
        }
    return {
        "observed_slots": [
            {"slot": "detail", "value": "smocked bodice", "evidence_summary": "back panel shows dense elastic smocking"},
        ],
        "abstained_slots": ["neckline"],
        "warnings": ["sleeve not visible in back view"],
    }


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _with_real_image_paths(payload: dict[str, object], temp_root: Path) -> dict[str, object]:
    rewritten = json.loads(json.dumps(payload))
    for product in rewritten["products"]:
        for image in product["images"]:
            image_path = temp_root / Path(image["image_path"]).name
            image_path.write_bytes(image["image_id"].encode("utf-8"))
            image["image_path"] = str(image_path)
    return rewritten
