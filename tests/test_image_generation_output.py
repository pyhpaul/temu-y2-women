from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from temu_y2_women.errors import GenerationError


_RESULT_FIXTURE_PATH = Path("tests/fixtures/feedback/dress/result_success.json")


class ImageRenderInputTest(unittest.TestCase):
    def test_result_fixture_carries_richer_factory_spec_draft_fields(self) -> None:
        payload = _read_json(_RESULT_FIXTURE_PATH)
        inferred = payload["factory_spec"]["inferred"]

        self.assertIn("sample_review_watchpoints", inferred)
        self.assertIn("qa_review_notes", inferred)
        self.assertIn("fit_review_cues", inferred)
        self.assertIn("commercial_review_cues", inferred)
        self.assertIn("visible_construction_checks", inferred)
        self.assertIn("open_questions", inferred)

    def test_load_dress_image_render_input_accepts_successful_result(self) -> None:
        from temu_y2_women.image_generation_output import load_dress_image_render_input

        render_input = load_dress_image_render_input(_RESULT_FIXTURE_PATH)

        self.assertEqual(render_input.category, "dress")
        self.assertEqual(render_input.mode, "A")
        self.assertIn("product-first presentation", render_input.prompt)
        self.assertEqual(len(render_input.render_jobs), 1)
        self.assertEqual(render_input.render_jobs[0].prompt_id, "hero_front")
        self.assertEqual(render_input.render_jobs[0].group, "hero")
        self.assertEqual(render_input.render_jobs[0].output_name, "rendered_image.png")
        self.assertEqual(
            render_input.render_notes,
            ("prioritize product-first presentation", "keep garment construction realistic"),
        )

    def test_load_dress_image_render_input_prefers_render_jobs_when_present(self) -> None:
        from temu_y2_women.image_generation_output import load_dress_image_render_input

        with TemporaryDirectory() as temp_dir:
            result_path = Path(temp_dir) / "bundle-result.json"
            _write_json(result_path, _bundle_result_payload())

            render_input = load_dress_image_render_input(result_path)

        self.assertEqual(render_input.prompt, "hero front prompt")
        self.assertEqual(
            [(job.prompt_id, job.group, job.output_name) for job in render_input.render_jobs],
            [
                ("hero_front", "hero", "hero_front.png"),
                ("hero_three_quarter", "hero", "hero_three_quarter.png"),
                ("hero_back", "hero", "hero_back.png"),
                ("construction_closeup", "detail", "construction_closeup.png"),
                ("fabric_print_closeup", "detail", "fabric_print_closeup.png"),
                ("hem_and_drape_closeup", "detail", "hem_and_drape_closeup.png"),
            ],
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


def _bundle_result_payload() -> dict[str, object]:
    payload = _read_json(_RESULT_FIXTURE_PATH)
    payload["prompt_bundle"]["render_jobs"] = [
        {
            "prompt_id": "hero_front",
            "group": "hero",
            "output_name": "hero_front.png",
            "prompt": "hero front prompt",
        },
        {
            "prompt_id": "hero_three_quarter",
            "group": "hero",
            "output_name": "hero_three_quarter.png",
            "prompt": "hero three quarter prompt",
        },
        {
            "prompt_id": "hero_back",
            "group": "hero",
            "output_name": "hero_back.png",
            "prompt": "hero back prompt",
        },
        {
            "prompt_id": "construction_closeup",
            "group": "detail",
            "output_name": "construction_closeup.png",
            "prompt": "construction prompt",
        },
        {
            "prompt_id": "fabric_print_closeup",
            "group": "detail",
            "output_name": "fabric_print_closeup.png",
            "prompt": "fabric prompt",
        },
        {
            "prompt_id": "hem_and_drape_closeup",
            "group": "detail",
            "output_name": "hem_and_drape_closeup.png",
            "prompt": "hem prompt",
        },
    ]
    payload["prompt_bundle"]["prompt"] = "legacy hero prompt should be ignored"
    return payload
