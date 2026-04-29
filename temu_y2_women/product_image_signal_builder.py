from __future__ import annotations

from typing import Any


def build_product_image_signal_bundle(
    manifest: dict[str, Any],
    observations: dict[str, Any],
    observed_at: str,
) -> dict[str, Any]:
    observed_products = _observed_products(observations)
    signals = [
        _signal_record(product, observed_products[str(product["product_id"])], observed_at, observations["observation_model"])
        for product in manifest["products"]
    ]
    return {"schema_version": "signal-bundle-v1", "signals": signals}


def _observed_products(observations: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(product["product_id"]): product for product in observations["products"]}


def _signal_record(
    product: dict[str, Any],
    observed_product: dict[str, Any],
    observed_at: str,
    observation_model: str,
) -> dict[str, Any]:
    return {
        "signal_id": f"product-image-{product['product_id']}",
        "source_type": "product_image_input",
        "source_url": str(product["source_url"]),
        "captured_at": observed_at,
        "target_market": "US",
        "category": "dress",
        "title": f"Product image observation for {product['product_id']}",
        "summary": f"Structured candidates aggregated from {len(observed_product['images'])} submitted product images.",
        "observed_price_band": str(product["price_band"]),
        "observed_occasion_tags": sorted(set(str(item) for item in product["occasion_tags"])),
        "observed_season_tags": sorted(set(str(item) for item in product["season_tags"])),
        "manual_tags": sorted(set(str(item) for item in product["manual_tags"])),
        "status": "active",
        "structured_candidates": _structured_candidates(observed_product["images"], observation_model),
        "extraction_provenance": _extraction_provenance(product["product_id"], observed_product["images"], observation_model),
    }


def _structured_candidates(images: list[dict[str, Any]], observation_model: str) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], set[str]] = {}
    for image in images:
        for observed in image["observed_slots"]:
            key = (str(observed["slot"]), _normalized_value(str(observed["value"])))
            grouped.setdefault(key, set()).add(str(image["image_id"]))
    return [_structured_candidate(slot, value, image_ids, observation_model) for (slot, value), image_ids in sorted(grouped.items())]


def _structured_candidate(
    slot: str,
    value: str,
    image_ids: set[str],
    observation_model: str,
) -> dict[str, Any]:
    supporting_ids = sorted(image_ids)
    count = len(supporting_ids)
    return {
        "slot": slot,
        "value": value,
        "candidate_source": "product_image_view_aggregation",
        "supporting_card_ids": supporting_ids,
        "supporting_card_count": count,
        "aggregation_threshold": 1,
        "observation_model": observation_model,
        "evidence_summary": f"Observed {slot}={value} across {count} product images.",
    }


def _extraction_provenance(
    product_id: str,
    images: list[dict[str, Any]],
    observation_model: str,
) -> dict[str, Any]:
    return {
        "kind": "product-image-aggregation",
        "product_id": product_id,
        "image_ids": sorted(str(image["image_id"]) for image in images),
        "observation_model": observation_model,
    }


def _normalized_value(value: str) -> str:
    return " ".join(value.strip().casefold().split())
