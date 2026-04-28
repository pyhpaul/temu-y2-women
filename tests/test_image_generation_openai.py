from __future__ import annotations

from base64 import b64encode
import unittest

from temu_y2_women.errors import GenerationError


class OpenAIImageProviderConfigTest(unittest.TestCase):
    def setUp(self) -> None:
        _RecordingImages.calls = []

    def test_build_openai_image_provider_accepts_base_url(self) -> None:
        from temu_y2_women.image_generation_openai import build_openai_image_provider
        from temu_y2_women.image_provider_config import ResolvedOpenAIImageConfig

        captured: dict[str, str] = {}

        def capture_client(**kwargs: str) -> object:
            captured.update(kwargs)
            return _FakeClient()

        provider = build_openai_image_provider(
            ResolvedOpenAIImageConfig(
                api_key="fixture-key",
                base_url="https://example.test",
                model="gpt-image-2",
                size="1024x1536",
                quality="high",
                background="auto",
                style="natural",
            ),
            client_factory=capture_client,
        )

        self.assertIsNotNone(provider)
        self.assertEqual(captured["api_key"], "fixture-key")
        self.assertEqual(captured["base_url"], "https://example.test")

    def test_build_openai_image_provider_rejects_missing_api_key(self) -> None:
        from temu_y2_women.image_generation_openai import build_openai_image_provider
        from temu_y2_women.image_provider_config import ResolvedOpenAIImageConfig

        with self.assertRaises(GenerationError) as error_context:
            build_openai_image_provider(
                ResolvedOpenAIImageConfig(
                    api_key="",
                    base_url="https://example.test",
                    model="gpt-image-2",
                    size="1024x1536",
                    quality="high",
                    background="auto",
                    style="natural",
                )
            )

        self.assertEqual(error_context.exception.code, "INVALID_IMAGE_PROVIDER_CONFIG")
        self.assertEqual(error_context.exception.details["field"], "api_key")

    def test_build_routed_openai_image_provider_uses_expansion_key_for_non_anchor_jobs(self) -> None:
        from temu_y2_women.image_generation_openai import build_routed_openai_image_provider
        from temu_y2_women.image_provider_config import (
            ResolvedOpenAIImageConfig,
            ResolvedOpenAIProviderConfigs,
        )

        provider = build_routed_openai_image_provider(
            ResolvedOpenAIProviderConfigs(
                default_config=_resolved_config("anchor-key"),
                expansion_config=_resolved_config("expansion-key"),
            ),
            client_factory=_recording_client_factory,
        )

        anchor_result = provider.render(_render_input("hero_front"))
        expansion_result = provider.render(_render_input("hero_back", render_strategy="edit", reference_image_bytes=b"anchor-image"))

        self.assertEqual(anchor_result.image_bytes, b"anchor-key-generate")
        self.assertEqual(expansion_result.image_bytes, b"expansion-key-edit")
        self.assertEqual(
            [(item["method"], item["api_key"]) for item in _RecordingImages.calls],
            [("generate", "anchor-key"), ("edit", "expansion-key")],
        )
        self.assertEqual(_RecordingImages.calls[-1]["kwargs"]["input_fidelity"], "high")
        self.assertEqual(_RecordingImages.calls[-1]["kwargs"]["image"][1], b"anchor-image")

    def test_build_openai_image_provider_rejects_edit_without_reference_image_bytes(self) -> None:
        from temu_y2_women.image_generation_openai import build_openai_image_provider

        provider = build_openai_image_provider(
            _resolved_config("anchor-key"),
            client_factory=_recording_client_factory,
        )

        with self.assertRaises(GenerationError) as error_context:
            provider.render(_render_input("hero_back", render_strategy="edit"))

        self.assertEqual(error_context.exception.details["field"], "reference_image_bytes")


class _FakeClient:
    def __init__(self) -> None:
        self.images = _FakeImages()


class _FakeImages:
    def generate(self, **kwargs: str) -> object:
        return object()


def _recording_client_factory(**kwargs: str) -> object:
    return _RecordingClient(kwargs["api_key"])


class _RecordingClient:
    def __init__(self, api_key: str) -> None:
        self.images = _RecordingImages(api_key)


class _RecordingImages:
    calls: list[dict[str, object]] = []

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def generate(self, **kwargs: str) -> object:
        self.calls.append({"method": "generate", "api_key": self._api_key, "kwargs": kwargs})
        payload = _ImagePayload(b64encode(f"{self._api_key}-generate".encode("utf-8")).decode("ascii"))
        return _ImageResponse([payload])

    def edit(self, **kwargs: object) -> object:
        self.calls.append({"method": "edit", "api_key": self._api_key, "kwargs": kwargs})
        payload = _ImagePayload(b64encode(f"{self._api_key}-edit".encode("utf-8")).decode("ascii"))
        return _ImageResponse([payload])


class _ImageResponse:
    def __init__(self, data: list[object]) -> None:
        self.data = data


class _ImagePayload:
    def __init__(self, b64_json: str) -> None:
        self.b64_json = b64_json


def _resolved_config(api_key: str) -> object:
    from temu_y2_women.image_provider_config import ResolvedOpenAIImageConfig

    return ResolvedOpenAIImageConfig(
        api_key=api_key,
        base_url="https://example.test",
        model="gpt-image-2",
        size="1024x1536",
        quality="high",
        background="auto",
        style="natural",
    )


def _render_input(
    prompt_id: str,
    *,
    render_strategy: str = "generate",
    reference_image_bytes: bytes | None = None,
) -> object:
    return type(
        "RenderInput",
        (),
        {
            "prompt": "test prompt",
            "prompt_id": prompt_id,
            "render_strategy": render_strategy,
            "reference_image_bytes": reference_image_bytes,
        },
    )()
