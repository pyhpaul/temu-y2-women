from __future__ import annotations

from collections import defaultdict
from typing import Any


_SEASON_TAGS = {"spring", "summer", "fall", "winter"}
_STRUCTURED_CANDIDATE_SOURCE = "roundup_card_image_aggregation"


def build_roundup_canonical_signals(
    snapshot: dict[str, Any],
    observations: dict[str, Any],
    default_price_band: str,
    aggregation_threshold: int,
) -> dict[str, Any]:
    grouped = _group_observations(observations)
    signals: list[dict[str, Any]] = []
    for index, ((slot, value), cards) in enumerate(_selected_groups(grouped, aggregation_threshold), start=1):
        signals.append(
            _build_signal(
                snapshot=snapshot,
                observations=observations,
                default_price_band=default_price_band,
                aggregation_threshold=aggregation_threshold,
                slot=slot,
                value=value,
                cards=cards,
                index=index,
            )
        )
    return {"schema_version": "canonical-signals-v1", "signals": signals}


def _group_observations(observations: dict[str, Any]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for card in observations["cards"]:
        for slot in card["observed_slots"]:
            grouped[(slot["slot"], slot["value"])].append(card)
    return grouped


def _selected_groups(
    grouped: dict[tuple[str, str], list[dict[str, Any]]],
    aggregation_threshold: int,
) -> list[tuple[tuple[str, str], list[dict[str, Any]]]]:
    selected = []
    for key, cards in grouped.items():
        if len(cards) >= aggregation_threshold:
            selected.append((key, cards))
    return sorted(selected, key=lambda item: item[0])


def _build_signal(
    snapshot: dict[str, Any],
    observations: dict[str, Any],
    default_price_band: str,
    aggregation_threshold: int,
    slot: str,
    value: str,
    cards: list[dict[str, Any]],
    index: int,
) -> dict[str, Any]:
    return {
        "canonical_signal_id": _canonical_signal_id(snapshot["source_id"], slot, value, index),
        "source_id": snapshot["source_id"],
        "source_type": snapshot["source_type"],
        "source_url": snapshot["source_url"],
        "captured_at": snapshot["captured_at"],
        "fetched_at": snapshot["fetched_at"],
        "target_market": snapshot["target_market"],
        "category": snapshot["category"],
        "title": snapshot["page_title"],
        "summary": f"Observed {slot}={value} across {len(cards)} roundup cards.",
        "evidence_excerpt": " | ".join(card["title"] for card in cards[:3]),
        "observed_occasion_tags": [],
        "observed_season_tags": _observed_season_tags(snapshot),
        "manual_tags": list(snapshot["page_context_tags"]),
        "structured_candidates": [_structured_candidate(slot, value, cards, aggregation_threshold, observations)],
        "observed_price_band": default_price_band,
        "price_band_resolution": "source_default",
        "status": "active",
        "extraction_provenance": _provenance(snapshot, observations, aggregation_threshold, slot, value, cards),
    }


def _canonical_signal_id(source_id: str, slot: str, value: str, index: int) -> str:
    return f"{source_id}-{slot}-{value.replace(' ', '-')}-{index:03d}"


def _observed_season_tags(snapshot: dict[str, Any]) -> list[str]:
    return [tag for tag in snapshot["page_context_tags"] if tag in _SEASON_TAGS]


def _provenance(
    snapshot: dict[str, Any],
    observations: dict[str, Any],
    aggregation_threshold: int,
    slot: str,
    value: str,
    cards: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "aggregation_kind": "roundup_card_slot_aggregation",
        "slot": slot,
        "value": value,
        "supporting_card_ids": [card["card_id"] for card in cards],
        "supporting_card_count": len(cards),
        "card_limit": observations["card_limit"],
        "aggregation_threshold": aggregation_threshold,
        "adapter_version": _adapter_version(snapshot, observations),
        "observation_model": observations["observation_model"],
        "warnings": _supporting_warnings(cards),
    }


def _adapter_version(snapshot: dict[str, Any], observations: dict[str, Any]) -> str:
    snapshot_adapter = snapshot.get("adapter_version")
    if isinstance(snapshot_adapter, str) and snapshot_adapter.strip():
        return snapshot_adapter
    snapshot_adapter = observations.get("adapter_version")
    if isinstance(snapshot_adapter, str) and snapshot_adapter.strip():
        return snapshot_adapter
    source_id = str(snapshot.get("source_id", observations.get("source_id", "")))
    if source_id.startswith("harpersbazaar-"):
        return "hearst_roundup_v1"
    return "whowhatwear_roundup_v1"


def _structured_candidate(
    slot: str,
    value: str,
    cards: list[dict[str, Any]],
    aggregation_threshold: int,
    observations: dict[str, Any],
) -> dict[str, Any]:
    return {
        "slot": slot,
        "value": value,
        "candidate_source": _STRUCTURED_CANDIDATE_SOURCE,
        "supporting_card_ids": [card["card_id"] for card in cards],
        "supporting_card_count": len(cards),
        "aggregation_threshold": aggregation_threshold,
        "observation_model": observations["observation_model"],
        "evidence_summary": _candidate_evidence_summary(slot, value, cards),
    }


def _candidate_evidence_summary(slot: str, value: str, cards: list[dict[str, Any]]) -> str:
    snippets = [_card_evidence_fragment(card, slot, value) for card in cards]
    joined = "; ".join(snippet for snippet in snippets if snippet)
    return f"{len(cards)} cards agree on {slot}={value}: {joined}."


def _card_evidence_fragment(card: dict[str, Any], slot: str, value: str) -> str:
    for observed in card.get("observed_slots", []):
        if observed.get("slot") == slot and observed.get("value") == value:
            summary = str(observed.get("evidence_summary", "")).strip()
            if summary:
                return f"{card['title']} ({summary})"
    return str(card["title"])


def _supporting_warnings(cards: list[dict[str, Any]]) -> list[str]:
    warnings: list[str] = []
    for card in cards:
        for warning in card.get("warnings", []):
            if warning not in warnings:
                warnings.append(warning)
    return warnings
