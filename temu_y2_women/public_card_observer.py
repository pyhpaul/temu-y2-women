from __future__ import annotations

from typing import Any, Callable

from temu_y2_women.errors import GenerationError


CardObserver = Callable[[dict[str, Any]], dict[str, Any]]
_ALLOWED_SLOTS = {
    "silhouette",
    "neckline",
    "sleeve",
    "dress_length",
    "pattern",
    "color_family",
    "waistline",
    "print_scale",
    "opacity_level",
    "detail",
}


def observe_roundup_cards(
    snapshot: dict[str, Any],
    observation_model: str,
    observe_card: CardObserver,
    card_limit: int,
) -> dict[str, Any]:
    cards = list(snapshot["cards"])[:card_limit]
    return {
        "schema_version": "public-card-observations-v1",
        "source_id": snapshot["source_id"],
        "source_url": snapshot["source_url"],
        "fetched_at": snapshot["fetched_at"],
        "observation_model": observation_model,
        "card_limit": card_limit,
        "cards": [_observe_single_card(card, observe_card) for card in cards],
    }


def _observe_single_card(card: dict[str, Any], observe_card: CardObserver) -> dict[str, Any]:
    payload = observe_card(card)
    observed_slots = _normalized_observed_slots(payload)
    abstained_slots = _normalized_abstained_slots(payload)
    if not observed_slots and not abstained_slots:
        raise GenerationError(
            code="INVALID_PUBLIC_CARD_OBSERVATION",
            message="observer returned no usable slots",
            details={"card_id": card["card_id"]},
        )
    return {
        **_base_card_payload(card),
        "observed_slots": observed_slots,
        "abstained_slots": abstained_slots,
        "warnings": [str(item) for item in payload.get("warnings", [])],
    }


def _base_card_payload(card: dict[str, Any]) -> dict[str, Any]:
    return {
        "card_id": card["card_id"],
        "rank": card["rank"],
        "title": card["title"],
        "image_url": card["image_url"],
        "source_url": card["source_url"],
    }


def _normalized_observed_slots(payload: dict[str, Any]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for item in payload.get("observed_slots", []):
        slot = str(item["slot"])
        if slot not in _ALLOWED_SLOTS:
            continue
        normalized.append(
            {
                "slot": slot,
                "value": str(item["value"]),
                "evidence_summary": str(item["evidence_summary"]),
            }
        )
    return normalized


def _normalized_abstained_slots(payload: dict[str, Any]) -> list[str]:
    return [str(slot) for slot in payload.get("abstained_slots", []) if str(slot) in _ALLOWED_SLOTS]
