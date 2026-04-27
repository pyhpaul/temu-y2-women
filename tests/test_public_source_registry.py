from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


class PublicSourceRegistryTest(unittest.TestCase):
    def test_load_enabled_sources_returns_expected_registry_entry(self) -> None:
        from temu_y2_women.public_source_registry import load_public_source_registry

        result = load_public_source_registry(Path("data/refresh/dress/source_registry.json"))

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["source_id"], "whowhatwear-summer-2025-dress-trends")
        self.assertEqual(result[0]["adapter_id"], "whowhatwear_editorial_v1")
        self.assertEqual(result[0]["default_price_band"], "mid")

    def test_registry_rejects_duplicate_source_ids(self) -> None:
        from temu_y2_women.public_source_registry import load_public_source_registry

        payload = {
            "schema_version": "public-source-registry-v1",
            "sources": [
                {
                    "source_id": "dup-source",
                    "source_type": "public_editorial_web",
                    "source_url": "https://example.com/a",
                    "target_market": "US",
                    "category": "dress",
                    "fetch_mode": "html",
                    "adapter_id": "whowhatwear_editorial_v1",
                    "default_price_band": "mid",
                    "enabled": True,
                },
                {
                    "source_id": "dup-source",
                    "source_type": "public_editorial_web",
                    "source_url": "https://example.com/b",
                    "target_market": "US",
                    "category": "dress",
                    "fetch_mode": "html",
                    "adapter_id": "whowhatwear_editorial_v1",
                    "default_price_band": "mid",
                    "enabled": True,
                },
            ],
        }
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "registry.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(Exception, "source_id"):
                load_public_source_registry(path)

    def test_registry_rejects_unsupported_market_or_category(self) -> None:
        from temu_y2_women.public_source_registry import load_public_source_registry

        payload = {
            "schema_version": "public-source-registry-v1",
            "sources": [
                {
                    "source_id": "bad-market",
                    "source_type": "public_editorial_web",
                    "source_url": "https://example.com/a",
                    "target_market": "EU",
                    "category": "top",
                    "fetch_mode": "html",
                    "adapter_id": "whowhatwear_editorial_v1",
                    "default_price_band": "mid",
                    "enabled": True,
                }
            ],
        }
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "registry.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(Exception, "target_market|category"):
                load_public_source_registry(path)
