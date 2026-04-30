from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser
from typing import Any

from temu_y2_women.errors import GenerationError


SectionRule = tuple[str, str, tuple[str, ...]]

_SECTION_RULES_BY_SOURCE = {
    "vogue-spring-2025-dress-trends": (
        ("The Butter Yellow Dress", "butter-yellow-dress", ("spring", "color")),
        ("The Drop Waist Dress", "drop-waist-dress", ("spring", "silhouette")),
        ("The Polka-Dot Dress", "polka-dot-dress", ("spring", "print")),
        ("Fashion-Forward Florals", "fashion-forward-florals", ("spring", "print")),
    ),
}


def parse_vogue_editorial_html(source: dict[str, Any], html: str, fetched_at: str) -> dict[str, Any]:
    section_rules = _resolve_section_rules(source)
    parser = _VogueHtmlParser(_heading_lookup(section_rules))
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
        "sections": [_section_record(parser, rule) for rule in section_rules],
        "warnings": [],
    }


def _resolve_section_rules(source: dict[str, Any]) -> tuple[SectionRule, ...]:
    configured = _configured_section_rules(source)
    if configured is not None:
        return configured
    source_id = str(source["source_id"])
    try:
        return _SECTION_RULES_BY_SOURCE[source_id]
    except KeyError as error:
        raise ValueError(f"unsupported Vogue source: {source_id}") from error


def _configured_section_rules(source: dict[str, Any]) -> tuple[SectionRule, ...] | None:
    parser_config = source.get("parser_config")
    if not isinstance(parser_config, dict):
        return None
    section_rules = parser_config.get("section_rules")
    if not isinstance(section_rules, list) or not section_rules:
        return None
    return tuple(_configured_section_rule(item) for item in section_rules)


def _configured_section_rule(item: Any) -> SectionRule:
    if not isinstance(item, dict):
        raise ValueError("section rule must be an object")
    tags = tuple(str(tag) for tag in item.get("tags", []))
    if not tags:
        raise ValueError("section rule tags must be non-empty")
    return str(item["heading"]), str(item["section_id"]), tags


def _heading_lookup(section_rules: tuple[SectionRule, ...]) -> dict[str, str]:
    return {_clean_html_text(heading).casefold(): section_id for heading, section_id, _ in section_rules}


def _section_record(parser: "_VogueHtmlParser", rule: SectionRule) -> dict[str, Any]:
    heading, section_id, tags = rule
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


class _VogueHtmlParser(HTMLParser):
    def __init__(self, heading_lookup: dict[str, str]) -> None:
        super().__init__(convert_charrefs=True)
        self._heading_lookup = heading_lookup
        self._title_parts: list[str] = []
        self._h1_parts: list[str] = []
        self._heading_parts: list[str] = []
        self._section_text_parts: dict[str, list[str]] = {}
        self._active_section: str | None = None
        self._current_paragraph_section: str | None = None
        self._captured_at: str | None = None
        self._in_title = False
        self._in_h1 = False
        self._in_h2 = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: value or "" for key, value in attrs}
        if tag == "title":
            self._in_title = True
            return
        if tag == "h1":
            self._in_h1 = True
            return
        if tag == "meta":
            self._capture_published_date(attr_map)
            return
        if tag == "h2":
            self._in_h2 = True
            self._heading_parts = []
            return
        if tag == "p" and self._active_section:
            self._current_paragraph_section = self._active_section

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
            return
        if tag == "h1":
            self._in_h1 = False
            return
        if tag == "h2":
            self._in_h2 = False
            self._active_section = self._resolved_heading_section()
            self._heading_parts = []
            return
        if tag == "p":
            self._current_paragraph_section = None

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_parts.append(data)
        elif self._in_h1:
            self._h1_parts.append(data)
        elif self._in_h2:
            self._heading_parts.append(data)
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
        cleaned = _clean_html_text(" ".join(self._section_text_parts.get(section_id, [])))
        if cleaned:
            return cleaned
        raise _adapter_error("required seasonal sections missing", field="sections", missing_section=section_id)

    def _capture_published_date(self, attrs: dict[str, str]) -> None:
        if attrs.get("property") != "article:published_time":
            return
        content = attrs.get("content", "")
        if re.match(r"\d{4}-\d{2}-\d{2}", content):
            self._captured_at = content[:10]

    def _resolved_heading_section(self) -> str | None:
        heading = _clean_html_text("".join(self._heading_parts)).casefold()
        return self._heading_lookup.get(heading)
