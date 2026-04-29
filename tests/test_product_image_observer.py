from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from temu_y2_women.errors import GenerationError


_FIXTURE_DIR = Path("tests/fixtures/product_image_signals/dress")


class ProductImageObserverTest(unittest.TestCase):
    def test_observe_product_images_keeps_only_whitelisted_slots_and_preserves_image_fields(self) -> None:
        from temu_y2_women.product_image_observer import observe_product_images

        manifest = _read_json(_FIXTURE_DIR / "input-manifest.json")
        expected = _read_json(_FIXTURE_DIR / "expected-image-observations.json")

        with TemporaryDirectory() as temp_dir:
            resolved_manifest = _with_real_image_paths(manifest, Path(temp_dir))
            resolved_expected = _with_real_image_paths(expected, Path(temp_dir))

            def fake_observer(image: dict[str, object]) -> dict[str, object]:
                if image["image_id"] == "dress-product-001-front":
                    return {
                        "observed_slots": [
                            {"slot": "neckline", "value": "square neckline", "evidence_summary": "front view shows a flat squared neck opening"},
                            {"slot": "dress_length", "value": "mini", "evidence_summary": "hemline sits above the knee"},
                            {"slot": "unsupported_slot", "value": "ignore", "evidence_summary": "bad"},
                        ],
                        "abstained_slots": ["opacity_level", "bad_slot"],
                        "warnings": [],
                    }
                return {
                    "observed_slots": [
                        {"slot": "detail", "value": "smocked bodice", "evidence_summary": "back panel shows dense elastic smocking"},
                    ],
                    "abstained_slots": ["neckline"],
                    "warnings": ["sleeve not visible in back view"],
                }

            result = observe_product_images(
                manifest=resolved_manifest,
                observation_model="fake-product-image-observer",
                observe_image=fake_observer,
            )

        self.assertEqual(result, resolved_expected)

    def test_observe_product_images_rejects_invalid_manifest_contract(self) -> None:
        from temu_y2_women.product_image_observer import observe_product_images

        with TemporaryDirectory() as temp_dir:
            for name, manifest, error_code in _invalid_manifest_cases(Path(temp_dir)):
                with self.subTest(name=name):
                    with self.assertRaises(GenerationError) as error:
                        observe_product_images(
                            manifest=manifest,
                            observation_model="fake-product-image-observer",
                            observe_image=lambda image: {"observed_slots": [], "abstained_slots": []},
                        )
                    self.assertEqual(error.exception.code, error_code)

    def test_observe_product_images_rejects_empty_observer_output(self) -> None:
        from temu_y2_women.product_image_observer import observe_product_images

        with TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "front.jpg"
            image_path.write_bytes(b"front")
            manifest = {
                "schema_version": "product-image-input-v1",
                "products": [
                    {
                        "product_id": "dress-product-001",
                        "category": "dress",
                        "target_market": "US",
                        "product_title": "reference only for image observer context",
                        "source_url": "https://example.com/products/dress-product-001",
                        "price_band": "mid",
                        "occasion_tags": ["vacation"],
                        "season_tags": ["summer"],
                        "manual_tags": ["vacation", "summer"],
                        "images": [
                            {
                                "image_id": "dress-product-001-front",
                                "image_path": str(image_path),
                                "view_label": "front",
                            }
                        ],
                    }
                ],
            }

            with self.assertRaises(GenerationError) as error:
                observe_product_images(
                    manifest=manifest,
                    observation_model="fake-product-image-observer",
                    observe_image=lambda image: {
                        "observed_slots": [{"slot": "unsupported_slot", "value": "ignore", "evidence_summary": "bad"}],
                        "abstained_slots": ["bad_slot"],
                        "warnings": [],
                    },
                )

        self.assertEqual(error.exception.code, "INVALID_PRODUCT_IMAGE_OBSERVATION")


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _invalid_manifest_cases(temp_dir: Path) -> list[tuple[str, dict[str, object], str]]:
    image_path = temp_dir / "front.jpg"
    image_path.write_bytes(b"front")
    base_product = _base_product(str(image_path))
    base_manifest = {"schema_version": "product-image-input-v1", "products": [base_product]}
    return [
        ("schema_version", {**base_manifest, "schema_version": "wrong"}, "INVALID_PRODUCT_IMAGE_INPUT"),
        ("products_type", {"schema_version": "product-image-input-v1", "products": {}}, "INVALID_PRODUCT_IMAGE_INPUT"),
        ("products", {"schema_version": "product-image-input-v1", "products": []}, "INVALID_PRODUCT_IMAGE_INPUT"),
        ("product_id", _single_product_manifest(base_product, product_id=""), "INVALID_PRODUCT_IMAGE_INPUT"),
        ("target_market", _single_product_manifest(base_product, target_market="UK"), "INVALID_PRODUCT_IMAGE_INPUT"),
        ("category", _single_product_manifest(base_product, category="tops"), "INVALID_PRODUCT_IMAGE_INPUT"),
        ("product_title", _single_product_manifest(base_product, product_title=""), "INVALID_PRODUCT_IMAGE_INPUT"),
        ("source_url", _single_product_manifest(base_product, source_url=""), "INVALID_PRODUCT_IMAGE_INPUT"),
        ("price_band", _single_product_manifest(base_product, price_band=""), "INVALID_PRODUCT_IMAGE_INPUT"),
        ("occasion_tags", _single_product_manifest(base_product, occasion_tags="vacation"), "INVALID_PRODUCT_IMAGE_INPUT"),
        ("season_tags", _single_product_manifest(base_product, season_tags="summer"), "INVALID_PRODUCT_IMAGE_INPUT"),
        ("manual_tags", _single_product_manifest(base_product, manual_tags="vacation"), "INVALID_PRODUCT_IMAGE_INPUT"),
        ("images", _single_product_manifest(base_product, images=[]), "INVALID_PRODUCT_IMAGE_INPUT"),
        ("image_id", _single_image_manifest(base_product, image_id=""), "INVALID_PRODUCT_IMAGE_INPUT"),
        ("view_label", _single_image_manifest(base_product, view_label=""), "INVALID_PRODUCT_IMAGE_INPUT"),
        ("image_path", _single_image_manifest(base_product, image_path=str(temp_dir / "missing.jpg")), "INVALID_PRODUCT_IMAGE_INPUT"),
    ]


def _base_product(image_path: str) -> dict[str, object]:
    return {
        "product_id": "dress-product-001",
        "category": "dress",
        "target_market": "US",
        "product_title": "reference only for image observer context",
        "source_url": "https://example.com/products/dress-product-001",
        "price_band": "mid",
        "occasion_tags": ["vacation"],
        "season_tags": ["summer"],
        "manual_tags": ["vacation", "summer"],
        "images": [
            {
                "image_id": "dress-product-001-front",
                "image_path": image_path,
                "view_label": "front",
            }
        ],
    }


def _single_product_manifest(base_product: dict[str, object], **overrides: object) -> dict[str, object]:
    return {"schema_version": "product-image-input-v1", "products": [{**base_product, **overrides}]}


def _single_image_manifest(base_product: dict[str, object], **image_overrides: object) -> dict[str, object]:
    image = {**base_product["images"][0], **image_overrides}
    product = {**base_product, "images": [image]}
    return _single_product_manifest(product)


def _with_real_image_paths(payload: dict[str, object], temp_dir: Path) -> dict[str, object]:
    rewritten = json.loads(json.dumps(payload))
    for product in rewritten["products"]:
        for image in product["images"]:
            image_path = temp_dir / Path(image["image_path"]).name
            image_path.write_bytes(image["image_id"].encode("utf-8"))
            image["image_path"] = str(image_path)
    return rewritten
