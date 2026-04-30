from __future__ import annotations

import json
import re
from html import unescape
from typing import Any

from temu_y2_women.errors import GenerationError


_ADAPTER_VERSION = "hearst_roundup_v1"


def parse_hearst_roundup_html(source: dict[str, Any], html: str, fetched_at: str) -> dict[str, Any]:
    next_data = _load_next_data(html)
    return {
        "schema_version": "public-roundup-source-snapshot-v1",
        "adapter_version": _ADAPTER_VERSION,
        "source_id": source["source_id"],
        "source_type": source["source_type"],
        "source_url": source["source_url"],
        "captured_at": _published_date(html),
        "fetched_at": fetched_at,
        "target_market": source["target_market"],
        "category": source["category"],
        "page_title": _page_title(html),
        "page_context_tags": ["summer", "shopping", "dress"],
        "cards": _build_cards(str(source["source_id"]), next_data),
        "warnings": [],
    }


def _page_title(html: str) -> str:
    match = re.search(r"<title(?:\s[^>]*)?>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if match:
        title = _clean_text(match.group(1))
        if title:
            return title
    raise _adapter_error("missing roundup page title", field="page_title")


def _published_date(html: str) -> str:
    match = re.search(
        r'<meta[^>]+property="article:published_time"[^>]+content="([^"]+)"',
        html,
        flags=re.IGNORECASE,
    )
    if match and re.match(r"\d{4}-\d{2}-\d{2}", match.group(1)):
        return match.group(1)[:10]
    raise _adapter_error("missing roundup published date", field="captured_at")


def _load_next_data(html: str) -> dict[str, Any]:
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        raise _adapter_error("missing Hearst hydration payload", field="__NEXT_DATA__")
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as error:
        raise _adapter_error("invalid Hearst hydration payload", field="__NEXT_DATA__", error=str(error)) from error


def _build_cards(source_id: str, next_data: dict[str, Any]) -> list[dict[str, Any]]:
    slides = _slides(next_data)
    cards = [_card_record(source_id, slide, index) for index, slide in enumerate(slides, start=1)]
    if cards:
        return cards
    raise _adapter_error("missing roundup cards", field="cards")


def _slides(next_data: dict[str, Any]) -> list[dict[str, Any]]:
    props = next_data.get("props")
    if not isinstance(props, dict):
        return []
    page_props = props.get("pageProps")
    if not isinstance(page_props, dict):
        return []
    slides = page_props.get("slides")
    if not isinstance(slides, list):
        return []
    return [slide for slide in slides if isinstance(slide, dict) and _card_title(slide)]


def _card_record(source_id: str, slide: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "card_id": f"{source_id}-card-{index:03d}",
        "rank": index,
        "title": _card_title(slide),
        "image_url": _image_url(slide),
        "source_url": _source_url(slide),
        "price_text": "",
        "brand_text": _brand_text(slide),
        "badges": [],
    }


def _card_title(slide: dict[str, Any]) -> str:
    metadata = slide.get("metadata")
    if isinstance(metadata, dict):
        title = _clean_text(str(metadata.get("custom_tag", "")))
        if title:
            return title
    return _clean_text(str(slide.get("name", "")))


def _image_url(slide: dict[str, Any]) -> str:
    image = slide.get("image")
    if isinstance(image, dict):
        url = _clean_text(str(image.get("aws_url", "")))
        if url:
            return url
    images = slide.get("images")
    if isinstance(images, list) and images:
        return _clean_text(str(images[0]))
    return ""


def _source_url(slide: dict[str, Any]) -> str:
    offers = slide.get("offers")
    if not isinstance(offers, list) or not offers:
        return ""
    offer = offers[0]
    if not isinstance(offer, dict):
        return ""
    return _clean_text(str(offer.get("url", "")))


def _brand_text(slide: dict[str, Any]) -> str:
    return _clean_text(str(slide.get("brand") or slide.get("custom_brand") or ""))


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(value)).strip()


def _adapter_error(message: str, **details: Any) -> GenerationError:
    return GenerationError(code="INVALID_PUBLIC_SOURCE_HTML", message=message, details=details)
