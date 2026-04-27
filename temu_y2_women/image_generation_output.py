from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from temu_y2_women.errors import GenerationError

_INVALID_INPUT_CODE = "INVALID_IMAGE_RENDER_INPUT"


@dataclass(frozen=True, slots=True)
class ImageRenderInput:
    source_result_path: Path
    category: str
    mode: str
    prompt: str
    render_notes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ImageProviderResult:
    image_bytes: bytes
    mime_type: str
    provider_name: str
    model: str


class ImageProvider(Protocol):
    def render(self, render_input: ImageRenderInput) -> ImageProviderResult:
        ...


class FakeImageProvider:
    def render(self, render_input: ImageRenderInput) -> ImageProviderResult:
        return ImageProviderResult(
            image_bytes=b"fake-image-provider-output",
            mime_type="image/png",
            provider_name="fake",
            model="fake-image-v1",
        )


def load_dress_image_render_input(result_path: Path) -> ImageRenderInput:
    payload = _load_json_object(result_path)
    request, prompt_bundle = _validated_success_payload(result_path, payload)
    return ImageRenderInput(
        source_result_path=result_path,
        category="dress",
        mode=str(prompt_bundle["mode"]),
        prompt=str(prompt_bundle["prompt"]),
        render_notes=_render_notes(result_path, prompt_bundle),
    )


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise _image_render_error(path, "result", "image render input must contain valid JSON") from error
    if isinstance(payload, dict):
        return payload
    raise _image_render_error(path, "result", "image render input root must be an object")


def _validated_success_payload(
    path: Path,
    payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if "error" in payload:
        raise _image_render_error(path, "result", "image render input must be a successful concept result")
    request = payload.get("request_normalized")
    if not isinstance(request, dict):
        raise _image_render_error(path, "request_normalized", "image render input is missing request_normalized")
    if request.get("category") != "dress":
        raise _image_render_error(path, "category", "image render input category is unsupported")
    prompt_bundle = payload.get("prompt_bundle")
    if not isinstance(prompt_bundle, dict):
        raise _image_render_error(path, "prompt_bundle", "image render input is missing prompt_bundle")
    if not isinstance(prompt_bundle.get("mode"), str) or not prompt_bundle["mode"].strip():
        raise _image_render_error(path, "mode", "image render input prompt_bundle mode must be a non-empty string")
    if not isinstance(prompt_bundle.get("prompt"), str) or not prompt_bundle["prompt"].strip():
        raise _image_render_error(path, "prompt", "image render input prompt_bundle prompt must be a non-empty string")
    return request, prompt_bundle


def _render_notes(path: Path, prompt_bundle: dict[str, Any]) -> tuple[str, ...]:
    notes = prompt_bundle.get("render_notes", [])
    if not isinstance(notes, list) or any(not isinstance(item, str) or not item.strip() for item in notes):
        raise _image_render_error(path, "render_notes", "image render input render_notes must be a list of non-empty strings")
    return tuple(item.strip() for item in notes)


def _image_render_error(path: Path, field: str, message: str) -> GenerationError:
    return GenerationError(
        code=_INVALID_INPUT_CODE,
        message=message,
        details={"path": str(path), "field": field},
    )
