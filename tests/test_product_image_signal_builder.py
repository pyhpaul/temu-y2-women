from __future__ import annotations

import json
from pathlib import Path
import unittest


_FIXTURE_DIR = Path("tests/fixtures/product_image_signals/dress")


class ProductImageSignalBuilderTest(unittest.TestCase):
    def test_build_product_image_signal_bundle_aggregates_candidates_without_title_leakage(self) -> None:
        from temu_y2_women.product_image_signal_builder import build_product_image_signal_bundle

        manifest = _read_json(_FIXTURE_DIR / "input-manifest.json")
        observations = _read_json(_FIXTURE_DIR / "expected-image-observations.json")
        result = build_product_image_signal_bundle(
            manifest=manifest,
            observations=observations,
            observed_at="2026-04-29T00:00:00Z",
        )

        self.assertEqual(result, _read_json(_FIXTURE_DIR / "expected-signal-bundle.json"))
        signal = result["signals"][0]
        self.assertEqual(signal["title"], "Product image observation for dress-product-001")
        self.assertEqual(
            signal["summary"],
            "Structured candidates aggregated from 2 submitted product images.",
        )
        self.assertNotIn("square neckline", signal["title"])


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))
