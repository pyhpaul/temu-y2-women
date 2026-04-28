from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any

from temu_y2_women.errors import GenerationError


def parse_whowhatwear_roundup_html(source: dict[str, Any], html: str, fetched_at: str) -> dict[str, Any]:
    parser = _RoundupCardParser()
    parser.feed(html)
    parser.close()
    return {
        "schema_version": "public-roundup-source-snapshot-v1",
        "source_id": source["source_id"],
        "source_type": source["source_type"],
        "source_url": source["source_url"],
        "captured_at": parser.captured_at(),
        "fetched_at": fetched_at,
        "target_market": source["target_market"],
        "category": source["category"],
        "page_title": parser.page_title(),
        "page_context_tags": ["summer", "shopping", "dress"],
        "cards": parser.cards(str(source["source_id"])),
        "warnings": [],
    }


def _adapter_error(message: str, **details: Any) -> GenerationError:
    return GenerationError(code="INVALID_PUBLIC_SOURCE_HTML", message=message, details=details)


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


class _RoundupCardParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._title_parts: list[str] = []
        self._captured_at: str | None = None
        self._cards: list[dict[str, str]] = []
        self._current_card: dict[str, str] | None = None
        self._active_field: str | None = None
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: value or "" for key, value in attrs}
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            self._capture_published_date(attr_map)
        elif tag == "li" and "data-card" in attr_map:
            self._current_card = {"title": "", "image_url": "", "source_url": "", "brand_text": ""}
        elif self._current_card is not None:
            self._update_card_from_tag(tag, attr_map)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag == "li" and self._current_card is not None:
            self._cards.append(dict(self._current_card))
            self._current_card = None
        elif tag in {"a", "span"}:
            self._active_field = None

    def handle_data(self, data: str) -> None:
        text = _clean_text(data)
        if not text:
            return
        if self._in_title:
            self._title_parts.append(text)
        elif self._current_card is not None and self._active_field:
            self._current_card[self._active_field] = text

    def page_title(self) -> str:
        title = _clean_text(" ".join(self._title_parts))
        if title:
            return title
        raise _adapter_error("missing roundup page title", field="page_title")

    def captured_at(self) -> str:
        if self._captured_at:
            return self._captured_at
        raise _adapter_error("missing roundup published date", field="captured_at")

    def cards(self, source_id: str) -> list[dict[str, Any]]:
        if not self._cards:
            raise _adapter_error("missing roundup cards", field="cards")
        return [_card_record(source_id, card, index) for index, card in enumerate(self._cards, start=1)]

    def _capture_published_date(self, attrs: dict[str, str]) -> None:
        if attrs.get("property") != "article:published_time":
            return
        content = attrs.get("content", "")
        if re.match(r"\d{4}-\d{2}-\d{2}", content):
            self._captured_at = content[:10]

    def _update_card_from_tag(self, tag: str, attrs: dict[str, str]) -> None:
        if tag == "a" and "data-card-link" in attrs:
            self._current_card["source_url"] = attrs.get("href", "")
        elif tag == "img":
            self._current_card["image_url"] = attrs.get("src", "")
        elif "data-card-title" in attrs:
            self._active_field = "title"
        elif "data-card-brand" in attrs:
            self._active_field = "brand_text"


def _card_record(source_id: str, card: dict[str, str], index: int) -> dict[str, Any]:
    return {
        "card_id": f"{source_id}-card-{index:03d}",
        "rank": index,
        "title": card["title"],
        "image_url": card["image_url"],
        "source_url": card["source_url"],
        "price_text": "",
        "brand_text": card["brand_text"],
        "badges": [],
    }
