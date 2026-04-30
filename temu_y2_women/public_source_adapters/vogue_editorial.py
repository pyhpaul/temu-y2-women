from __future__ import annotations

import json
import re
from html import unescape
from html.parser import HTMLParser
from typing import Any

from temu_y2_women.errors import GenerationError


_EXCLUDED_HEADINGS = (
    "featured in this article",
    "shop more dresses from vogue shopping",
)
_SECTION_TEXT_MARKER = "Ahead is Vogue's edit of the best dresses inspired by the Spring Summer 2025 trends."
_STOPWORDS = {"the", "a", "an", "and", "of", "dress", "dresses"}


def parse_vogue_editorial_html(source: dict[str, Any], html: str, fetched_at: str) -> dict[str, Any]:
    parser = _VogueHtmlParser()
    parser.feed(html)
    parser.close()
    headings = _trend_headings(parser.h2_headings())
    texts = _section_texts(parser.article_body_paragraphs(), len(headings))
    sections = [_build_section_record(heading, text) for heading, text in zip(headings, texts, strict=True)]
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


def _build_section_record(heading: str, text: str) -> dict[str, Any]:
    return {
        "section_id": _section_id(heading),
        "heading": heading,
        "text": text,
        "tags": _section_tags(heading),
    }


def _trend_headings(headings: list[str]) -> list[str]:
    filtered = [heading for heading in headings if heading.lower() not in _EXCLUDED_HEADINGS]
    if filtered:
        return filtered
    raise _adapter_error("required editorial sections missing", field="sections")


def _section_texts(paragraphs: list[str], expected_count: int) -> list[str]:
    if expected_count == 0:
        raise _adapter_error("required editorial sections missing", field="sections")
    start = _section_start_index(paragraphs)
    if start >= 0:
        texts = paragraphs[start + 1 : start + 1 + expected_count]
    else:
        texts = paragraphs[-expected_count:]
    if len(texts) != expected_count or any(not text for text in texts):
        raise _adapter_error("required editorial sections missing", field="sections")
    return texts


def _section_start_index(paragraphs: list[str]) -> int:
    for index, paragraph in enumerate(paragraphs):
        if paragraph == _SECTION_TEXT_MARKER:
            return index
    return -1


def _section_tags(heading: str) -> list[str]:
    tags = ["spring", "summer"]
    for token in _slugify(heading).split("-"):
        if token and token not in _STOPWORDS and token not in tags:
            tags.append(token)
    return tags


def _section_id(heading: str) -> str:
    return re.sub(r"^the-", "", _slugify(heading))


def _slugify(value: str) -> str:
    lowered = _clean_html_text(value).lower().replace("'", "")
    return re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9]+", "-", lowered)).strip("-")


def _clean_html_text(value: str) -> str:
    text = unescape(value)
    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u00e0": "a",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return re.sub(r"\s+", " ", text).strip()


def _adapter_error(message: str, **details: Any) -> GenerationError:
    return GenerationError(code="INVALID_PUBLIC_SOURCE_HTML", message=message, details=details)


class _VogueHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._title_parts: list[str] = []
        self._h1_parts: list[str] = []
        self._h2_parts: list[str] = []
        self._current_script: list[str] = []
        self._headings: list[str] = []
        self._article_body = ""
        self._captured_at: str | None = None
        self._in_title = False
        self._in_h1 = False
        self._in_h2 = False
        self._in_ld_json = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: value or "" for key, value in attrs}
        if tag == "title":
            self._in_title = True
        elif tag == "h1":
            self._in_h1 = True
        elif tag == "h2":
            self._in_h2 = True
            self._h2_parts = []
        elif tag == "meta":
            self._capture_published_date(attr_map.get("property", ""), attr_map.get("content", ""))
        elif tag == "script" and attr_map.get("type") == "application/ld+json":
            self._in_ld_json = True
            self._current_script = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag == "h1":
            self._in_h1 = False
        elif tag == "h2":
            self._in_h2 = False
            heading = _clean_html_text("".join(self._h2_parts))
            if heading:
                self._headings.append(heading)
        elif tag == "script" and self._in_ld_json:
            self._in_ld_json = False
            self._capture_ld_json("".join(self._current_script))

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_parts.append(data)
        elif self._in_h1:
            self._h1_parts.append(data)
        elif self._in_h2:
            self._h2_parts.append(data)
        elif self._in_ld_json:
            self._current_script.append(data)

    def page_title(self) -> str:
        for candidate in ("".join(self._h1_parts), "".join(self._title_parts)):
            cleaned = _clean_html_text(candidate).removesuffix(" | Vogue")
            if cleaned:
                return cleaned
        raise _adapter_error("missing page title", field="page_title")

    def captured_at(self) -> str:
        if self._captured_at:
            return self._captured_at
        raise _adapter_error("missing published date", field="captured_at")

    def h2_headings(self) -> list[str]:
        return list(self._headings)

    def article_body_paragraphs(self) -> list[str]:
        paragraphs = [_clean_html_text(item) for item in self._article_body.splitlines()]
        return [item for item in paragraphs if item]

    def _capture_published_date(self, property_name: str, content: str) -> None:
        if property_name == "article:published_time":
            self._set_captured_at(content)

    def _capture_ld_json(self, raw_json: str) -> None:
        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError:
            return
        for item in _json_items(payload):
            if item.get("@type") != "NewsArticle":
                continue
            self._article_body = self._article_body or str(item.get("articleBody", ""))
            self._set_captured_at(str(item.get("datePublished", "")))

    def _set_captured_at(self, value: str) -> None:
        if self._captured_at or not re.match(r"\d{4}-\d{2}-\d{2}", value):
            return
        self._captured_at = value[:10]


def _json_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        graph = payload.get("@graph")
        if isinstance(graph, list):
            return [item for item in graph if isinstance(item, dict)]
        return [payload]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []
