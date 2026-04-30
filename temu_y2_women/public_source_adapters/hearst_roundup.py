from __future__ import annotations

import json
import re
from typing import Any

from temu_y2_women.errors import GenerationError


def parse_hearst_roundup_html(source: dict[str, Any], html: str, fetched_at: str) -> dict[str, Any]:
    page_props = _page_props(html)
    page_title = _page_title(page_props, html)
    captured_at = _published_date(html)
    cards = _cards(page_props.get("slides"), str(source["source_id"]))
    return {
        "schema_version": "public-roundup-source-snapshot-v1",
        "source_id": source["source_id"],
        "source_type": source["source_type"],
        "source_url": source["source_url"],
        "captured_at": captured_at,
        "fetched_at": fetched_at,
        "target_market": source["target_market"],
        "category": source["category"],
        "page_title": page_title,
        "page_context_tags": _page_context_tags(source),
        "cards": cards,
        "warnings": [],
    }


def _page_props(html: str) -> dict[str, Any]:
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">\s*(.*?)\s*</script>', html, re.DOTALL)
    if not match:
        return {}
    payload = json.loads(match.group(1))
    return dict(payload.get("props", {}).get("pageProps", {}))


def _page_title(page_props: dict[str, Any], html: str) -> str:
    title = _first_non_empty(page_props.get("titleText"), _capture(r"<title[^>]*>(.*?)</title>", html))
    if title:
        return title
    raise _adapter_error("missing Hearst roundup page title", field="page_title")


def _published_date(html: str) -> str:
    patterns = (
        r'<meta[^>]+(?:property|name)=["\']article:published_time["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']article:published_time["\']',
    )
    for pattern in patterns:
        content = _capture(pattern, html)
        if content and re.match(r"\d{4}-\d{2}-\d{2}", content):
            return content[:10]
    raise _adapter_error("missing Hearst roundup published date", field="captured_at")


def _cards(raw_slides: Any, source_id: str) -> list[dict[str, Any]]:
    slides = raw_slides if isinstance(raw_slides, list) else []
    cards = [_card_record(source_id, slide, index) for index, slide in enumerate(slides, start=1)]
    cards = [card for card in cards if card is not None]
    if cards:
        return cards
    raise _adapter_error("missing Hearst roundup cards", field="cards")


def _card_record(source_id: str, slide: Any, index: int) -> dict[str, Any] | None:
    if not isinstance(slide, dict):
        return None
    offer = _first_offer(slide)
    title = _first_non_empty(slide.get("custom_name"), slide.get("name"))
    image_url = _first_non_empty(_nested_string(slide, "image", "aws_url"), _first_list_item(slide.get("images")))
    source_url = _first_non_empty(offer.get("url"), offer.get("affiliate_url"))
    if not title or not image_url or not source_url:
        return None
    return {
        "card_id": f"{source_id}-card-{index:03d}",
        "rank": index,
        "title": title,
        "image_url": image_url,
        "source_url": source_url,
        "price_text": _price_text(offer),
        "brand_text": _first_non_empty(slide.get("custom_brand"), slide.get("brand"), offer.get("display_name")),
        "badges": _badges(slide),
    }


def _price_text(offer: dict[str, str]) -> str:
    amount = _first_non_empty(offer.get("listprice"), offer.get("price"))
    if not amount:
        return ""
    return f"${amount}" if offer.get("price_currency") == "USD" else amount


def _badges(slide: dict[str, Any]) -> list[str]:
    badge = _first_non_empty(slide.get("label"), _nested_string(slide, "metadata", "custom_tag"))
    return [badge] if badge else []


def _page_context_tags(source: dict[str, Any]) -> list[str]:
    parser_config = source.get("parser_config")
    if isinstance(parser_config, dict):
        tags = parser_config.get("page_context_tags")
        if isinstance(tags, list) and all(isinstance(tag, str) and tag.strip() for tag in tags):
            return [tag.strip() for tag in tags]
    return ["summer", "shopping", str(source["category"])]


def _first_offer(slide: dict[str, Any]) -> dict[str, str]:
    offers = slide.get("offers")
    if isinstance(offers, list) and offers and isinstance(offers[0], dict):
        return {key: str(value) for key, value in offers[0].items() if isinstance(value, (str, int, float))}
    return {}


def _first_non_empty(*values: Any) -> str:
    for value in values:
        if isinstance(value, str):
            cleaned = re.sub(r"\s+", " ", value).strip()
            if cleaned:
                return cleaned
    return ""


def _first_list_item(value: Any) -> str:
    if isinstance(value, list) and value and isinstance(value[0], str):
        return value[0]
    return ""


def _nested_string(record: dict[str, Any], *keys: str) -> str:
    value: Any = record
    for key in keys:
        if not isinstance(value, dict):
            return ""
        value = value.get(key)
    return value if isinstance(value, str) else ""


def _capture(pattern: str, html: str) -> str:
    match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
    return match.group(1) if match else ""


def _adapter_error(message: str, **details: Any) -> GenerationError:
    return GenerationError(code="INVALID_PUBLIC_SOURCE_HTML", message=message, details=details)
