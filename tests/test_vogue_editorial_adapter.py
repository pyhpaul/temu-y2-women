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


class VogueEditorialAdapterTest(unittest.TestCase):
    def test_parse_vogue_editorial_html_returns_expected_snapshot(self) -> None:
        from temu_y2_women.public_source_adapters.vogue_editorial import parse_vogue_editorial_html

        result = parse_vogue_editorial_html(
            source={
                "source_id": "vogue-spring-2025-dress-trends",
                "source_type": "public_editorial_web",
                "source_url": "https://www.vogue.com/article/spring-2025-dress-trends",
                "target_market": "US",
                "category": "dress",
            },
            html=_load_fixture("vogue-spring-2025-dress-trends.html"),
            fetched_at="2026-04-30T00:00:00Z",
        )

        self.assertEqual(result, _load_snapshot("expected-vogue-spring-2025-raw-source-snapshot.json"))

    def test_parse_vogue_editorial_html_rejects_missing_published_date(self) -> None:
        from temu_y2_women.public_source_adapters.vogue_editorial import parse_vogue_editorial_html

        html = (
            "<html><head><title>Broken Vogue Fixture</title>"
            "<script type=\"application/ld+json\">"
            "{\"@context\":\"http://schema.org\",\"@type\":\"NewsArticle\","
            "\"articleBody\":\"Intro\\nAhead is Vogue's edit\\nSection text.\"}"
            "</script>"
            "</head><body><h1>Broken Vogue Fixture</h1><h2>The Butter Yellow Dress</h2></body></html>"
        )

        with self.assertRaises(GenerationError) as error:
            parse_vogue_editorial_html(
                source={
                    "source_id": "vogue-spring-2025-dress-trends",
                    "source_type": "public_editorial_web",
                    "source_url": "https://www.vogue.com/article/spring-2025-dress-trends",
                    "target_market": "US",
                    "category": "dress",
                },
                html=html,
                fetched_at="2026-04-30T00:00:00Z",
            )

        self.assertEqual(error.exception.code, "INVALID_PUBLIC_SOURCE_HTML")
        self.assertEqual(error.exception.details["field"], "captured_at")
