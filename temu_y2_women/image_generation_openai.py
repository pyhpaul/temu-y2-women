from __future__ import annotations

from base64 import b64decode
from dataclasses import dataclass
import subprocess
from typing import Any, Callable

from openai import OpenAI

from temu_y2_women.errors import GenerationError
from temu_y2_women.image_gateway_curl import (
    render_edit_with_curl,
    render_generate_with_curl,
    uses_curl_transport,
)
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
        curl_runner: Callable[..., Any] = subprocess.run,
    ) -> None:
        self._config = config
        self._curl_runner = curl_runner
        self._uses_curl_transport = uses_curl_transport(config.base_url)
        self._client = None if self._uses_curl_transport else client_factory(**_client_kwargs(config))

    def render(self, render_input: object) -> ImageProviderResult:
        if self._uses_curl_transport:
            return self._render_with_curl(render_input)
        if _is_edit_request(render_input):
            return self._render_edit(render_input)
        return self._render_generate(render_input)

    def _render_with_curl(self, render_input: object) -> ImageProviderResult:
        if _is_edit_request(render_input):
            return self._render_edit_with_curl(render_input)
        return self._render_generate_with_curl(render_input)

    def _render_generate(self, render_input: object) -> ImageProviderResult:
        response = self._required_client().images.generate(
            prompt=getattr(render_input, "prompt"),
            model=self._config.model,
            size=self._config.size,
            quality=self._config.quality,
            background=self._config.background,
            style=self._config.style,
            response_format="b64_json",
            output_format="png",
        )
        return _provider_result_from_response(response, self._config)

    def _render_edit(self, render_input: object) -> ImageProviderResult:
        response = self._required_client().images.edit(
            image=("reference.png", _required_reference_image_bytes(render_input), "image/png"),
            prompt=getattr(render_input, "prompt"),
            model=self._config.model,
            size=self._config.size,
            quality=self._config.quality,
            background=self._config.background,
            input_fidelity="high",
            response_format="b64_json",
            output_format="png",
        )
        return _provider_result_from_response(response, self._config)

    def _render_generate_with_curl(self, render_input: object) -> ImageProviderResult:
        return render_generate_with_curl(
            config=self._config,
            prompt=getattr(render_input, "prompt"),
            curl_runner=self._curl_runner,
        )

    def _render_edit_with_curl(self, render_input: object) -> ImageProviderResult:
        return render_edit_with_curl(
            config=self._config,
            prompt=getattr(render_input, "prompt"),
            reference_image_bytes=_required_reference_image_bytes(render_input),
            curl_runner=self._curl_runner,
        )

    def _required_client(self) -> Any:
        if self._client is not None:
            return self._client
        raise GenerationError(
            code="IMAGE_PROVIDER_FAILED",
            message="OpenAI SDK client is unavailable for the current gateway transport",
            details={"provider": "openai", "field": "base_url"},
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
        return self._provider_for_input(render_input).render(render_input)

    def _provider_for_input(self, render_input: object) -> ImageProvider:
        if self._expansion_provider and _uses_expansion_route(render_input):
            return self._expansion_provider
        return self._default_provider


def build_openai_image_provider(
    config: ResolvedOpenAIImageConfig,
    *,
    client_factory: Callable[..., Any] = OpenAI,
    curl_runner: Callable[..., Any] = subprocess.run,
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
            curl_runner=curl_runner,
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
    curl_runner: Callable[..., Any] = subprocess.run,
) -> ImageProvider:
    default_provider = build_openai_image_provider(
        configs.default_config,
        client_factory=client_factory,
        curl_runner=curl_runner,
    )
    if configs.expansion_config is None:
        return default_provider
    return RoutedOpenAIImageProvider(
        default_provider=default_provider,
        expansion_provider=build_openai_image_provider(
            configs.expansion_config,
            client_factory=client_factory,
            curl_runner=curl_runner,
        ),
    )


def _client_kwargs(config: OpenAIImageProviderConfig) -> dict[str, str]:
    kwargs = {"api_key": config.api_key}
    if config.base_url:
        kwargs["base_url"] = config.base_url
    return kwargs


def _uses_expansion_route(render_input: object) -> bool:
    if _is_edit_request(render_input):
        return True
    return getattr(render_input, "prompt_id", "") != "hero_front"


def _provider_result_from_response(
    response: object,
    config: OpenAIImageProviderConfig,
) -> ImageProviderResult:
    image_data = (getattr(response, "data", None) or [None])[0]
    return _provider_result_from_b64_json(getattr(image_data, "b64_json", ""), config)


def _provider_result_from_b64_json(
    b64_json: str,
    config: OpenAIImageProviderConfig,
) -> ImageProviderResult:
    if not b64_json:
        raise GenerationError(
            code="IMAGE_PROVIDER_FAILED",
            message="OpenAI image provider returned no image payload",
            details={"provider": "openai"},
        )
    return ImageProviderResult(
        image_bytes=b64decode(b64_json),
        mime_type="image/png",
        provider_name="openai",
        model=config.model,
        base_url=config.base_url,
    )


def _is_edit_request(render_input: object) -> bool:
    return getattr(render_input, "render_strategy", "generate") == "edit"


def _required_reference_image_bytes(render_input: object) -> bytes:
    value = getattr(render_input, "reference_image_bytes", None)
    if isinstance(value, bytes) and value:
        return value
    raise GenerationError(
        code="IMAGE_PROVIDER_FAILED",
        message="OpenAI image edit requires reference image bytes",
        details={"provider": "openai", "field": "reference_image_bytes"},
    )
