from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser
from typing import Any

from temu_y2_women.errors import GenerationError


def _rule(
    section_id: str,
    heading: str,
    tags: list[str],
    confidence: float,
    excerpt_anchor: str,
    matched_keywords: list[str],
) -> dict[str, Any]:
    return {
        "section_id": section_id,
        "heading": heading,
        "tags": tags,
        "adapter_version": "marieclaire_editorial_v1",
        "confidence": confidence,
        "excerpt_anchor": excerpt_anchor,
        "matched_keywords": matched_keywords,
    }


_SECTION_RULES = (
    _rule("smocked-dresses", "Smocked Dresses", ["summer"], 0.79, "smocked dresses", ["smocked bodices", "cotton poplin"]),
    _rule("polka-dot-dresses", "Polka Dot Dresses", ["summer"], 0.68, "polka dot dresses", ["polka dots"]),
    _rule("boho-dresses", "Boho Dresses", ["summer"], 0.73, "flutter sleeves", ["flutter sleeves", "floral"]),
    _rule("gingham-dresses", "Gingham Dresses", ["summer"], 0.71, "a-line", ["a-line", "cotton poplin"]),
    _rule("babydoll-dresses", "Babydoll Dresses", ["summer"], 0.67, "square neckline", ["square neckline"]),
)


def parse_marieclaire_editorial_html(source: dict[str, Any], html: str, fetched_at: str) -> dict[str, Any]:
    parser = _MarieClaireHtmlParser(_section_ids())
    parser.feed(html)
    parser.close()
    return {
        "schema_version": "public-source-snapshot-v1",
        "source_id": source["source_id"],
        "source_url": source["source_url"],
        "source_type": source["source_type"],
        "target_market": source["target_market"],
        "category": source["category"],
        "captured_at": parser.captured_at(),
        "fetched_at": fetched_at,
        "page_title": parser.page_title(),
        "sections": [_build_section_record(parser, rule) for rule in _SECTION_RULES],
        "warnings": [],
    }


def _section_ids() -> set[str]:
    return {str(rule["section_id"]) for rule in _SECTION_RULES}


def _build_section_record(parser: "_MarieClaireHtmlParser", rule: dict[str, Any]) -> dict[str, Any]:
    return {
        "section_id": rule["section_id"],
        "heading": rule["heading"],
        "text": parser.section_text(str(rule["section_id"])),
        "tags": list(rule["tags"]),
        "adapter_version": rule["adapter_version"],
        "confidence": rule["confidence"],
        "excerpt_anchor": rule["excerpt_anchor"],
        "matched_keywords": list(rule["matched_keywords"]),
    }


def _clean_html_text(value: str) -> str:
    text = unescape(value)
    return re.sub(r"\s+", " ", text).strip()


def _adapter_error(message: str, **details: Any) -> GenerationError:
    return GenerationError(code="INVALID_PUBLIC_SOURCE_HTML", message=message, details=details)


class _MarieClaireHtmlParser(HTMLParser):
    def __init__(self, section_ids: set[str]) -> None:
        super().__init__(convert_charrefs=True)
        self._section_ids = section_ids
        self._title_parts: list[str] = []
        self._h1_parts: list[str] = []
        self._section_text_parts: dict[str, list[str]] = {}
        self._captured_at: str | None = None
        self._in_title = False
        self._in_h1 = False
        self._active_section: str | None = None
        self._current_paragraph_section: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: value or "" for key, value in attrs}
        if tag == "title":
            self._in_title = True
        elif tag == "h1":
            self._in_h1 = True
        elif tag == "meta":
            self._capture_published_date(attr_map)
        elif tag == "h2":
            self._active_section = _section_id_from_html_id(attr_map.get("id", ""), self._section_ids)
        elif tag == "p":
            self._start_section_paragraph()

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag == "h1":
            self._in_h1 = False
        elif tag == "p":
            self._active_section = None
            self._current_paragraph_section = None

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_parts.append(data)
        elif self._in_h1:
            self._h1_parts.append(data)
        elif self._current_paragraph_section:
            self._section_text_parts.setdefault(self._current_paragraph_section, []).append(data)

    def page_title(self) -> str:
        for candidate in ("".join(self._h1_parts), "".join(self._title_parts)):
            cleaned = _clean_html_text(candidate)
            if cleaned:
                return cleaned
        raise _adapter_error("missing page title", field="page_title")

    def captured_at(self) -> str:
        if self._captured_at:
            return self._captured_at
        raise _adapter_error("missing published date", field="captured_at")

    def section_text(self, section_id: str) -> str:
        cleaned = _clean_html_text("".join(self._section_text_parts.get(section_id, [])))
        if cleaned:
            return cleaned
        raise _adapter_error("required seasonal sections missing", field="sections", missing_section=section_id)

    def _capture_published_date(self, attrs: dict[str, str]) -> None:
        if attrs.get("property") != "article:published_time":
            return
        content = attrs.get("content", "")
        if re.match(r"\d{4}-\d{2}-\d{2}", content):
            self._captured_at = content[:10]

    def _start_section_paragraph(self) -> None:
        if not self._active_section or self._active_section in self._section_text_parts:
            return
        self._current_paragraph_section = self._active_section


def _section_id_from_html_id(value: str, section_ids: set[str]) -> str | None:
    if value in section_ids:
        return value
    for section_id in section_ids:
        if value.endswith(section_id):
            return section_id
    return None
