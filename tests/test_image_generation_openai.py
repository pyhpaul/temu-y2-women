from __future__ import annotations

import unittest

from temu_y2_women.errors import GenerationError


class OpenAIImageProviderConfigTest(unittest.TestCase):
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


class _FakeClient:
    def __init__(self) -> None:
        self.images = _FakeImages()


class _FakeImages:
    def generate(self, **kwargs: str) -> object:
        return object()
