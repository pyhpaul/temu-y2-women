from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


_RESULT_FIXTURE_PATH = Path("tests/fixtures/feedback/dress/result_success.json")


class ImageRenderWorkflowTest(unittest.TestCase):
    def test_render_dress_concept_image_writes_six_image_bundle_and_report(self) -> None:
        from temu_y2_women.image_generation_output import FakeImageProvider
        from temu_y2_women.image_generation_workflow import render_dress_concept_image

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "render-output"
            result_path = Path(temp_dir) / "bundle-result.json"
            _write_json(result_path, _bundle_result_payload())
            result = render_dress_concept_image(
                result_path=result_path,
                output_dir=output_dir,
                provider=FakeImageProvider(),
            )

            self.assertEqual(result["provider"], "fake")
            self.assertEqual(result["model"], "fake-image-v1")
            self.assertEqual(result["mode"], "A")
            self.assertEqual(result["image_path"], str(output_dir / "hero_front.png"))
            self.assertEqual(len(result["images"]), 6)
            self.assertEqual(result["images"][0]["prompt_id"], "hero_front")
            self.assertEqual(result["images"][0]["output_name"], "hero_front.png")
            self.assertTrue((output_dir / "hero_front.png").exists())
            self.assertTrue((output_dir / "hero_three_quarter.png").exists())
            self.assertTrue((output_dir / "hero_back.png").exists())
            self.assertTrue((output_dir / "construction_closeup.png").exists())
            self.assertTrue((output_dir / "fabric_print_closeup.png").exists())
            self.assertTrue((output_dir / "hem_and_drape_closeup.png").exists())
            self.assertTrue((output_dir / "image_render_report.json").exists())
            self.assertEqual(
                (output_dir / "hero_front.png").read_bytes(),
                b"fake-image-provider-output",
            )
            self.assertEqual(
                _read_json(output_dir / "image_render_report.json"),
                result,
            )

    def test_render_dress_concept_image_falls_back_to_legacy_single_image(self) -> None:
        from temu_y2_women.image_generation_output import FakeImageProvider
        from temu_y2_women.image_generation_workflow import render_dress_concept_image

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "render-output"
            result = render_dress_concept_image(
                result_path=_RESULT_FIXTURE_PATH,
                output_dir=output_dir,
                provider=FakeImageProvider(),
            )

        self.assertEqual(result["image_path"], str(output_dir / "rendered_image.png"))
        self.assertEqual(
            result["images"],
            [
                {
                    "prompt_id": "hero_front",
                    "group": "hero",
                    "output_name": "rendered_image.png",
                    "prompt_fingerprint": result["images"][0]["prompt_fingerprint"],
                    "image_path": str(output_dir / "rendered_image.png"),
                }
            ],
        )

    def test_render_dress_concept_image_returns_provider_error_without_outputs(self) -> None:
        from temu_y2_women.image_generation_workflow import render_dress_concept_image

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "render-output"
            result_path = Path(temp_dir) / "bundle-result.json"
            _write_json(result_path, _bundle_result_payload())
            result = render_dress_concept_image(
                result_path=result_path,
                output_dir=output_dir,
                provider=_FailingOnPromptProvider("construction_closeup"),
            )

            self.assertEqual(result["error"]["code"], "IMAGE_PROVIDER_FAILED")
            self.assertFalse((output_dir / "hero_front.png").exists())
            self.assertFalse((output_dir / "hero_three_quarter.png").exists())
            self.assertFalse((output_dir / "image_render_report.json").exists())

    def test_render_dress_concept_image_rolls_back_when_output_publication_fails(self) -> None:
        from temu_y2_women.image_generation_output import FakeImageProvider
        from temu_y2_women.image_generation_workflow import render_dress_concept_image

        with TemporaryDirectory() as temp_dir:
            occupied_path = Path(temp_dir) / "occupied"
            occupied_path.write_text("not-a-directory", encoding="utf-8")
            result_path = Path(temp_dir) / "bundle-result.json"
            _write_json(result_path, _bundle_result_payload())
            result = render_dress_concept_image(
                result_path=result_path,
                output_dir=occupied_path,
                provider=FakeImageProvider(),
            )

            self.assertEqual(result["error"]["code"], "IMAGE_RENDER_OUTPUT_FAILED")
            self.assertTrue(occupied_path.is_file())
            self.assertEqual(occupied_path.read_text(encoding="utf-8"), "not-a-directory")


class _FailingOnPromptProvider:
    def __init__(self, prompt_id: str) -> None:
        self._prompt_id = prompt_id

    def render(self, render_input: object) -> object:
        if getattr(render_input, "prompt_id") == self._prompt_id:
            raise RuntimeError("provider boom")
        return _provider_result()


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
    return payload


def _provider_result() -> object:
    from temu_y2_women.image_generation_output import ImageProviderResult

    return ImageProviderResult(
        image_bytes=b"fake-image-provider-output",
        mime_type="image/png",
        provider_name="fake",
        model="fake-image-v1",
    )
