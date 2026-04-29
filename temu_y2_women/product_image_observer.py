from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from temu_y2_women.errors import GenerationError


ImageObserver = Callable[[dict[str, Any]], dict[str, Any]]
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


def observe_product_images(
    manifest: dict[str, Any],
    observation_model: str,
    observe_image: ImageObserver,
) -> dict[str, Any]:
    products = _validated_products(manifest)
    return {
        "schema_version": "product-image-observations-v1",
        "observation_model": observation_model,
        "products": [_observe_product(product, observe_image) for product in products],
    }


def _validated_products(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    if manifest.get("schema_version") != "product-image-input-v1":
        raise _invalid_input("unsupported product image schema")
    products = manifest.get("products")
    if not isinstance(products, list) or not products:
        raise _invalid_input("product image input requires at least one product")
    return [_validated_product(product) for product in products]


def _validated_product(product: Any) -> dict[str, Any]:
    if not isinstance(product, dict):
        raise _invalid_input("product record must be an object")
    if str(product.get("category")) != "dress" or str(product.get("target_market")) != "US":
        raise _invalid_input("product image input only supports US dress products")
    return {
        "product_id": _required_string(product, "product_id"),
        "category": "dress",
        "target_market": "US",
        "product_title": _required_string(product, "product_title"),
        "source_url": _required_string(product, "source_url"),
        "price_band": _required_string(product, "price_band"),
        "occasion_tags": _required_string_list(product, "occasion_tags"),
        "season_tags": _required_string_list(product, "season_tags"),
        "manual_tags": _required_string_list(product, "manual_tags"),
        "images": _validated_images(product),
    }


def _required_string(product: dict[str, Any], field: str) -> str:
    value = product.get(field)
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise _invalid_input(f"product field '{field}' must be a non-empty string", {"field": field})


def _required_string_list(product: dict[str, Any], field: str) -> list[str]:
    value = product.get(field)
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return [item for item in value if item]
    raise _invalid_input(f"product field '{field}' must be a list of strings", {"field": field})


def _validated_images(product: dict[str, Any]) -> list[dict[str, Any]]:
    images = product.get("images")
    if not isinstance(images, list) or not images:
        raise _invalid_input("product image input requires at least one image", {"field": "images"})
    return [_validated_image(image) for image in images]


def _validated_image(image: Any) -> dict[str, Any]:
    if not isinstance(image, dict):
        raise _invalid_input("image record must be an object")
    image_path = Path(_required_image_string(image, "image_path"))
    if not image_path.is_file():
        raise _invalid_input(
            "product image path does not exist",
            {"image_id": image.get("image_id"), "image_path": str(image_path)},
        )
    return {
        "image_id": _required_image_string(image, "image_id"),
        "image_path": str(image_path),
        "view_label": _required_image_string(image, "view_label"),
    }


def _required_image_string(image: dict[str, Any], field: str) -> str:
    value = image.get(field)
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise _invalid_input(f"image field '{field}' must be a non-empty string", {"field": field})


def _observe_product(product: dict[str, Any], observe_image: ImageObserver) -> dict[str, Any]:
    return {
        "product_id": product["product_id"],
        "category": product["category"],
        "target_market": product["target_market"],
        "source_url": product["source_url"],
        "product_title": product["product_title"],
        "images": [_observe_single_image(image, observe_image) for image in product["images"]],
    }


def _observe_single_image(image: dict[str, Any], observe_image: ImageObserver) -> dict[str, Any]:
    payload = observe_image(image)
    observed_slots = _normalized_observed_slots(payload)
    abstained_slots = _normalized_abstained_slots(payload)
    if not observed_slots and not abstained_slots:
        raise GenerationError(
            code="INVALID_PRODUCT_IMAGE_OBSERVATION",
            message="observer returned no usable slots",
            details={"image_id": image["image_id"]},
        )
    return {
        "image_id": image["image_id"],
        "image_path": image["image_path"],
        "view_label": image["view_label"],
        "observed_slots": observed_slots,
        "abstained_slots": abstained_slots,
        "warnings": [str(item) for item in payload.get("warnings", [])],
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
                "value": str(item["value"]).strip(),
                "evidence_summary": str(item["evidence_summary"]).strip(),
            }
        )
    return normalized


def _normalized_abstained_slots(payload: dict[str, Any]) -> list[str]:
    return [str(slot) for slot in payload.get("abstained_slots", []) if str(slot) in _ALLOWED_SLOTS]


def _invalid_input(message: str, details: dict[str, Any] | None = None) -> GenerationError:
    return GenerationError(
        code="INVALID_PRODUCT_IMAGE_INPUT",
        message=message,
        details=details or {},
    )
