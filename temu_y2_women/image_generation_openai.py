from __future__ import annotations

from base64 import b64decode
from dataclasses import dataclass
from typing import Any, Callable

from openai import OpenAI

from temu_y2_women.errors import GenerationError
from temu_y2_women.image_generation_output import ImageProvider, ImageProviderResult
from temu_y2_women.image_provider_config import ResolvedOpenAIImageConfig, ResolvedOpenAIProviderConfigs


@dataclass(frozen=True, slots=True)
class OpenAIImageProviderConfig:
    api_key: str
    base_url: str | None
    model: str
    size: str
    quality: str
    background: str
    style: str


class OpenAIImageProvider:
    def __init__(
        self,
        config: OpenAIImageProviderConfig,
        *,
        client_factory: Callable[..., Any] = OpenAI,
    ) -> None:
        self._config = config
        self._client = client_factory(**_client_kwargs(config))

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
            base_url=self._config.base_url,
        )


class RoutedOpenAIImageProvider:
    def __init__(
        self,
        default_provider: ImageProvider,
        expansion_provider: ImageProvider | None = None,
    ) -> None:
        self._default_provider = default_provider
        self._expansion_provider = expansion_provider

    def render(self, render_input: object) -> ImageProviderResult:
        provider = self._provider_for_input(render_input)
        return provider.render(render_input)

    def _provider_for_input(self, render_input: object) -> ImageProvider:
        if self._expansion_provider and _uses_expansion_route(render_input):
            return self._expansion_provider
        return self._default_provider


def build_openai_image_provider(
    config: ResolvedOpenAIImageConfig,
    *,
    client_factory: Callable[..., Any] = OpenAI,
) -> OpenAIImageProvider:
    if config.api_key.strip():
        return OpenAIImageProvider(
            OpenAIImageProviderConfig(
                api_key=config.api_key.strip(),
                base_url=config.base_url,
                model=config.model,
                size=config.size,
                quality=config.quality,
                background=config.background,
                style=config.style,
            ),
            client_factory=client_factory,
        )
    raise GenerationError(
        code="INVALID_IMAGE_PROVIDER_CONFIG",
        message="OpenAI image provider requires an API key",
        details={"provider": "openai", "field": "api_key"},
    )


def build_routed_openai_image_provider(
    configs: ResolvedOpenAIProviderConfigs,
    *,
    client_factory: Callable[..., Any] = OpenAI,
) -> ImageProvider:
    default_provider = build_openai_image_provider(
        configs.default_config,
        client_factory=client_factory,
    )
    if configs.expansion_config is None:
        return default_provider
    return RoutedOpenAIImageProvider(
        default_provider=default_provider,
        expansion_provider=build_openai_image_provider(
            configs.expansion_config,
            client_factory=client_factory,
        ),
    )


def _client_kwargs(config: OpenAIImageProviderConfig) -> dict[str, str]:
    kwargs = {"api_key": config.api_key}
    if config.base_url:
        kwargs["base_url"] = config.base_url
    return kwargs


def _uses_expansion_route(render_input: object) -> bool:
    return getattr(render_input, "prompt_id", "") != "hero_front"
