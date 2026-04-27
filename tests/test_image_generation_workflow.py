from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


_RESULT_FIXTURE_PATH = Path("tests/fixtures/feedback/dress/result_success.json")


class ImageRenderWorkflowTest(unittest.TestCase):
    def test_render_dress_concept_image_writes_image_and_report(self) -> None:
        from temu_y2_women.image_generation_output import FakeImageProvider
        from temu_y2_women.image_generation_workflow import render_dress_concept_image

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "render-output"
            result = render_dress_concept_image(
                result_path=_RESULT_FIXTURE_PATH,
                output_dir=output_dir,
                provider=FakeImageProvider(),
            )

            self.assertEqual(result["provider"], "fake")
            self.assertEqual(result["model"], "fake-image-v1")
            self.assertEqual(result["mode"], "A")
            self.assertTrue((output_dir / "rendered_image.png").exists())
            self.assertTrue((output_dir / "image_render_report.json").exists())
            self.assertEqual(
                (output_dir / "rendered_image.png").read_bytes(),
                b"fake-image-provider-output",
            )
            self.assertEqual(
                _read_json(output_dir / "image_render_report.json"),
                result,
            )

    def test_render_dress_concept_image_returns_provider_error_without_outputs(self) -> None:
        from temu_y2_women.image_generation_workflow import render_dress_concept_image

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "render-output"
            result = render_dress_concept_image(
                result_path=_RESULT_FIXTURE_PATH,
                output_dir=output_dir,
                provider=_ExplodingProvider(),
            )

            self.assertEqual(result["error"]["code"], "IMAGE_PROVIDER_FAILED")
            self.assertFalse((output_dir / "rendered_image.png").exists())
            self.assertFalse((output_dir / "image_render_report.json").exists())

    def test_render_dress_concept_image_rolls_back_when_output_publication_fails(self) -> None:
        from temu_y2_women.image_generation_output import FakeImageProvider
        from temu_y2_women.image_generation_workflow import render_dress_concept_image

        with TemporaryDirectory() as temp_dir:
            occupied_path = Path(temp_dir) / "occupied"
            occupied_path.write_text("not-a-directory", encoding="utf-8")
            result = render_dress_concept_image(
                result_path=_RESULT_FIXTURE_PATH,
                output_dir=occupied_path,
                provider=FakeImageProvider(),
            )

            self.assertEqual(result["error"]["code"], "IMAGE_RENDER_OUTPUT_FAILED")
            self.assertTrue(occupied_path.is_file())
            self.assertEqual(occupied_path.read_text(encoding="utf-8"), "not-a-directory")


class _ExplodingProvider:
    def render(self, render_input: object) -> object:
        raise RuntimeError("provider boom")


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))
