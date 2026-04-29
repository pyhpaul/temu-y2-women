from __future__ import annotations

from datetime import date
from typing import Any

from temu_y2_women.errors import GenerationError
from temu_y2_women.models import NormalizedRequest


def normalize_request(payload: dict[str, Any]) -> NormalizedRequest:
    category = payload.get("category")
    if category != "dress":
        raise GenerationError(
            code="UNSUPPORTED_CATEGORY",
            message="only 'dress' category is supported in the MVP",
            details={"category": category},
        )

    target_market = payload.get("target_market")
    if not isinstance(target_market, str) or not target_market:
        raise GenerationError(
            code="INVALID_REQUEST",
            message="target_market is required",
            details={"field": "target_market"},
        )
    if target_market != "US":
        raise GenerationError(
            code="INVALID_REQUEST",
            message="target_market must be 'US' in the MVP",
            details={"field": "target_market", "target_market": target_market},
        )

    raw_date = payload.get("target_launch_date")
    if not isinstance(raw_date, str):
        raise GenerationError(
            code="INVALID_REQUEST",
            message="target_launch_date is required",
            details={"field": "target_launch_date"},
        )

    try:
        target_launch_date = date.fromisoformat(raw_date)
    except ValueError as exc:
        raise GenerationError(
            code="INVALID_DATE",
            message="target_launch_date must be a valid ISO date",
            details={"target_launch_date": raw_date},
        ) from exc

    mode = payload.get("mode")
    if mode not in {"A", "B"}:
        raise GenerationError(
            code="INVALID_REQUEST",
            message="mode must be 'A' or 'B'",
            details={"field": "mode", "mode": mode},
        )

    return NormalizedRequest(
        category=category,
        target_market=target_market,
        target_launch_date=target_launch_date,
        mode=mode,
        price_band=_optional_string(payload.get("price_band")),
        occasion_tags=_string_tuple(payload.get("occasion_tags")),
        must_have_tags=_string_tuple(payload.get("must_have_tags")),
        avoid_tags=_string_tuple(payload.get("avoid_tags")),
        style_family=_optional_string(payload.get("style_family")),
    )


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise GenerationError(
            code="INVALID_REQUEST",
            message="optional string fields must be non-empty strings",
            details={"value": value},
        )
    return value


def _string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise GenerationError(
            code="INVALID_REQUEST",
            message="list fields must be arrays of strings",
            details={"value": value},
        )

    items: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise GenerationError(
                code="INVALID_REQUEST",
                message="list fields must contain non-empty strings",
                details={"value": value},
            )
        items.append(item)
    return tuple(items)
