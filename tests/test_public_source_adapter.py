from __future__ import annotations

import json
from pathlib import Path
import unittest

from temu_y2_women.errors import GenerationError


_FIXTURE_DIR = Path("tests/fixtures/public_sources/dress")


class PublicSourceAdapterTest(unittest.TestCase):
    def test_resolve_public_source_adapter_returns_whowhatwear_parser(self) -> None:
        from temu_y2_women.public_source_adapter import resolve_public_source_adapter
        from temu_y2_women.public_source_adapters.whowhatwear_editorial import parse_whowhatwear_editorial_html

        self.assertIs(resolve_public_source_adapter("whowhatwear_editorial_v1"), parse_whowhatwear_editorial_html)

    def test_resolve_public_source_adapter_returns_marieclaire_parser(self) -> None:
        from temu_y2_women.public_source_adapter import resolve_public_source_adapter
        from temu_y2_women.public_source_adapters.marieclaire_editorial import parse_marieclaire_editorial_html

        self.assertIs(resolve_public_source_adapter("marieclaire_editorial_v1"), parse_marieclaire_editorial_html)

    def test_resolve_public_source_adapter_rejects_unknown_adapter_id(self) -> None:
        from temu_y2_women.public_source_adapter import resolve_public_source_adapter

        with self.assertRaisesRegex(ValueError, "unsupported public source adapter"):
            resolve_public_source_adapter("unknown_adapter")

    def test_parse_whowhatwear_editorial_html_returns_expected_snapshot(self) -> None:
        from temu_y2_women.public_source_adapters.whowhatwear_editorial import parse_whowhatwear_editorial_html

        html = (_FIXTURE_DIR / "whowhatwear-summer-2025-dress-trends.html").read_text(encoding="utf-8")
        source = {
            "source_id": "whowhatwear-summer-2025-dress-trends",
            "source_type": "public_editorial_web",
            "source_url": "https://www.whowhatwear.com/fashion/summer/summer-2025-dress-trends",
            "target_market": "US",
            "category": "dress",
        }

        result = parse_whowhatwear_editorial_html(
            source=source,
            html=html,
            fetched_at="2026-04-28T00:00:00Z",
        )

        expected = json.loads(
            (_FIXTURE_DIR / "expected-whowhatwear-raw-source-snapshot.json").read_text(encoding="utf-8")
        )
        self.assertEqual(result, expected)

    def test_parse_second_whowhatwear_editorial_html_returns_expected_snapshot(self) -> None:
        from temu_y2_women.public_source_adapters.whowhatwear_editorial import parse_whowhatwear_editorial_html

        html = (_FIXTURE_DIR / "whowhatwear-summer-dress-trends-2025.html").read_text(encoding="utf-8")
        source = {
            "source_id": "whowhatwear-summer-dress-trends-2025",
            "source_type": "public_editorial_web",
            "source_url": "https://www.whowhatwear.com/fashion/dresses/summer-dress-trends-2025",
            "target_market": "US",
            "category": "dress",
        }

        result = parse_whowhatwear_editorial_html(source=source, html=html, fetched_at="2026-04-28T00:00:00Z")

        expected = json.loads(
            (_FIXTURE_DIR / "expected-whowhatwear-summer-dress-trends-2025-raw-source-snapshot.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(result, expected)

    def test_parse_marieclaire_editorial_html_returns_expected_snapshot(self) -> None:
        from temu_y2_women.public_source_adapters.marieclaire_editorial import parse_marieclaire_editorial_html

        html = (_FIXTURE_DIR / "marieclaire-summer-2025-dress-trends.html").read_text(encoding="utf-8")
        source = {
            "source_id": "marieclaire-summer-2025-dress-trends",
            "source_type": "public_editorial_web",
            "source_url": "https://www.marieclaire.com/fashion/summer-fashion/summer-2025-dress-trends/",
            "target_market": "US",
            "category": "dress",
        }

        result = parse_marieclaire_editorial_html(source=source, html=html, fetched_at="2026-04-28T00:00:00Z")

        expected = json.loads((_FIXTURE_DIR / "expected-marieclaire-raw-source-snapshot.json").read_text(encoding="utf-8"))
        self.assertEqual(result, expected)

    def test_parse_whowhatwear_editorial_html_rejects_missing_sections(self) -> None:
        from temu_y2_women.public_source_adapters.whowhatwear_editorial import parse_whowhatwear_editorial_html

        with self.assertRaises(GenerationError) as error:
            parse_whowhatwear_editorial_html(
                source={
                    "source_id": "whowhatwear-summer-2025-dress-trends",
                    "source_type": "public_editorial_web",
                    "source_url": "https://www.whowhatwear.com/fashion/summer/summer-2025-dress-trends",
                    "target_market": "US",
                    "category": "dress",
                },
                html=(
                    '<html><head><meta property="article:published_time" content="2025-06-18T07:00:00Z"></head>'
                    "<body><h1>broken</h1></body></html>"
                ),
                fetched_at="2026-04-28T00:00:00Z",
            )
        self.assertEqual(error.exception.code, "INVALID_PUBLIC_SOURCE_HTML")
        self.assertEqual(error.exception.details["field"], "sections")

    def test_parse_whowhatwear_editorial_html_rejects_missing_page_title(self) -> None:
        from temu_y2_women.public_source_adapters.whowhatwear_editorial import parse_whowhatwear_editorial_html

        html = '<html><head><meta property="article:published_time" content="2025-06-18T07:00:00Z"></head><body></body></html>'

        with self.assertRaises(GenerationError) as error:
            parse_whowhatwear_editorial_html(
                source={
                    "source_id": "whowhatwear-summer-2025-dress-trends",
                    "source_type": "public_editorial_web",
                    "source_url": "https://www.whowhatwear.com/fashion/summer/summer-2025-dress-trends",
                    "target_market": "US",
                    "category": "dress",
                },
                html=html,
                fetched_at="2026-04-28T00:00:00Z",
            )
        self.assertEqual(error.exception.code, "INVALID_PUBLIC_SOURCE_HTML")
        self.assertEqual(error.exception.details["field"], "page_title")

    def test_parse_whowhatwear_editorial_html_rejects_missing_published_date(self) -> None:
        from temu_y2_women.public_source_adapters.whowhatwear_editorial import parse_whowhatwear_editorial_html

        html = "<html><body><h1>People With Cool Style Are All Wearing These 11 Dress Trends This Summer</h1></body></html>"

        with self.assertRaises(GenerationError) as error:
            parse_whowhatwear_editorial_html(
                source={
                    "source_id": "whowhatwear-summer-2025-dress-trends",
                    "source_type": "public_editorial_web",
                    "source_url": "https://www.whowhatwear.com/fashion/summer/summer-2025-dress-trends",
                    "target_market": "US",
                    "category": "dress",
                },
                html=html,
                fetched_at="2026-04-28T00:00:00Z",
            )
        self.assertEqual(error.exception.code, "INVALID_PUBLIC_SOURCE_HTML")
        self.assertEqual(error.exception.details["field"], "captured_at")

    def test_parse_whowhatwear_editorial_html_accepts_reordered_published_date_attributes(self) -> None:
        from temu_y2_women.public_source_adapters.whowhatwear_editorial import parse_whowhatwear_editorial_html

        html = (
            '<html><head><meta content="2025-06-18T07:00:00Z" property="article:published_time"></head>'
            "<body>"
            '<h1>People With Cool Style Are All Wearing These 11 Dress Trends This Summer</h1>'
            '<a id="elk-1-the-vacation-mini"></a><h2 id="section-1-the-vacation-mini"><span>1. The Vacation Mini</span></h2><p id="p1">Vacation mini text.</p>'
            '<a id="elk-3-fairy-sleeves"></a><h2 id="section-3-fairy-sleeves"><span>3. Fairy Sleeves</span></h2><p id="p2">Fairy sleeves text.</p>'
            '<a id="elk-5-all-things-polka-dots"></a><h2 id="section-5-all-things-polka-dots"><span>5. All Things Polka Dots</span></h2><p id="p3">Polka dots text.</p>'
            '<a id="elk-10-the-exaggerated-drop-waist"></a><h2 id="section-10-the-exaggerated-drop-waist"><span>10. The Exaggerated Drop Waist</span></h2><p id="p4">Drop waist text.</p>'
            '<a id="elk-11-sheer-printed-midis"></a><h2 id="section-11-sheer-printed-midis"><span>11. Sheer Printed Midis</span></h2><p id="p5">Sheer printed midis text.</p>'
            "</body></html>"
        )

        result = parse_whowhatwear_editorial_html(
            source={
                "source_id": "whowhatwear-summer-2025-dress-trends",
                "source_type": "public_editorial_web",
                "source_url": "https://www.whowhatwear.com/fashion/summer/summer-2025-dress-trends",
                "target_market": "US",
                "category": "dress",
            },
            html=html,
            fetched_at="2026-04-28T00:00:00Z",
        )

        self.assertEqual(result["captured_at"], "2025-06-18")

    def test_parse_whowhatwear_editorial_html_accepts_single_quoted_published_date_meta(self) -> None:
        from temu_y2_women.public_source_adapters.whowhatwear_editorial import parse_whowhatwear_editorial_html

        html = (
            "<html><head><meta content='2025-06-18T07:00:00Z' property='article:published_time'></head>"
            "<body>"
            '<h1>People With Cool Style Are All Wearing These 11 Dress Trends This Summer</h1>'
            '<a id="elk-1-the-vacation-mini"></a><h2 id="section-1-the-vacation-mini"><span>1. The Vacation Mini</span></h2><p id="p1">Vacation mini text.</p>'
            '<a id="elk-3-fairy-sleeves"></a><h2 id="section-3-fairy-sleeves"><span>3. Fairy Sleeves</span></h2><p id="p2">Fairy sleeves text.</p>'
            '<a id="elk-5-all-things-polka-dots"></a><h2 id="section-5-all-things-polka-dots"><span>5. All Things Polka Dots</span></h2><p id="p3">Polka dots text.</p>'
            '<a id="elk-10-the-exaggerated-drop-waist"></a><h2 id="section-10-the-exaggerated-drop-waist"><span>10. The Exaggerated Drop Waist</span></h2><p id="p4">Drop waist text.</p>'
            '<a id="elk-11-sheer-printed-midis"></a><h2 id="section-11-sheer-printed-midis"><span>11. Sheer Printed Midis</span></h2><p id="p5">Sheer printed midis text.</p>'
            "</body></html>"
        )

        result = parse_whowhatwear_editorial_html(
            source={
                "source_id": "whowhatwear-summer-2025-dress-trends",
                "source_type": "public_editorial_web",
                "source_url": "https://www.whowhatwear.com/fashion/summer/summer-2025-dress-trends",
                "target_market": "US",
                "category": "dress",
            },
            html=html,
            fetched_at="2026-04-28T00:00:00Z",
        )

        self.assertEqual(result["captured_at"], "2025-06-18")

    def test_parse_whowhatwear_editorial_html_uses_title_tag_when_h1_missing(self) -> None:
        from temu_y2_women.public_source_adapters.whowhatwear_editorial import parse_whowhatwear_editorial_html

        html = (
            '<html><head><title>Fallback Dress Trends Title</title>'
            '<meta property="article:published_time" content="2025-06-18T07:00:00Z"></head>'
            "<body>"
            '<a id="elk-1-the-vacation-mini"></a><h2 id="section-1-the-vacation-mini"><span>1. The Vacation Mini</span></h2><p id="p1">Vacation mini text.</p>'
            '<a id="elk-3-fairy-sleeves"></a><h2 id="section-3-fairy-sleeves"><span>3. Fairy Sleeves</span></h2><p id="p2">Fairy sleeves text.</p>'
            '<a id="elk-5-all-things-polka-dots"></a><h2 id="section-5-all-things-polka-dots"><span>5. All Things Polka Dots</span></h2><p id="p3">Polka dots text.</p>'
            '<a id="elk-10-the-exaggerated-drop-waist"></a><h2 id="section-10-the-exaggerated-drop-waist"><span>10. The Exaggerated Drop Waist</span></h2><p id="p4">Drop waist text.</p>'
            '<a id="elk-11-sheer-printed-midis"></a><h2 id="section-11-sheer-printed-midis"><span>11. Sheer Printed Midis</span></h2><p id="p5">Sheer printed midis text.</p>'
            "</body></html>"
        )

        result = parse_whowhatwear_editorial_html(
            source={
                "source_id": "whowhatwear-summer-2025-dress-trends",
                "source_type": "public_editorial_web",
                "source_url": "https://www.whowhatwear.com/fashion/summer/summer-2025-dress-trends",
                "target_market": "US",
                "category": "dress",
            },
            html=html,
            fetched_at="2026-04-28T00:00:00Z",
        )

        self.assertEqual(result["page_title"], "Fallback Dress Trends Title")

    def test_parse_whowhatwear_editorial_html_rejects_section_without_body_paragraph(self) -> None:
        from temu_y2_women.public_source_adapters.whowhatwear_editorial import parse_whowhatwear_editorial_html

        html = (
            '<html><head><meta property="article:published_time" content="2025-06-18T07:00:00Z"></head>'
            "<body>"
            '<h1>People With Cool Style Are All Wearing These 11 Dress Trends This Summer</h1>'
            '<a id="elk-1-the-vacation-mini"></a><h2 id="section-1-the-vacation-mini"><span>1. The Vacation Mini</span></h2>'
            '<a id="elk-3-fairy-sleeves"></a><h2 id="section-3-fairy-sleeves"><span>3. Fairy Sleeves</span></h2><p id="p2">Fairy sleeves text.</p>'
            '<a id="elk-5-all-things-polka-dots"></a><h2 id="section-5-all-things-polka-dots"><span>5. All Things Polka Dots</span></h2><p id="p3">Polka dots text.</p>'
            '<a id="elk-10-the-exaggerated-drop-waist"></a><h2 id="section-10-the-exaggerated-drop-waist"><span>10. The Exaggerated Drop Waist</span></h2><p id="p4">Drop waist text.</p>'
            '<a id="elk-11-sheer-printed-midis"></a><h2 id="section-11-sheer-printed-midis"><span>11. Sheer Printed Midis</span></h2><p id="p5">Sheer printed midis text.</p>'
            "</body></html>"
        )

        with self.assertRaises(GenerationError) as error:
            parse_whowhatwear_editorial_html(
                source={
                    "source_id": "whowhatwear-summer-2025-dress-trends",
                    "source_type": "public_editorial_web",
                    "source_url": "https://www.whowhatwear.com/fashion/summer/summer-2025-dress-trends",
                    "target_market": "US",
                    "category": "dress",
                },
                html=html,
                fetched_at="2026-04-28T00:00:00Z",
            )

        self.assertEqual(error.exception.code, "INVALID_PUBLIC_SOURCE_HTML")
        self.assertEqual(error.exception.details["field"], "sections")
        self.assertEqual(error.exception.details["missing_section"], "the-vacation-mini")
