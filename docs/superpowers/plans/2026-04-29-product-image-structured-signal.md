# Product Image Structured Signal Implementation Plan

> Completion status: implemented on `main` and verified with `python -m pytest tests` on 2026-04-30.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]` / `- [x]`) syntax for tracking.

**Goal:** 把用户提交的单款/多款商品图转成 `structured_candidates` 并进入现有 `signal_ingestion -> draft_elements -> review` 主链，且默认不依赖商品标题文本命中。

**Architecture:** 新增一条独立的 `product image input -> image observation -> structured signal bundle -> signal_ingestion` 上游链路，尽量不改 refresh / promotion 主链。商品图链路复用既有 `structured_candidates` schema 与 staged artifacts，只在 `signal_ingestion.py` 上补一个新的 `candidate_source` 常量，其他能力尽量通过新增 `product_image_*` 模块完成。

**Tech Stack:** Python 3、现有 `unittest` 测试体系、OpenAI-compatible Responses API、JSON staged artifacts、现有 `signal_ingestion.py` / `evidence_promotion_cli.py`、`validate_python_function_length.py`、`validate_forbidden_patterns.py`。

---

## File Map

- Create: `temu_y2_women/product_image_observer.py`
- Create: `temu_y2_women/product_image_observer_openai.py`
- Create: `temu_y2_women/product_image_signal_builder.py`
- Create: `temu_y2_women/product_image_signal_run.py`
- Create: `temu_y2_women/product_image_signal_cli.py`
- Modify: `temu_y2_women/signal_ingestion.py`
- Create: `tests/test_product_image_observer.py`
- Create: `tests/test_product_image_observer_openai.py`
- Create: `tests/test_product_image_signal_builder.py`
- Create: `tests/test_product_image_signal_run.py`
- Create: `tests/test_product_image_signal_cli.py`
- Modify: `tests/test_signal_ingestion.py`
- Create: `tests/fixtures/product_image_signals/dress/input-manifest.json`
- Create: `tests/fixtures/product_image_signals/dress/expected-image-observations.json`
- Create: `tests/fixtures/product_image_signals/dress/expected-signal-bundle.json`
- Create: `tests/fixtures/product_image_signals/dress/expected-run-report.json`

## Task 1: 建立商品图输入与观察结果 contract

**Files:**
- Create: `temu_y2_women/product_image_observer.py`
- Create: `tests/test_product_image_observer.py`
- Create: `tests/fixtures/product_image_signals/dress/input-manifest.json`
- Create: `tests/fixtures/product_image_signals/dress/expected-image-observations.json`

- [x] **Step 1: 先写失败测试，固定 manifest 与 observation 输出 shape**

Create `tests/test_product_image_observer.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


_FIXTURE_DIR = Path("tests/fixtures/product_image_signals/dress")


class ProductImageObserverTest(unittest.TestCase):
    def test_observe_product_images_normalizes_slots_and_preserves_image_context(self) -> None:
        from temu_y2_women.product_image_observer import observe_product_images

        manifest = _read_json(_FIXTURE_DIR / "input-manifest.json")

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            front = temp_root / "front.jpg"
            back = temp_root / "back.jpg"
            front.write_bytes(b"front")
            back.write_bytes(b"back")
            manifest["products"][0]["images"][0]["image_path"] = str(front)
            manifest["products"][0]["images"][1]["image_path"] = str(back)

            def fake_observe_image(image: dict[str, object]) -> dict[str, object]:
                if image["image_id"] == "dress-product-001-front":
                    return {
                        "observed_slots": [
                            {"slot": "neckline", "value": "square neckline", "evidence_summary": "front view shows a flat squared neck opening"},
                            {"slot": "dress_length", "value": "mini", "evidence_summary": "hemline sits above the knee"},
                            {"slot": "unsupported_slot", "value": "ignore", "evidence_summary": "bad"},
                        ],
                        "abstained_slots": ["opacity_level"],
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
                manifest=manifest,
                observation_model="fake-product-image-observer",
                observe_image=fake_observe_image,
            )

        expected = _read_json(_FIXTURE_DIR / "expected-image-observations.json")
        expected["products"][0]["images"][0]["image_path"] = str(front)
        expected["products"][0]["images"][1]["image_path"] = str(back)
        self.assertEqual(result, expected)
```

Create `tests/fixtures/product_image_signals/dress/input-manifest.json`:

```json
{
  "schema_version": "product-image-input-v1",
  "products": [
    {
      "product_id": "dress-product-001",
      "category": "dress",
      "target_market": "US",
      "product_title": "reference only for image observer context",
      "source_url": "https://example.com/products/dress-product-001",
      "price_band": "mid",
      "occasion_tags": [
        "vacation"
      ],
      "season_tags": [
        "summer"
      ],
      "manual_tags": [
        "vacation",
        "summer"
      ],
      "images": [
        {
          "image_id": "dress-product-001-front",
          "image_path": "front.jpg",
          "view_label": "front"
        },
        {
          "image_id": "dress-product-001-back",
          "image_path": "back.jpg",
          "view_label": "back"
        }
      ]
    }
  ]
}
```

Create `tests/fixtures/product_image_signals/dress/expected-image-observations.json`:

```json
{
  "schema_version": "product-image-observations-v1",
  "observation_model": "fake-product-image-observer",
  "products": [
    {
      "product_id": "dress-product-001",
      "category": "dress",
      "target_market": "US",
      "source_url": "https://example.com/products/dress-product-001",
      "product_title": "reference only for image observer context",
      "images": [
        {
          "image_id": "dress-product-001-front",
          "image_path": "front.jpg",
          "view_label": "front",
          "observed_slots": [
            {
              "slot": "neckline",
              "value": "square neckline",
              "evidence_summary": "front view shows a flat squared neck opening"
            },
            {
              "slot": "dress_length",
              "value": "mini",
              "evidence_summary": "hemline sits above the knee"
            }
          ],
          "abstained_slots": [
            "opacity_level"
          ],
          "warnings": []
        },
        {
          "image_id": "dress-product-001-back",
          "image_path": "back.jpg",
          "view_label": "back",
          "observed_slots": [
            {
              "slot": "detail",
              "value": "smocked bodice",
              "evidence_summary": "back panel shows dense elastic smocking"
            }
          ],
          "abstained_slots": [
            "neckline"
          ],
          "warnings": [
            "sleeve not visible in back view"
          ]
        }
      ]
    }
  ]
}
```

- [x] **Step 2: 运行聚焦测试，确认当前失败**

Run: `python -m unittest tests.test_product_image_observer -v`

Expected:
- `FAIL`
- `ModuleNotFoundError: No module named 'temu_y2_women.product_image_observer'`

- [x] **Step 3: 实现 manifest 校验与商品图观察模块**

Create `temu_y2_women/product_image_observer.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from temu_y2_women.errors import GenerationError


ProductImageObserver = Callable[[dict[str, Any]], dict[str, Any]]
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
    observe_image: ProductImageObserver,
) -> dict[str, Any]:
    products = _validated_products(manifest)
    return {
        "schema_version": "product-image-observations-v1",
        "observation_model": observation_model,
        "products": [_observe_product(product, observe_image) for product in products],
    }


def _validated_products(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    products = manifest.get("products")
    if manifest.get("schema_version") != "product-image-input-v1":
        raise GenerationError(code="INVALID_PRODUCT_IMAGE_INPUT", message="unsupported product image manifest schema")
    if not isinstance(products, list) or not products:
        raise GenerationError(code="INVALID_PRODUCT_IMAGE_INPUT", message="product image manifest must contain products")
    return [_validated_product(product) for product in products]


def _validated_product(product: Any) -> dict[str, Any]:
    if not isinstance(product, dict):
        raise GenerationError(code="INVALID_PRODUCT_IMAGE_INPUT", message="product record must be an object")
    if str(product.get("category")) != "dress" or str(product.get("target_market")) != "US":
        raise GenerationError(code="INVALID_PRODUCT_IMAGE_INPUT", message="only US dress product images are supported")
    images = product.get("images")
    if not isinstance(images, list) or not images:
        raise GenerationError(code="INVALID_PRODUCT_IMAGE_INPUT", message="product image manifest requires at least one image")
    return {
        "product_id": str(product["product_id"]),
        "category": "dress",
        "target_market": "US",
        "product_title": str(product.get("product_title", "")).strip(),
        "source_url": str(product.get("source_url", "")).strip(),
        "price_band": str(product.get("price_band", "mid")).strip(),
        "occasion_tags": [str(item) for item in product.get("occasion_tags", [])],
        "season_tags": [str(item) for item in product.get("season_tags", [])],
        "manual_tags": [str(item) for item in product.get("manual_tags", [])],
        "images": [_validated_image(image) for image in images],
    }


def _validated_image(image: Any) -> dict[str, Any]:
    if not isinstance(image, dict):
        raise GenerationError(code="INVALID_PRODUCT_IMAGE_INPUT", message="image record must be an object")
    image_path = Path(str(image["image_path"]))
    if not image_path.is_file():
        raise GenerationError(
            code="INVALID_PRODUCT_IMAGE_INPUT",
            message="product image path does not exist",
            details={"path": str(image_path)},
        )
    return {
        "image_id": str(image["image_id"]),
        "image_path": str(image_path),
        "view_label": str(image.get("view_label", "")).strip(),
    }


def _observe_product(product: dict[str, Any], observe_image: ProductImageObserver) -> dict[str, Any]:
    return {
        "product_id": product["product_id"],
        "category": product["category"],
        "target_market": product["target_market"],
        "source_url": product["source_url"],
        "product_title": product["product_title"],
        "images": [_observe_single_image(image, observe_image) for image in product["images"]],
    }


def _observe_single_image(image: dict[str, Any], observe_image: ProductImageObserver) -> dict[str, Any]:
    payload = observe_image(image)
    observed_slots = _normalized_observed_slots(payload)
    abstained_slots = _normalized_abstained_slots(payload)
    if not observed_slots and not abstained_slots:
        raise GenerationError(code="INVALID_PRODUCT_IMAGE_OBSERVATION", message="observer returned no usable slots")
    return {
        **image,
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
```

- [x] **Step 4: 重新运行测试，确认 contract 固定**

Run: `python -m unittest tests.test_product_image_observer -v`

Expected:
- `PASS`
- 仅保留白名单 slots
- 本地图片路径、view_label、warnings 都被保留

- [x] **Step 5: 提交 contract 基础模块**

```bash
git add \
  temu_y2_women/product_image_observer.py \
  tests/test_product_image_observer.py \
  tests/fixtures/product_image_signals/dress/input-manifest.json \
  tests/fixtures/product_image_signals/dress/expected-image-observations.json
git commit -m "feat: add product image observation contract"
```

## Task 2: 为本地商品图补 OpenAI-compatible live observer

**Files:**
- Create: `temu_y2_women/product_image_observer_openai.py`
- Create: `tests/test_product_image_observer_openai.py`

- [x] **Step 1: 先写失败测试，锁定配置校验与 data URL 输入行为**

Create `tests/test_product_image_observer_openai.py`:

```python
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch


class ProductImageObserverOpenAITest(unittest.TestCase):
    def test_build_openai_product_image_observer_requires_api_key(self) -> None:
        from temu_y2_women.product_image_observer_openai import build_openai_product_image_observer
        from temu_y2_women.errors import GenerationError

        with self.assertRaises(GenerationError) as error:
            build_openai_product_image_observer(api_key="", base_url="https://example.com/v1")

        self.assertEqual(error.exception.code, "INVALID_PRODUCT_IMAGE_OBSERVER_CONFIG")

    def test_observe_image_sends_local_file_as_data_url_and_parses_json(self) -> None:
        from temu_y2_women.product_image_observer_openai import build_openai_product_image_observer

        fake_client = Mock()
        fake_client.responses.create.return_value = Mock(
            output_text='{"observed_slots":[{"slot":"pattern","value":"gingham check","evidence_summary":"grid checks visible across bodice"}],"abstained_slots":["waistline"],"warnings":[]}'
        )

        with TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "front.jpg"
            image_path.write_bytes(b"fake-jpeg-bytes")
            with patch("temu_y2_women.product_image_observer_openai.OpenAI", return_value=fake_client):
                observer = build_openai_product_image_observer(
                    api_key="test-key",
                    base_url="https://example.com/v1",
                    model="gpt-4.1-mini",
                )
                payload = observer.observe_image(
                    {
                        "image_id": "dress-product-001-front",
                        "image_path": str(image_path),
                        "view_label": "front",
                    }
                )

        self.assertEqual(payload["observed_slots"][0]["slot"], "pattern")
        request = fake_client.responses.create.call_args.kwargs["input"][0]
        self.assertEqual(request["content"][1]["type"], "input_image")
        self.assertTrue(request["content"][1]["image_url"].startswith("data:image/jpeg;base64,"))
```

- [x] **Step 2: 运行聚焦测试，确认当前失败**

Run: `python -m unittest tests.test_product_image_observer_openai -v`

Expected:
- `FAIL`
- `ModuleNotFoundError: No module named 'temu_y2_women.product_image_observer_openai'`

- [x] **Step 3: 实现 live observer，支持本地文件读取与 JSON-only 返回**

Create `temu_y2_women/product_image_observer_openai.py`:

```python
from __future__ import annotations

import base64
from dataclasses import dataclass
import json
import mimetypes
import os
from pathlib import Path
from typing import Any

from openai import OpenAI

from temu_y2_women.errors import GenerationError


@dataclass(frozen=True, slots=True)
class OpenAIProductImageObserverConfig:
    api_key: str
    base_url: str
    model: str


class OpenAIProductImageObserver:
    def __init__(self, config: OpenAIProductImageObserverConfig) -> None:
        self._config = config
        self._client = OpenAI(api_key=config.api_key, base_url=config.base_url)

    def observe_image(self, image: dict[str, Any]) -> dict[str, Any]:
        response = self._client.responses.create(
            model=self._config.model,
            input=[_observer_input(image)],
        )
        return _response_payload(response.output_text, str(image["image_id"]))


def build_openai_product_image_observer(
    api_key: str | None = None,
    base_url: str | None = None,
    model: str = "gpt-4.1-mini",
) -> OpenAIProductImageObserver:
    resolved_api_key = (api_key or os.getenv("OPENAI_COMPAT_EXPANSION_API_KEY", "")).strip()
    resolved_base_url = (base_url or os.getenv("OPENAI_COMPAT_BASE_URL", "")).strip()
    if not resolved_api_key:
        raise GenerationError(code="INVALID_PRODUCT_IMAGE_OBSERVER_CONFIG", message="product image observer requires api_key")
    if not resolved_base_url:
        raise GenerationError(code="INVALID_PRODUCT_IMAGE_OBSERVER_CONFIG", message="product image observer requires base_url")
    return OpenAIProductImageObserver(
        OpenAIProductImageObserverConfig(
            api_key=resolved_api_key,
            base_url=resolved_base_url,
            model=model,
        )
    )


def _observer_input(image: dict[str, Any]) -> dict[str, Any]:
    return {
        "role": "user",
        "content": [
            {"type": "input_text", "text": _observer_prompt(image)},
            {"type": "input_image", "image_url": _image_data_url(Path(str(image["image_path"])))},
        ],
    }


def _observer_prompt(image: dict[str, Any]) -> str:
    return (
        "Observe this women's dress product image and return JSON only. "
        "Use keys observed_slots, abstained_slots, warnings. "
        "Allowed slots: silhouette, neckline, sleeve, dress_length, pattern, "
        "color_family, waistline, print_scale, opacity_level, detail. "
        f"View label: {image.get('view_label', '')}. "
        "Do not infer subjective style labels."
    )


def _image_data_url(path: Path) -> str:
    mime_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _response_payload(output_text: str, image_id: str) -> dict[str, Any]:
    try:
        return json.loads(output_text)
    except json.JSONDecodeError as error:
        raise GenerationError(
            code="INVALID_PRODUCT_IMAGE_OBSERVATION",
            message="observer returned invalid JSON",
            details={"image_id": image_id},
        ) from error
```

- [x] **Step 4: 重新运行 live observer 测试**

Run: `python -m unittest tests.test_product_image_observer_openai -v`

Expected:
- `PASS`
- 缺失配置时报 `INVALID_PRODUCT_IMAGE_OBSERVER_CONFIG`
- 本地图片会被编码成 data URL 送入 `responses.create(...)`

- [x] **Step 5: 提交 live observer**

```bash
git add \
  temu_y2_women/product_image_observer_openai.py \
  tests/test_product_image_observer_openai.py
git commit -m "feat: add openai product image observer"
```

## Task 3: 把多视角商品图观察结果聚合成 `signal-bundle-v1`

**Files:**
- Create: `temu_y2_women/product_image_signal_builder.py`
- Create: `tests/test_product_image_signal_builder.py`
- Create: `tests/fixtures/product_image_signals/dress/expected-signal-bundle.json`

- [x] **Step 1: 先写失败测试，锁定 neutral text + structured candidates 聚合行为**

Create `tests/test_product_image_signal_builder.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
import unittest


_FIXTURE_DIR = Path("tests/fixtures/product_image_signals/dress")


class ProductImageSignalBuilderTest(unittest.TestCase):
    def test_build_product_image_signal_bundle_aggregates_candidates_without_title_leakage(self) -> None:
        from temu_y2_women.product_image_signal_builder import build_product_image_signal_bundle

        manifest = _read_json(_FIXTURE_DIR / "input-manifest.json")
        observations = _read_json(_FIXTURE_DIR / "expected-image-observations.json")
        result = build_product_image_signal_bundle(
            manifest=manifest,
            observations=observations,
            observed_at="2026-04-29T00:00:00Z",
        )

        self.assertEqual(result, _read_json(_FIXTURE_DIR / "expected-signal-bundle.json"))
        signal = result["signals"][0]
        self.assertEqual(signal["title"], "Product image observation for dress-product-001")
        self.assertEqual(
            signal["summary"],
            "Structured candidates aggregated from 2 submitted product images.",
        )
        self.assertNotIn("square neckline", signal["title"])
```

Create `tests/fixtures/product_image_signals/dress/expected-signal-bundle.json`:

```json
{
  "schema_version": "signal-bundle-v1",
  "signals": [
    {
      "signal_id": "product-image-dress-product-001",
      "source_type": "product_image_input",
      "source_url": "https://example.com/products/dress-product-001",
      "captured_at": "2026-04-29T00:00:00Z",
      "target_market": "US",
      "category": "dress",
      "title": "Product image observation for dress-product-001",
      "summary": "Structured candidates aggregated from 2 submitted product images.",
      "observed_price_band": "mid",
      "observed_occasion_tags": [
        "vacation"
      ],
      "observed_season_tags": [
        "summer"
      ],
      "manual_tags": [
        "summer",
        "vacation"
      ],
      "status": "active",
      "structured_candidates": [
        {
          "slot": "detail",
          "value": "smocked bodice",
          "candidate_source": "product_image_view_aggregation",
          "supporting_card_ids": [
            "dress-product-001-back"
          ],
          "supporting_card_count": 1,
          "aggregation_threshold": 1,
          "observation_model": "fake-product-image-observer",
          "evidence_summary": "Observed detail=smocked bodice across 1 product images."
        },
        {
          "slot": "dress_length",
          "value": "mini",
          "candidate_source": "product_image_view_aggregation",
          "supporting_card_ids": [
            "dress-product-001-front"
          ],
          "supporting_card_count": 1,
          "aggregation_threshold": 1,
          "observation_model": "fake-product-image-observer",
          "evidence_summary": "Observed dress_length=mini across 1 product images."
        },
        {
          "slot": "neckline",
          "value": "square neckline",
          "candidate_source": "product_image_view_aggregation",
          "supporting_card_ids": [
            "dress-product-001-front"
          ],
          "supporting_card_count": 1,
          "aggregation_threshold": 1,
          "observation_model": "fake-product-image-observer",
          "evidence_summary": "Observed neckline=square neckline across 1 product images."
        }
      ],
      "extraction_provenance": {
        "kind": "product-image-aggregation",
        "product_id": "dress-product-001",
        "image_ids": [
          "dress-product-001-back",
          "dress-product-001-front"
        ],
        "observation_model": "fake-product-image-observer"
      }
    }
  ]
}
```

- [x] **Step 2: 运行聚焦测试，确认当前失败**

Run: `python -m unittest tests.test_product_image_signal_builder -v`

Expected:
- `FAIL`
- `ModuleNotFoundError: No module named 'temu_y2_women.product_image_signal_builder'`

- [x] **Step 3: 实现 signal bundle 聚合器，默认隔离文本通道**

Create `temu_y2_women/product_image_signal_builder.py`:

```python
from __future__ import annotations

from typing import Any


def build_product_image_signal_bundle(
    manifest: dict[str, Any],
    observations: dict[str, Any],
    observed_at: str,
) -> dict[str, Any]:
    products = list(manifest["products"])
    observed_products = {str(product["product_id"]): product for product in observations["products"]}
    return {
        "schema_version": "signal-bundle-v1",
        "signals": [
            _signal_record(product, observed_products[str(product["product_id"])], observed_at, observations["observation_model"])
            for product in products
        ],
    }


def _signal_record(
    product: dict[str, Any],
    observed_product: dict[str, Any],
    observed_at: str,
    observation_model: str,
) -> dict[str, Any]:
    return {
        "signal_id": f"product-image-{product['product_id']}",
        "source_type": "product_image_input",
        "source_url": str(product.get("source_url", "")).strip(),
        "captured_at": observed_at,
        "target_market": "US",
        "category": "dress",
        "title": f"Product image observation for {product['product_id']}",
        "summary": f"Structured candidates aggregated from {len(observed_product['images'])} submitted product images.",
        "observed_price_band": str(product.get("price_band", "mid")).strip(),
        "observed_occasion_tags": sorted(set(str(item) for item in product.get("occasion_tags", []))),
        "observed_season_tags": sorted(set(str(item) for item in product.get("season_tags", []))),
        "manual_tags": sorted(set(str(item) for item in product.get("manual_tags", []))),
        "status": "active",
        "structured_candidates": _structured_candidates(observed_product["images"], observation_model),
        "extraction_provenance": {
            "kind": "product-image-aggregation",
            "product_id": product["product_id"],
            "image_ids": sorted(str(image["image_id"]) for image in observed_product["images"]),
            "observation_model": observation_model,
        },
    }


def _structured_candidates(images: list[dict[str, Any]], observation_model: str) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for image in images:
        for slot_record in image["observed_slots"]:
            key = (str(slot_record["slot"]), str(slot_record["value"]).strip().casefold())
            grouped.setdefault(
                key,
                {
                    "slot": str(slot_record["slot"]),
                    "value": str(slot_record["value"]).strip().casefold(),
                    "supporting_card_ids": [],
                },
            )
            grouped[key]["supporting_card_ids"].append(str(image["image_id"]))
    return [
        {
            "slot": item["slot"],
            "value": item["value"],
            "candidate_source": "product_image_view_aggregation",
            "supporting_card_ids": sorted(set(item["supporting_card_ids"])),
            "supporting_card_count": len(set(item["supporting_card_ids"])),
            "aggregation_threshold": 1,
            "observation_model": observation_model,
            "evidence_summary": f"Observed {item['slot']}={item['value']} across {len(set(item['supporting_card_ids']))} product images.",
        }
        for item in sorted(grouped.values(), key=lambda entry: (entry["slot"], entry["value"]))
    ]
```

这里要明确保留一个设计边界：`product_title` 只允许在 observer prompt 中作为上下文，不写回 `signal_bundle.title/summary`，否则又会重新引入 title phrase match 污染。

- [x] **Step 4: 重新运行 builder 测试**

Run: `python -m unittest tests.test_product_image_signal_builder -v`

Expected:
- `PASS`
- signal bundle 可被现有 `signal_ingestion` 直接消费
- `title/summary` 保持 neutral，不承载具体元素词

- [x] **Step 5: 提交 builder**

```bash
git add \
  temu_y2_women/product_image_signal_builder.py \
  tests/test_product_image_signal_builder.py \
  tests/fixtures/product_image_signals/dress/expected-signal-bundle.json
git commit -m "feat: build structured signal bundle from product images"
```

## Task 4: 接入既有 ingestion，完成本地 run 产物闭环

**Files:**
- Create: `temu_y2_women/product_image_signal_run.py`
- Modify: `temu_y2_women/signal_ingestion.py`
- Create: `tests/test_product_image_signal_run.py`
- Modify: `tests/test_signal_ingestion.py`
- Create: `tests/fixtures/product_image_signals/dress/expected-run-report.json`

- [x] **Step 1: 先写两个失败测试：新 candidate_source 可被 ingestion 接受，run 会落 staged artifacts**

Append to `tests/test_signal_ingestion.py`:

```python
    def test_ingest_dress_signals_accepts_product_image_structured_candidates(self) -> None:
        from temu_y2_women.signal_ingestion import ingest_dress_signals

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            input_path = temp_root / "signals.json"
            input_path.write_text(
                json.dumps(
                    {
                        "schema_version": "signal-bundle-v1",
                        "signals": [
                            {
                                "signal_id": "product-image-dress-product-001",
                                "source_type": "product_image_input",
                                "source_url": "https://example.com/products/dress-product-001",
                                "captured_at": "2026-04-29T00:00:00Z",
                                "target_market": "US",
                                "category": "dress",
                                "title": "Product image observation for dress-product-001",
                                "summary": "Structured candidates aggregated from 2 submitted product images.",
                                "observed_price_band": "mid",
                                "observed_occasion_tags": ["vacation"],
                                "observed_season_tags": ["summer"],
                                "manual_tags": ["vacation"],
                                "status": "active",
                                "structured_candidates": [
                                    {
                                        "slot": "neckline",
                                        "value": "square neckline",
                                        "candidate_source": "product_image_view_aggregation",
                                        "supporting_card_ids": ["dress-product-001-front"],
                                        "supporting_card_count": 1,
                                        "aggregation_threshold": 1,
                                        "observation_model": "fake-product-image-observer",
                                        "evidence_summary": "Observed neckline=square neckline across 1 product images."
                                    }
                                ]
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            report = ingest_dress_signals(input_path=input_path, output_dir=temp_root / "staged")

        self.assertNotIn("error", report)
```

Create `tests/test_product_image_signal_run.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


_FIXTURE_DIR = Path("tests/fixtures/product_image_signals/dress")


class ProductImageSignalRunTest(unittest.TestCase):
    def test_run_product_image_signal_ingestion_writes_expected_artifacts(self) -> None:
        from temu_y2_women.product_image_signal_run import run_product_image_signal_ingestion

        manifest = _read_json(_FIXTURE_DIR / "input-manifest.json")

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            front = temp_root / "front.jpg"
            back = temp_root / "back.jpg"
            front.write_bytes(b"front")
            back.write_bytes(b"back")
            manifest["products"][0]["images"][0]["image_path"] = str(front)
            manifest["products"][0]["images"][1]["image_path"] = str(back)
            manifest_path = temp_root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            def fake_observe_image(image: dict[str, object]) -> dict[str, object]:
                if image["image_id"] == "dress-product-001-front":
                    return {
                        "observed_slots": [
                            {"slot": "neckline", "value": "square neckline", "evidence_summary": "front view shows a flat squared neck opening"},
                            {"slot": "dress_length", "value": "mini", "evidence_summary": "hemline sits above the knee"},
                        ],
                        "abstained_slots": ["opacity_level"],
                        "warnings": [],
                    }
                return {
                    "observed_slots": [
                        {"slot": "detail", "value": "smocked bodice", "evidence_summary": "back panel shows dense elastic smocking"},
                    ],
                    "abstained_slots": ["neckline"],
                    "warnings": ["sleeve not visible in back view"],
                }

            report = run_product_image_signal_ingestion(
                input_path=manifest_path,
                output_root=temp_root / "runs",
                observed_at="2026-04-29T00:00:00Z",
                observe_image=fake_observe_image,
            )
            run_dir = temp_root / "runs" / report["run_id"]

        self.assertTrue((run_dir / "signal_bundle.json").is_file())
        self.assertTrue((run_dir / "draft_elements.json").is_file())
        self.assertEqual(report, _read_json(_FIXTURE_DIR / "expected-run-report.json"))
```

Create `tests/fixtures/product_image_signals/dress/expected-run-report.json`:

```json
{
  "schema_version": "product-image-run-report-v1",
  "run_id": "2026-04-29T00-00-00Z-1products-7529b1",
  "input_product_count": 1,
  "input_image_count": 2,
  "observed_product_count": 1,
  "signal_bundle_count": 1,
  "structured_candidate_count": 3,
  "coverage": {
    "matched_signals": 1,
    "unmatched_signal_ids": []
  },
  "warnings": [
    "sleeve not visible in back view"
  ],
  "errors": []
}
```

- [x] **Step 2: 运行聚焦测试，确认当前失败**

Run: `python -m unittest tests.test_signal_ingestion.SignalIngestionTest.test_ingest_dress_signals_accepts_product_image_structured_candidates tests.test_product_image_signal_run -v`

Expected:
- ingestion 测试 `FAIL`，因为 `candidate_source=product_image_view_aggregation` 尚未允许
- run 测试 `FAIL`，因为 `product_image_signal_run.py` 还不存在

- [x] **Step 3: 扩 `signal_ingestion` 的 source whitelist，并新增 run orchestration**

Modify `temu_y2_women/signal_ingestion.py`:

```python
_ALLOWED_STRUCTURED_CANDIDATE_SOURCES = {
    "roundup_card_image_aggregation",
    "product_image_view_aggregation",
}
```

Create `temu_y2_women/product_image_signal_run.py`:

```python
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from temu_y2_women.errors import GenerationError
from temu_y2_women.product_image_observer import observe_product_images
from temu_y2_women.product_image_observer_openai import build_openai_product_image_observer
from temu_y2_women.product_image_signal_builder import build_product_image_signal_bundle
from temu_y2_women.signal_ingestion import ingest_dress_signals


ProductImageObserver = Callable[[dict[str, Any]], dict[str, Any]]


def run_product_image_signal_ingestion(
    input_path: Path,
    output_root: Path,
    observed_at: str,
    observe_image: ProductImageObserver | None = None,
) -> dict[str, Any]:
    try:
        manifest = json.loads(input_path.read_text(encoding="utf-8"))
        observer, observation_model = _resolve_observer(observe_image)
        observations = observe_product_images(
            manifest=manifest,
            observation_model=observation_model,
            observe_image=observer,
        )
        bundle = build_product_image_signal_bundle(
            manifest=manifest,
            observations=observations,
            observed_at=observed_at,
        )
        run_id = _build_run_id(observed_at, manifest)
        run_dir = output_root / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        _write_json(run_dir / "input_manifest_snapshot.json", manifest)
        _write_json(run_dir / "image_observations.json", observations)
        _write_json(run_dir / "signal_bundle.json", bundle)
        ingestion_report = ingest_dress_signals(
            input_path=run_dir / "signal_bundle.json",
            output_dir=run_dir,
        )
        if "error" in ingestion_report:
            return ingestion_report
        report = _build_run_report(run_id, manifest, observations, bundle, ingestion_report)
        _write_json(run_dir / "product_image_run_report.json", report)
        return report
    except GenerationError as error:
        return error.to_dict()


def _resolve_observer(observe_image: ProductImageObserver | None) -> tuple[ProductImageObserver, str]:
    if observe_image is not None:
        return observe_image, _observer_label(observe_image)
    observer = build_openai_product_image_observer()
    return observer.observe_image, observer.model


def _observer_label(observer: ProductImageObserver) -> str:
    name = getattr(observer, "__name__", "").strip("_")
    if not name:
        return "custom-product-image-observer"
    return name.replace("_", "-")


def _build_run_id(observed_at: str, manifest: dict[str, Any]) -> str:
    product_ids = [str(product["product_id"]) for product in manifest["products"]]
    joined = "|".join(product_ids).encode("utf-8")
    return f"{observed_at.replace(':', '-')}-{len(product_ids)}products-{hashlib.sha1(joined).hexdigest()[:6]}"


def _build_run_report(
    run_id: str,
    manifest: dict[str, Any],
    observations: dict[str, Any],
    bundle: dict[str, Any],
    ingestion_report: dict[str, Any],
) -> dict[str, Any]:
    warnings = _observation_warnings(observations)
    return {
        "schema_version": "product-image-run-report-v1",
        "run_id": run_id,
        "input_product_count": len(manifest["products"]),
        "input_image_count": sum(len(product["images"]) for product in manifest["products"]),
        "observed_product_count": len(observations["products"]),
        "signal_bundle_count": len(bundle["signals"]),
        "structured_candidate_count": sum(len(signal.get("structured_candidates", [])) for signal in bundle["signals"]),
        "coverage": {
            "matched_signals": ingestion_report["coverage"]["matched_signal_count"],
            "unmatched_signal_ids": list(ingestion_report["coverage"]["unmatched_signal_ids"]),
        },
        "warnings": warnings,
        "errors": [],
    }


def _observation_warnings(observations: dict[str, Any]) -> list[str]:
    ordered: list[str] = []
    for product in observations["products"]:
        for image in product["images"]:
            for warning in image.get("warnings", []):
                if warning not in ordered:
                    ordered.append(str(warning))
    return ordered


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
```

- [x] **Step 4: 重新运行 run 与 ingestion 测试**

Run: `python -m unittest tests.test_signal_ingestion tests.test_product_image_signal_run -v`

Expected:
- `PASS`
- `draft_elements.json` 中出现 `square neckline`、`mini`、`smocked bodice`
- `matched_channels` 只有 `structured_candidate`

- [x] **Step 5: 提交 run 闭环**

```bash
git add \
  temu_y2_women/product_image_signal_run.py \
  temu_y2_women/signal_ingestion.py \
  tests/test_product_image_signal_run.py \
  tests/test_signal_ingestion.py \
  tests/fixtures/product_image_signals/dress/expected-run-report.json
git commit -m "feat: stage product image structured signals"
```

## Task 5: 提供 CLI 与可执行操作链路

**Files:**
- Create: `temu_y2_women/product_image_signal_cli.py`
- Create: `tests/test_product_image_signal_cli.py`

- [x] **Step 1: 先写 CLI 失败测试，锁定命令行契约**

Create `tests/test_product_image_signal_cli.py`:

```python
from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
import unittest
from unittest.mock import patch


class ProductImageSignalCliTest(unittest.TestCase):
    def test_cli_runs_stage_and_prints_report(self) -> None:
        from temu_y2_women.product_image_signal_cli import main

        stdout = StringIO()
        with patch(
            "temu_y2_women.product_image_signal_cli.run_product_image_signal_ingestion",
            return_value={
                "schema_version": "product-image-run-report-v1",
                "run_id": "2026-04-29T00-00-00Z-1products-7529b1",
                "input_product_count": 1,
                "input_image_count": 2,
                "observed_product_count": 1,
                "signal_bundle_count": 1,
                "structured_candidate_count": 3,
                "coverage": {"matched_signals": 1, "unmatched_signal_ids": []},
                "warnings": [],
                "errors": [],
            },
        ) as runner, patch("sys.stdout", stdout):
            exit_code = main(
                [
                    "run",
                    "--input",
                    "data/product_images/dress/manifest.json",
                    "--output-root",
                    "data/product_images/dress/runs",
                    "--observed-at",
                    "2026-04-29T00:00:00Z",
                ]
            )

        self.assertEqual(exit_code, 0)
        runner.assert_called_once_with(
            input_path=Path("data/product_images/dress/manifest.json"),
            output_root=Path("data/product_images/dress/runs"),
            observed_at="2026-04-29T00:00:00Z",
        )
        self.assertEqual(json.loads(stdout.getvalue())["schema_version"], "product-image-run-report-v1")

    def test_cli_returns_nonzero_when_runner_returns_error(self) -> None:
        from temu_y2_women.product_image_signal_cli import main

        stdout = StringIO()
        with patch(
            "temu_y2_women.product_image_signal_cli.run_product_image_signal_ingestion",
            return_value={"error": {"code": "INVALID_PRODUCT_IMAGE_INPUT", "message": "bad", "details": {}}},
        ), patch("sys.stdout", stdout):
            exit_code = main(
                [
                    "run",
                    "--input",
                    "data/product_images/dress/manifest.json",
                    "--output-root",
                    "data/product_images/dress/runs",
                    "--observed-at",
                    "2026-04-29T00:00:00Z",
                ]
            )

        self.assertEqual(exit_code, 1)
        self.assertEqual(json.loads(stdout.getvalue())["error"]["code"], "INVALID_PRODUCT_IMAGE_INPUT")
```

- [x] **Step 2: 运行聚焦 CLI 测试，确认当前失败**

Run: `python -m unittest tests.test_product_image_signal_cli -v`

Expected:
- `FAIL`
- `ModuleNotFoundError: No module named 'temu_y2_women.product_image_signal_cli'`

- [x] **Step 3: 实现 CLI，并明确后续 review 命令衔接**

Create `temu_y2_women/product_image_signal_cli.py`:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from temu_y2_women.product_image_signal_run import run_product_image_signal_ingestion


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stage structured dress evidence from local product images.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Observe local product images and write staged ingestion artifacts.")
    run_parser.add_argument("--input", required=True, help="Path to product image manifest JSON.")
    run_parser.add_argument("--output-root", required=True, help="Directory for staged run outputs.")
    run_parser.add_argument("--observed-at", required=True, help="ISO timestamp for this observation run.")

    args = parser.parse_args(argv)
    result = run_product_image_signal_ingestion(
        input_path=Path(args.input),
        output_root=Path(args.output_root),
        observed_at=str(args.observed_at),
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0 if "error" not in result else 1
```

为操作链路补一个固定 smoke 命令，验证 staged 输出能直接接现有 review CLI：

```bash
python -m temu_y2_women.product_image_signal_cli run \
  --input data/product_images/dress/manifest.json \
  --output-root data/product_images/dress/runs \
  --observed-at 2026-04-29T00:00:00Z

python -m temu_y2_women.evidence_promotion_cli prepare \
  --draft-elements data/product_images/dress/runs/2026-04-29T00-00-00Z-1products-7529b1/draft_elements.json \
  --draft-strategy-hints data/product_images/dress/runs/2026-04-29T00-00-00Z-1products-7529b1/draft_strategy_hints.json \
  --active-elements data/mvp/dress/elements.json \
  --active-strategies data/mvp/dress/strategy_templates.json \
  --output data/product_images/dress/runs/2026-04-29T00-00-00Z-1products-7529b1/promotion_review.json
```

- [x] **Step 4: 运行目标测试 + 全量验证**

Run: `python -m unittest tests.test_product_image_observer tests.test_product_image_observer_openai tests.test_product_image_signal_builder tests.test_product_image_signal_run tests.test_product_image_signal_cli tests.test_signal_ingestion -v`

Expected:
- `PASS`
- 商品图链路聚焦测试全部通过

Run: `python -m unittest -v`
Expected: `PASS`

Run: `python validate_python_function_length.py .`
Expected: `OK`

Run: `python validate_forbidden_patterns.py .`
Expected: `OK`

- [x] **Step 5: 提交 CLI 与最终集成**

```bash
git add \
  temu_y2_women/product_image_signal_cli.py \
  tests/test_product_image_signal_cli.py \
  temu_y2_women/product_image_observer.py \
  temu_y2_women/product_image_observer_openai.py \
  temu_y2_women/product_image_signal_builder.py \
  temu_y2_women/product_image_signal_run.py \
  temu_y2_women/signal_ingestion.py \
  tests/test_product_image_observer.py \
  tests/test_product_image_observer_openai.py \
  tests/test_product_image_signal_builder.py \
  tests/test_product_image_signal_run.py \
  tests/test_signal_ingestion.py \
  tests/fixtures/product_image_signals/dress/input-manifest.json \
  tests/fixtures/product_image_signals/dress/expected-image-observations.json \
  tests/fixtures/product_image_signals/dress/expected-signal-bundle.json \
  tests/fixtures/product_image_signals/dress/expected-run-report.json
git commit -m "feat: ingest structured signals from product images"
```

## Self-Review Checklist

- Spec coverage:
  - 商品图输入 contract -> Task 1
  - 本地图 live observer -> Task 2
  - multi-image structured candidate 聚合 -> Task 3
  - 复用既有 `signal_ingestion` / staged artifacts -> Task 4
  - 可执行 CLI 与 review 衔接 -> Task 5
- Placeholder scan:
  - 无占位标记或延后实现表述
  - 每个任务都给出明确文件、测试、命令、代码片段
- Type consistency:
  - `product-image-input-v1`
  - `product-image-observations-v1`
  - `product_image_view_aggregation`
  - `product_image_input`
  - `structured_candidates`
  - `promotion_review.json`

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-29-product-image-structured-signal.md`.

Two execution options:

1. **Subagent-Driven (recommended)** - 按任务拆 fresh subagent，并行推进 A 线实现
2. **Inline Execution** - 在当前会话里按任务顺序直接做

基于你之前已经明确要多 agent 协作，默认下一步按 **Subagent-Driven** 执行，除非你明确切到 Inline。
