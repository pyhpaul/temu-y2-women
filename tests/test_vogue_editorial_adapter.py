from __future__ import annotations

import json
from pathlib import Path
import unittest

from temu_y2_women.errors import GenerationError


_FIXTURE_DIR = Path("tests/fixtures/public_sources/dress")


def _load_fixture(name: str) -> str:
    return (_FIXTURE_DIR / name).read_text(encoding="utf-8")


def _load_snapshot(name: str) -> dict[str, object]:
    return json.loads(_load_fixture(name))


def _source() -> dict[str, object]:
    return {
        "source_id": "vogue-spring-2025-dress-trends",
        "source_type": "public_editorial_web",
        "source_url": "https://www.vogue.com/article/spring-2025-dress-trends",
        "target_market": "US",
        "category": "dress",
        "parser_config": {
            "section_rules": [
                {"heading": "The Butter Yellow Dress", "section_id": "butter-yellow-dress", "tags": ["spring", "color"]},
                {"heading": "The Drop Waist Dress", "section_id": "drop-waist-dress", "tags": ["spring", "silhouette"]},
                {"heading": "The Polka-Dot Dress", "section_id": "polka-dot-dress", "tags": ["spring", "print"]},
                {"heading": "Fashion-Forward Florals", "section_id": "fashion-forward-florals", "tags": ["spring", "print"]},
            ]
        },
    }


class VogueEditorialAdapterTest(unittest.TestCase):
    def test_parse_vogue_editorial_html_returns_expected_snapshot(self) -> None:
        from temu_y2_women.public_source_adapters.vogue_editorial import parse_vogue_editorial_html

        result = parse_vogue_editorial_html(
            source=_source(),
            html=_load_fixture("vogue-spring-2025-dress-trends.html"),
            fetched_at="2026-04-30T00:00:00Z",
        )

        self.assertEqual(result, _load_snapshot("expected-vogue-spring-2025-raw-source-snapshot.json"))

    def test_parse_vogue_editorial_html_rejects_missing_published_date(self) -> None:
        from temu_y2_women.public_source_adapters.vogue_editorial import parse_vogue_editorial_html

        html = _load_fixture("vogue-spring-2025-dress-trends.html").replace("article:published_time", "missing")

        with self.assertRaises(GenerationError) as error_context:
            parse_vogue_editorial_html(source=_source(), html=html, fetched_at="2026-04-30T00:00:00Z")

        self.assertEqual(error_context.exception.code, "INVALID_PUBLIC_SOURCE_HTML")
        self.assertEqual(error_context.exception.details["field"], "captured_at")
