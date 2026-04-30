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
        expansion_result = provider.render(
            _render_input("hero_back", render_strategy="edit", reference_image_bytes=b"anchor-image")
        )

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

    def test_build_openai_image_provider_uses_curl_transport_for_callxyq_generation(self) -> None:
        from temu_y2_women.image_generation_openai import build_openai_image_provider

        captured: dict[str, object] = {}

        provider = build_openai_image_provider(
            _resolved_config("anchor-key", base_url="https://callxyq.xyz/v1"),
            client_factory=_unexpected_client_factory,
            curl_runner=_curl_runner_with_json_response(captured, _png_payload("callxyq-generate")),
        )

        result = provider.render(_render_input("hero_front"))

        self.assertEqual(result.image_bytes, b"callxyq-generate")
        self.assertEqual(result.base_url, "https://callxyq.xyz/v1")
        self.assertEqual(captured["input"], '{"model":"gpt-image-2","prompt":"test prompt","response_format":"b64_json"}')
        self.assertIn("https://callxyq.xyz/v1/images/generations", captured["command"])
        self.assertIn("Authorization: Bearer anchor-key", captured["command"])

    def test_build_openai_image_provider_downloads_url_payload_for_callxyq_edit(self) -> None:
        from temu_y2_women.image_generation_openai import build_openai_image_provider

        captured: dict[str, object] = {}

        provider = build_openai_image_provider(
            _resolved_config("expansion-key", base_url="https://callxyq.xyz/v1"),
            client_factory=_unexpected_client_factory,
            curl_runner=_curl_runner_with_edit_url_response(captured),
        )

        result = provider.render(
            _render_input(
                "hero_back",
                render_strategy="edit",
                reference_image_bytes=b"anchor-image",
            )
        )

        self.assertEqual(result.image_bytes, b"callxyq-edit")
        self.assertEqual(len(captured["commands"]), 2)
        self.assertIn("https://callxyq.xyz/v1/images/edits", captured["commands"][0])
        self.assertIn("https://asset.callxyq.test/final.png", captured["commands"][1])
        self.assertIn("-F model=gpt-image-2", " ".join(captured["commands"][0]))
        self.assertIn("-F prompt=test prompt", " ".join(captured["commands"][0]))
        self.assertIn("-F response_format=b64_json", " ".join(captured["commands"][0]))
        self.assertIn("-F input_fidelity=high", " ".join(captured["commands"][0]))
        self.assertNotIn("size=1024x1536", " ".join(captured["commands"][0]))
        self.assertNotIn("quality=high", " ".join(captured["commands"][0]))
        self.assertNotIn("background=auto", " ".join(captured["commands"][0]))
        self.assertNotIn("output_format=png", " ".join(captured["commands"][0]))

    def test_build_openai_image_provider_surfaces_callxyq_edit_gateway_block_hint(self) -> None:
        from temu_y2_women.image_generation_openai import build_openai_image_provider

        provider = build_openai_image_provider(
            _resolved_config("expansion-key", base_url="https://callxyq.xyz/v1"),
            client_factory=_unexpected_client_factory,
            curl_runner=_curl_runner_with_http_error("<html><body>forbidden</body></html>", 403),
        )

        with self.assertRaises(GenerationError) as error_context:
            provider.render(
                _render_input(
                    "hero_back",
                    render_strategy="edit",
                    reference_image_bytes=b"anchor-image",
                )
            )

        details = error_context.exception.details
        self.assertEqual(details["gateway_host"], "callxyq.xyz")
        self.assertEqual(details["gateway_route"], "/images/edits")
        self.assertEqual(details["http_code"], 403)
        self.assertEqual(details["reason_type"], "html_response")
        self.assertEqual(details["gateway_error_category"], "gateway_reference_image_blocked")
        self.assertIn("real garment reference images", details["hint"])


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


class _CompletedProcess:
    def __init__(self, stdout: str | bytes, stderr: str = "", returncode: int = 0) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def _resolved_config(api_key: str, *, base_url: str = "https://example.test") -> object:
    from temu_y2_women.image_provider_config import ResolvedOpenAIImageConfig

    return ResolvedOpenAIImageConfig(
        api_key=api_key,
        base_url=base_url,
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


def _unexpected_client_factory(**_: str) -> object:
    raise AssertionError("OpenAI SDK transport should not be used for callxyq")


def _curl_runner_with_json_response(captured: dict[str, object], payload: str):
    def _runner(command: list[str], **kwargs: object) -> _CompletedProcess:
        captured["command"] = command
        captured["input"] = kwargs.get("input")
        return _CompletedProcess(f"{payload}\nHTTP_CODE:200")

    return _runner


def _curl_runner_with_edit_url_response(captured: dict[str, object]):
    commands: list[list[str]] = []
    captured["commands"] = commands

    def _runner(command: list[str], **kwargs: object) -> _CompletedProcess:
        commands.append(command)
        if len(commands) == 1:
            payload = '{"data":[{"url":"https://asset.callxyq.test/final.png","b64_json":""}]}'
            return _CompletedProcess(f"{payload}\nHTTP_CODE:200")
        return _CompletedProcess(b"callxyq-edit")

    return _runner


def _curl_runner_with_http_error(body_text: str, http_code: int):
    def _runner(command: list[str], **kwargs: object) -> _CompletedProcess:
        return _CompletedProcess(f"{body_text}\nHTTP_CODE:{http_code}")

    return _runner


def _png_payload(value: str) -> str:
    encoded = b64encode(value.encode("utf-8")).decode("ascii")
    return f'{{"data":[{{"b64_json":"{encoded}"}}]}}'
