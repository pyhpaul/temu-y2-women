from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from temu_y2_women.errors import GenerationError


_RESULT_FIXTURE_PATH = Path("tests/fixtures/feedback/dress/result_success.json")


class ImageRenderInputTest(unittest.TestCase):
    def test_load_dress_image_render_input_accepts_successful_result(self) -> None:
        from temu_y2_women.image_generation_output import load_dress_image_render_input

        render_input = load_dress_image_render_input(_RESULT_FIXTURE_PATH)

        self.assertEqual(render_input.category, "dress")
        self.assertEqual(render_input.mode, "A")
        self.assertIn("product-first presentation", render_input.prompt)
        self.assertEqual(
            render_input.render_notes,
            ("prioritize product-first presentation", "keep garment construction realistic"),
        )

    def test_load_dress_image_render_input_rejects_error_payload(self) -> None:
        from temu_y2_women.image_generation_output import load_dress_image_render_input

        with TemporaryDirectory() as temp_dir:
            invalid_path = Path(temp_dir) / "error.json"
            invalid_path.write_text(
                json.dumps({"error": {"code": "NO_CANDIDATES", "message": "bad", "details": {}}}),
                encoding="utf-8",
            )

            with self.assertRaises(GenerationError) as error_context:
                load_dress_image_render_input(invalid_path)

        self.assertEqual(error_context.exception.code, "INVALID_IMAGE_RENDER_INPUT")
        self.assertEqual(error_context.exception.details["field"], "result")

    def test_load_dress_image_render_input_rejects_missing_prompt_bundle(self) -> None:
        from temu_y2_women.image_generation_output import load_dress_image_render_input

        with TemporaryDirectory() as temp_dir:
            invalid_path = Path(temp_dir) / "missing-prompt.json"
            payload = _read_json(_RESULT_FIXTURE_PATH)
            payload.pop("prompt_bundle")
            _write_json(invalid_path, payload)

            with self.assertRaises(GenerationError) as error_context:
                load_dress_image_render_input(invalid_path)

        self.assertEqual(error_context.exception.code, "INVALID_IMAGE_RENDER_INPUT")
        self.assertEqual(error_context.exception.details["field"], "prompt_bundle")


class FakeImageProviderTest(unittest.TestCase):
    def test_fake_image_provider_returns_stable_bytes_and_metadata(self) -> None:
        from temu_y2_women.image_generation_output import FakeImageProvider, load_dress_image_render_input

        render_input = load_dress_image_render_input(_RESULT_FIXTURE_PATH)
        result = FakeImageProvider().render(render_input)

        self.assertEqual(result.image_bytes, b"fake-image-provider-output")
        self.assertEqual(result.mime_type, "image/png")
        self.assertEqual(result.provider_name, "fake")
        self.assertEqual(result.model, "fake-image-v1")


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
