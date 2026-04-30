from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


class PublicSourceRegistryTest(unittest.TestCase):
    def test_load_enabled_sources_returns_expected_registry_entry(self) -> None:
        from temu_y2_women.public_source_registry import load_public_source_registry

        result = load_public_source_registry(Path("data/refresh/dress/source_registry.json"))

        self.assertEqual(len(result), 4)
        self.assertEqual(result[0]["source_id"], "whowhatwear-summer-2025-dress-trends")
        self.assertEqual(result[0]["adapter_id"], "whowhatwear_editorial_v1")
        self.assertEqual(result[0]["default_price_band"], "mid")
        self.assertEqual(result[0]["priority"], 100)
        self.assertEqual(result[0]["weight"], 1.0)

    def test_load_enabled_sources_includes_roundup_routing_fields(self) -> None:
        from temu_y2_women.public_source_registry import load_public_source_registry

        result = load_public_source_registry(Path("data/refresh/dress/source_registry.json"))

        roundup = next(source for source in result if source["source_id"] == "whowhatwear-best-summer-dresses-2025")
        self.assertEqual(roundup["source_type"], "public_roundup_web")
        self.assertEqual(roundup["adapter_id"], "whowhatwear_roundup_v1")
        self.assertEqual(roundup["pipeline_mode"], "roundup_image_cards")
        self.assertEqual(roundup["card_limit"], 12)
        self.assertEqual(roundup["aggregation_threshold"], 2)
        self.assertEqual(roundup["observation_model"], "gpt-4.1-mini")

    def test_select_public_sources_returns_all_enabled_sources_by_default(self) -> None:
        from temu_y2_women.public_source_registry import load_public_source_registry, select_public_sources

        registry = load_public_source_registry(Path("data/refresh/dress/source_registry.json"))

        result = select_public_sources(registry)

        self.assertEqual(
            [source["source_id"] for source in result],
            [
                "whowhatwear-summer-2025-dress-trends",
                "whowhatwear-summer-dress-trends-2025",
                "marieclaire-summer-2025-dress-trends",
                "whowhatwear-best-summer-dresses-2025",
            ],
        )

    def test_select_public_sources_filters_requested_ids_in_requested_order(self) -> None:
        from temu_y2_women.public_source_registry import load_public_source_registry, select_public_sources

        registry = load_public_source_registry(Path("data/refresh/dress/source_registry.json"))

        result = select_public_sources(
            registry,
            source_ids=[
                "marieclaire-summer-2025-dress-trends",
                "whowhatwear-summer-dress-trends-2025",
            ],
        )

        self.assertEqual(
            [source["source_id"] for source in result],
            [
                "marieclaire-summer-2025-dress-trends",
                "whowhatwear-summer-dress-trends-2025",
            ],
        )

    def test_select_public_sources_rejects_unknown_source_id(self) -> None:
        from temu_y2_women.public_source_registry import load_public_source_registry, select_public_sources

        registry = load_public_source_registry(Path("data/refresh/dress/source_registry.json"))

        with self.assertRaisesRegex(Exception, "source selection contains unknown source_id"):
            select_public_sources(registry, source_ids=["unknown-source"])

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
                    "pipeline_mode": "editorial_text",
                    "priority": 100,
                    "weight": 1.0,
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
                    "pipeline_mode": "editorial_text",
                    "priority": 90,
                    "weight": 0.9,
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
                    "pipeline_mode": "editorial_text",
                    "priority": 100,
                    "weight": 1.0,
                    "enabled": True,
                }
            ],
        }
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "registry.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(Exception, "target_market|category"):
                load_public_source_registry(path)

    def test_registry_rejects_non_positive_priority_or_weight(self) -> None:
        from temu_y2_women.public_source_registry import load_public_source_registry

        payload = {
            "schema_version": "public-source-registry-v1",
            "sources": [
                {
                    "source_id": "bad-priority",
                    "source_type": "public_editorial_web",
                    "source_url": "https://example.com/a",
                    "target_market": "US",
                    "category": "dress",
                    "fetch_mode": "html",
                    "adapter_id": "whowhatwear_editorial_v1",
                    "default_price_band": "mid",
                    "pipeline_mode": "editorial_text",
                    "priority": 0,
                    "weight": 0.5,
                    "enabled": True,
                }
            ],
        }
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "registry.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(Exception, "priority"):
                load_public_source_registry(path)

    def test_registry_rejects_roundup_source_missing_required_routing_fields(self) -> None:
        from temu_y2_women.public_source_registry import load_public_source_registry

        payload = {
            "schema_version": "public-source-registry-v1",
            "sources": [
                {
                    "source_id": "roundup-source",
                    "source_type": "public_roundup_web",
                    "source_url": "https://example.com/a",
                    "target_market": "US",
                    "category": "dress",
                    "fetch_mode": "html",
                    "adapter_id": "whowhatwear_roundup_v1",
                    "default_price_band": "mid",
                    "pipeline_mode": "roundup_image_cards",
                    "aggregation_threshold": 2,
                    "observation_model": "gpt-4.1-mini",
                    "priority": 70,
                    "weight": 0.7,
                    "enabled": True,
                }
            ],
        }
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "registry.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(Exception, "card_limit"):
                load_public_source_registry(path)
