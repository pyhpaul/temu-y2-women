from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


_REQUEST_FIXTURE_PATH = Path("tests/fixtures/requests/dress-generation-mvp/success-summer-vacation-mode-a.json")
_FAILURE_FIXTURE_PATH = Path("tests/fixtures/requests/dress-generation-mvp/failure-no-candidates-summer-vacation.json")


class GenerateAndRenderWorkflowSuccessTest(unittest.TestCase):
    def test_generate_and_render_writes_persisted_result_and_render_bundle(self) -> None:
        from temu_y2_women.generate_and_render_workflow import generate_and_render_dress_concept
        from temu_y2_women.image_generation_output import FakeImageProvider

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "render-output"
            result = generate_and_render_dress_concept(
                request_path=_REQUEST_FIXTURE_PATH,
                output_dir=output_dir,
                provider_factory=lambda: FakeImageProvider(),
            )

            concept_result = _read_json(output_dir / "concept_result.json")

            self.assertEqual(result["provider"], "fake")
            self.assertEqual(result["model"], "fake-image-v1")
            self.assertEqual(result["source_result_path"], str(output_dir / "concept_result.json"))
            self.assertEqual(concept_result["prompt_bundle"]["mode"], "A")
            self.assertTrue((output_dir / "rendered_image.png").exists())
            self.assertTrue((output_dir / "image_render_report.json").exists())
            self.assertEqual(_read_json(output_dir / "image_render_report.json"), result)


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))
