from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Any

from openai import OpenAI

from temu_y2_women.errors import GenerationError


@dataclass(frozen=True, slots=True)
class OpenAIPublicCardObserverConfig:
    api_key: str
    base_url: str
    model: str


class OpenAIPublicCardObserver:
    def __init__(self, config: OpenAIPublicCardObserverConfig) -> None:
        self._config = config
        self._client = OpenAI(api_key=config.api_key, base_url=config.base_url)

    def observe_card(self, card: dict[str, Any]) -> dict[str, Any]:
        response = self._client.responses.create(
            model=self._config.model,
            input=[_observer_input(card)],
        )
        return _response_payload(response.output_text, str(card["card_id"]))


def build_openai_public_card_observer(
    api_key: str | None = None,
    base_url: str | None = None,
    model: str = "gpt-4.1-mini",
) -> OpenAIPublicCardObserver:
    resolved_api_key = (api_key or os.getenv("OPENAI_COMPAT_EXPANSION_API_KEY", "")).strip()
    resolved_base_url = (base_url or os.getenv("OPENAI_COMPAT_BASE_URL", "")).strip()
    if not resolved_api_key:
        raise GenerationError(
            code="INVALID_PUBLIC_CARD_OBSERVER_CONFIG",
            message="public card observer requires api_key",
            details={"field": "api_key"},
        )
    if not resolved_base_url:
        raise GenerationError(
            code="INVALID_PUBLIC_CARD_OBSERVER_CONFIG",
            message="public card observer requires base_url",
            details={"field": "base_url"},
        )
    return OpenAIPublicCardObserver(
        OpenAIPublicCardObserverConfig(
            api_key=resolved_api_key,
            base_url=resolved_base_url,
            model=model,
        )
    )


def _observer_input(card: dict[str, Any]) -> dict[str, Any]:
    return {
        "role": "user",
        "content": [
            {"type": "input_text", "text": _observer_prompt(card)},
            {"type": "input_image", "image_url": card["image_url"]},
        ],
    }


def _observer_prompt(card: dict[str, Any]) -> str:
    return (
        "Observe this dress product image and return JSON only. "
        "Use keys observed_slots, abstained_slots, warnings. "
        "Allowed slots: silhouette, neckline, sleeve, dress_length, pattern, "
        "color_family, waistline, print_scale, opacity_level, detail. "
        "If a slot is not clearly visible, put it in abstained_slots. "
        f"Card title: {card['title']}. "
        f"Product URL: {card['source_url']}."
    )


def _response_payload(output_text: str, card_id: str) -> dict[str, Any]:
    try:
        return json.loads(output_text)
    except json.JSONDecodeError as error:
        raise GenerationError(
            code="INVALID_PUBLIC_CARD_OBSERVATION",
            message="observer returned invalid JSON",
            details={"card_id": card_id},
        ) from error
