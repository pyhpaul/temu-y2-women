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
        "source_id": "harpersbazaar-best-summer-dresses-2025",
        "source_type": "public_roundup_web",
        "source_url": "https://www.harpersbazaar.com/fashion/trends/g65192976/best-summer-dresses-for-women/",
        "target_market": "US",
        "category": "dress",
    }


class HearstRoundupAdapterTest(unittest.TestCase):
    def test_parse_hearst_roundup_html_returns_expected_snapshot(self) -> None:
        from temu_y2_women.public_source_adapters.hearst_roundup import parse_hearst_roundup_html

        result = parse_hearst_roundup_html(
            source=_source(),
            html=_load_fixture("harpersbazaar-best-summer-dresses-2025.html"),
            fetched_at="2026-04-30T00:00:00Z",
        )

        self.assertEqual(result, _load_snapshot("expected-harpersbazaar-best-summer-dresses-2025-raw-source-snapshot.json"))

    def test_parse_hearst_roundup_html_rejects_missing_cards(self) -> None:
        from temu_y2_women.public_source_adapters.hearst_roundup import parse_hearst_roundup_html

        html = (
            "<html><head>"
            "<title>The Best Summer Dresses 2025 to Shop Now and Wear All Season Long</title>"
            '<meta property="article:published_time" content="2025-06-30T18:07:00Z" />'
            '<script id="__NEXT_DATA__" type="application/json">'
            '{"props":{"pageProps":{"slides":[]}}}'
            "</script></head><body></body></html>"
        )

        with self.assertRaises(GenerationError) as error_context:
            parse_hearst_roundup_html(source=_source(), html=html, fetched_at="2026-04-30T00:00:00Z")

        self.assertEqual(error_context.exception.code, "INVALID_PUBLIC_SOURCE_HTML")
        self.assertEqual(error_context.exception.details["field"], "cards")

    def test_parse_hearst_roundup_html_rejects_missing_page_title(self) -> None:
        from temu_y2_women.public_source_adapters.hearst_roundup import parse_hearst_roundup_html

        html = _load_fixture("harpersbazaar-best-summer-dresses-2025.html").replace("<title>", "<title-disabled>")

        with self.assertRaises(GenerationError) as error_context:
            parse_hearst_roundup_html(source=_source(), html=html, fetched_at="2026-04-30T00:00:00Z")

        self.assertEqual(error_context.exception.code, "INVALID_PUBLIC_SOURCE_HTML")
        self.assertEqual(error_context.exception.details["field"], "page_title")
