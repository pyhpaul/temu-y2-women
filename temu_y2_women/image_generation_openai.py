from __future__ import annotations

from base64 import b64decode
from dataclasses import dataclass
import os

from openai import OpenAI

from temu_y2_women.errors import GenerationError
from temu_y2_women.image_generation_output import ImageProviderResult


@dataclass(frozen=True, slots=True)
class OpenAIImageProviderConfig:
    api_key: str
    model: str
    size: str
    quality: str
    background: str
    style: str


class OpenAIImageProvider:
    def __init__(self, config: OpenAIImageProviderConfig) -> None:
        self._config = config
        self._client = OpenAI(api_key=config.api_key)

    def render(self, render_input: object) -> ImageProviderResult:
        response = self._client.images.generate(
            prompt=getattr(render_input, "prompt"),
            model=self._config.model,
            size=self._config.size,
            quality=self._config.quality,
            background=self._config.background,
            style=self._config.style,
            response_format="b64_json",
            output_format="png",
        )
        image_data = (response.data or [None])[0]
        if image_data is None or not image_data.b64_json:
            raise GenerationError(
                code="IMAGE_PROVIDER_FAILED",
                message="OpenAI image provider returned no image payload",
                details={"provider": "openai"},
            )
        return ImageProviderResult(
            image_bytes=b64decode(image_data.b64_json),
            mime_type="image/png",
            provider_name="openai",
            model=self._config.model,
        )


def build_openai_image_provider(
    api_key: str | None = None,
    model: str = "gpt-image-1",
    size: str = "1024x1536",
    quality: str = "high",
    background: str = "auto",
    style: str = "natural",
) -> OpenAIImageProvider:
    resolved_api_key = (api_key or os.getenv("OPENAI_API_KEY", "")).strip()
    if resolved_api_key:
        return OpenAIImageProvider(
            OpenAIImageProviderConfig(
                api_key=resolved_api_key,
                model=model,
                size=size,
                quality=quality,
                background=background,
                style=style,
            )
        )
    raise GenerationError(
        code="INVALID_IMAGE_PROVIDER_CONFIG",
        message="OpenAI image provider requires OPENAI_API_KEY",
        details={"provider": "openai", "field": "api_key"},
    )
