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
        raise GenerationError(
            code="INVALID_PRODUCT_IMAGE_OBSERVER_CONFIG",
            message="product image observer requires api_key",
            details={"field": "api_key"},
        )
    if not resolved_base_url:
        raise GenerationError(
            code="INVALID_PRODUCT_IMAGE_OBSERVER_CONFIG",
            message="product image observer requires base_url",
            details={"field": "base_url"},
        )
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
    return "return JSON only with keys observed_slots, abstained_slots, warnings."


def _image_data_url(path: Path) -> str:
    mime_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _response_payload(output_text: str, image_id: str) -> dict[str, Any]:
    if not isinstance(output_text, str):
        raise GenerationError(
            code="INVALID_PRODUCT_IMAGE_OBSERVATION",
            message="observer returned invalid JSON",
            details={"image_id": image_id},
        )
    try:
        return json.loads(output_text)
    except (TypeError, json.JSONDecodeError) as error:
        raise GenerationError(
            code="INVALID_PRODUCT_IMAGE_OBSERVATION",
            message="observer returned invalid JSON",
            details={"image_id": image_id},
        ) from error
