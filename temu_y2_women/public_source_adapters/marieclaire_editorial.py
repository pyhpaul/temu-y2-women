from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser
from typing import Any

from temu_y2_women.errors import GenerationError


_SECTION_RULES_BY_SOURCE = {
    "marieclaire-summer-2025-dress-trends": (
        ("linen-dresses-3", "linen-dresses", "Linen Dresses", ("summer",)),
        ("smocked-dresses-3", "smocked-dresses", "Smocked Dresses", ("summer",)),
        ("chocolate-brown-dresses-3", "chocolate-brown-dresses", "Chocolate Brown Dresses", ("summer",)),
        ("polka-dot-dresses-3", "polka-dot-dresses", "Polka Dot Dresses", ("summer",)),
        ("gingham-dresses-3", "gingham-dresses", "Gingham Dresses", ("summer",)),
        ("boho-dresses-3", "boho-dresses", "Boho Dresses", ("summer",)),
        ("babydoll-dresses-3", "babydoll-dresses", "Babydoll Dresses", ("summer",)),
    ),
    "marieclaire-spring-2026-dress-trends": (
        ("section-crinkle-texture-dresses", "crinkle-texture-dresses", "Crinkle Texture Dresses", ("spring",)),
        ("section-drop-waist-dresses", "drop-waist-dresses", "Drop-Waist Dresses", ("spring",)),
        ("section-shirt-dresses", "shirt-dresses", "Shirt Dresses", ("spring",)),
        ("section-fringe-dresses", "fringe-dresses", "Fringe Dresses", ("spring",)),
        ("section-lace-trimmed-dresses", "lace-trimmed-dresses", "Lace-Trimmed Dresses", ("spring",)),
        ("section-voluminous-dresses", "voluminous-dresses", "Voluminous Dresses", ("spring",)),
        ("section-shift-dresses", "shift-dresses", "Shift Dresses", ("spring",)),
        ("section-cape-dresses", "cape-dresses", "Cape Dresses", ("spring",)),
    ),
}


def parse_marieclaire_editorial_html(source: dict[str, Any], html: str, fetched_at: str) -> dict[str, Any]:
    section_rules = _resolve_section_rules(str(source["source_id"]))
    parser = _MarieClaireHtmlParser(_html_section_ids(section_rules))
    parser.feed(html)
    parser.close()
    sections = [
        _build_section_record(parser, section_id, heading, tags)
        for _, section_id, heading, tags in section_rules
    ]
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
        "sections": sections,
        "warnings": [],
    }


def _resolve_section_rules(source_id: str) -> tuple[tuple[str, str, str, tuple[str, ...]], ...]:
    try:
        return _SECTION_RULES_BY_SOURCE[source_id]
    except KeyError as error:
        raise ValueError(f"unsupported Marie Claire source: {source_id}") from error


def _html_section_ids(
    section_rules: tuple[tuple[str, str, str, tuple[str, ...]], ...],
) -> dict[str, str]:
    return {html_id: section_id for html_id, section_id, _, _ in section_rules}


def _build_section_record(
    parser: "_MarieClaireHtmlParser",
    section_id: str,
    heading: str,
    tags: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "section_id": section_id,
        "heading": heading,
        "text": parser.section_text(section_id),
        "tags": list(tags),
    }


def _clean_html_text(value: str) -> str:
    text = unescape(value)
    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return re.sub(r"\s+", " ", text).strip()


def _adapter_error(message: str, **details: Any) -> GenerationError:
    return GenerationError(code="INVALID_PUBLIC_SOURCE_HTML", message=message, details=details)


class _MarieClaireHtmlParser(HTMLParser):
    def __init__(self, html_section_ids: dict[str, str]) -> None:
        super().__init__(convert_charrefs=True)
        self._html_section_ids = html_section_ids
        self._title_parts: list[str] = []
        self._h1_parts: list[str] = []
        self._in_title = False
        self._in_h1 = False
        self._active_section: str | None = None
        self._current_paragraph_section: str | None = None
        self._captured_at: str | None = None
        self._section_text_parts: dict[str, list[str]] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: value or "" for key, value in attrs}
        if tag == "title":
            self._in_title = True
        elif tag == "h1":
            self._in_h1 = True
        elif tag == "meta":
            self._capture_published_date(attr_map)
        elif tag in {"h2", "h3"}:
            self._active_section = self._html_section_ids.get(attr_map.get("id", ""))
        elif tag == "p":
            self._start_section_paragraph(attr_map)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag == "h1":
            self._in_h1 = False
        elif tag in {"h2", "h3"}:
            return
        elif tag == "p" and self._current_paragraph_section:
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
        raise _adapter_error(
            "required seasonal sections missing",
            field="sections",
            missing_section=section_id,
        )

    def _capture_published_date(self, attrs: dict[str, str]) -> None:
        if attrs.get("property") != "article:published_time":
            return
        content = attrs.get("content", "")
        if re.match(r"\d{4}-\d{2}-\d{2}", content):
            self._captured_at = content[:10]

    def _start_section_paragraph(self, attrs: dict[str, str]) -> None:
        if not self._active_section or not attrs.get("id"):
            return
        if self._active_section in self._section_text_parts:
            return
        self._current_paragraph_section = self._active_section
