from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

from tests.test_public_signal_refresh import _fixture_fetcher_by_url


_REQUEST_FIXTURE_PATH = Path("tests/fixtures/requests/dress-generation-mvp/success-summer-vacation-mode-a.json")


class GenerateAndRenderWorkflowSuccessTest(unittest.TestCase):
    def test_generate_and_render_writes_persisted_result_and_render_bundle(self) -> None:
        from temu_y2_women.generate_and_render_workflow import generate_and_render_dress_concept
        from temu_y2_women.image_generation_output import FakeImageProvider
        from temu_y2_women.orchestrator import generate_dress_concept

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "render-output"
            result = generate_and_render_dress_concept(
                request_path=_REQUEST_FIXTURE_PATH,
                output_dir=output_dir,
                provider_factory=lambda: FakeImageProvider(),
            )

            concept_result = _read_json(output_dir / "concept_result.json")
            expected_concept_result = generate_dress_concept(_read_json(_REQUEST_FIXTURE_PATH))

            self.assertEqual(result["provider"], "fake")
            self.assertEqual(result["model"], "fake-image-v1")
            self.assertEqual(result["source_result_path"], str(output_dir / "concept_result.json"))
            self.assertEqual(concept_result, expected_concept_result)
            self.assertEqual(concept_result["factory_spec"]["schema_version"], "factory-spec-v1")
            self.assertEqual(concept_result["prompt_bundle"]["render_jobs"][0]["render_strategy"], "generate")
            self.assertIsNone(concept_result["prompt_bundle"]["render_jobs"][0]["reference_prompt_id"])
            self.assertEqual(concept_result["prompt_bundle"]["render_jobs"][1]["render_strategy"], "edit")
            self.assertEqual(concept_result["prompt_bundle"]["render_jobs"][1]["reference_prompt_id"], "hero_front")
            self.assertEqual(
                tuple(image["output_name"] for image in result["images"]),
                (
                    "hero_front.png",
                    "hero_three_quarter.png",
                    "hero_back.png",
                    "construction_closeup.png",
                    "fabric_print_closeup.png",
                    "hem_and_drape_closeup.png",
                ),
            )
            self.assertEqual(len(result["images"]), 6)
            self.assertTrue((output_dir / "hero_front.png").exists())
            self.assertTrue((output_dir / "hero_three_quarter.png").exists())
            self.assertTrue((output_dir / "hero_back.png").exists())
            self.assertTrue((output_dir / "construction_closeup.png").exists())
            self.assertTrue((output_dir / "fabric_print_closeup.png").exists())
            self.assertTrue((output_dir / "hem_and_drape_closeup.png").exists())
            self.assertTrue((output_dir / "image_render_report.json").exists())
            self.assertEqual(_read_json(output_dir / "image_render_report.json"), result)
            self.assertFalse((output_dir / "concept_result.json.tmp").exists())

    def test_generate_and_render_can_use_refresh_experiment_evidence_snapshot(self) -> None:
        from temu_y2_women.generate_and_render_workflow import generate_and_render_dress_concept
        from temu_y2_women.public_signal_refresh import run_public_signal_refresh
        from temu_y2_women.refresh_experiment_runner import (
            apply_refresh_experiment,
            prepare_refresh_experiment,
        )

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            refresh = run_public_signal_refresh(
                registry_path=Path("data/refresh/dress/source_registry.json"),
                output_root=temp_root,
                fetched_at="2026-04-30T00:00:00Z",
                fetcher=_fixture_fetcher_by_url(),
            )
            prepared = prepare_refresh_experiment(
                run_dir=temp_root / refresh["run_id"],
                request_set_path=Path("tests/fixtures/refresh_experiment/request_set.json"),
                experiment_root=temp_root / "experiments",
                workspace_name="render-workflow",
            )
            apply_refresh_experiment(
                manifest_path=Path(prepared["manifest_path"]),
                auto_accept_pending=True,
            )
            workspace_root = Path(prepared["workspace_root"])
            output_dir = temp_root / "render-output"

            result = generate_and_render_dress_concept(
                request_path=_REQUEST_FIXTURE_PATH,
                output_dir=output_dir,
                provider_factory=lambda: _RecordingProvider(),
                evidence_paths=_workspace_evidence_paths(workspace_root),
            )

            concept_result = _read_json(output_dir / "concept_result.json")
            self.assertEqual(result["provider"], "recording")
            self.assertEqual(concept_result["selected_strategies"][0]["strategy_id"], "dress-us-summer-vacation")
            self.assertEqual(
                concept_result["composed_concept"]["selected_elements"]["neckline"]["value"],
                "v-neckline",
            )
            self.assertTrue((output_dir / "hero_front.png").exists())


class GenerateAndRenderWorkflowFailureTest(unittest.TestCase):
    def test_generate_and_render_rejects_non_object_request_payload(self) -> None:
        from temu_y2_women.generate_and_render_workflow import generate_and_render_dress_concept
        from temu_y2_women.image_generation_output import FakeImageProvider

        with TemporaryDirectory() as temp_dir:
            request_path = Path(temp_dir) / "request.json"
            request_path.write_text("[]", encoding="utf-8")
            output_dir = Path(temp_dir) / "render-output"
            result = generate_and_render_dress_concept(
                request_path=request_path,
                output_dir=output_dir,
                provider_factory=lambda: FakeImageProvider(),
            )

            self.assertEqual(result["error"]["code"], "INVALID_GENERATE_AND_RENDER_INPUT")
            self.assertFalse(output_dir.exists())

    def test_generate_and_render_rejects_non_utf8_request_payload(self) -> None:
        from temu_y2_women.generate_and_render_workflow import generate_and_render_dress_concept
        from temu_y2_women.image_generation_output import FakeImageProvider

        with TemporaryDirectory() as temp_dir:
            request_path = Path(temp_dir) / "request.json"
            request_path.write_bytes(b"\xff\xfe\x80invalid")
            output_dir = Path(temp_dir) / "render-output"
            result = generate_and_render_dress_concept(
                request_path=request_path,
                output_dir=output_dir,
                provider_factory=lambda: FakeImageProvider(),
            )

            self.assertEqual(result["error"]["code"], "INVALID_GENERATE_AND_RENDER_INPUT")
            self.assertFalse(output_dir.exists())

    def test_generate_and_render_returns_generation_error_without_outputs(self) -> None:
        from temu_y2_women.generate_and_render_workflow import generate_and_render_dress_concept
        from temu_y2_women.image_generation_output import FakeImageProvider

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "render-output"
            result = generate_and_render_dress_concept(
                request_path=Path("tests/fixtures/requests/dress-generation-mvp/failure-no-candidates-summer-vacation.json"),
                output_dir=output_dir,
                provider_factory=lambda: FakeImageProvider(),
            )

            self.assertEqual(result["error"]["code"], "NO_CANDIDATES")
            self.assertFalse(output_dir.exists())

    def test_generate_and_render_returns_concept_result_output_error(self) -> None:
        from temu_y2_women.generate_and_render_workflow import generate_and_render_dress_concept
        from temu_y2_women.image_generation_output import FakeImageProvider

        with TemporaryDirectory() as temp_dir:
            occupied_path = Path(temp_dir) / "occupied"
            occupied_path.write_text("not-a-directory", encoding="utf-8")
            result = generate_and_render_dress_concept(
                request_path=_REQUEST_FIXTURE_PATH,
                output_dir=occupied_path,
                provider_factory=lambda: FakeImageProvider(),
            )

            self.assertEqual(result["error"]["code"], "CONCEPT_RESULT_OUTPUT_FAILED")
            self.assertEqual(result["error"]["details"]["path"], str(occupied_path))
            self.assertTrue(occupied_path.is_file())
            self.assertEqual(occupied_path.read_text(encoding="utf-8"), "not-a-directory")

    def test_generate_and_render_preserves_concept_result_when_render_fails(self) -> None:
        from temu_y2_women.generate_and_render_workflow import generate_and_render_dress_concept

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "render-output"
            result = generate_and_render_dress_concept(
                request_path=_REQUEST_FIXTURE_PATH,
                output_dir=output_dir,
                provider_factory=lambda: _ExplodingProvider(),
            )

            self.assertEqual(result["error"]["code"], "IMAGE_PROVIDER_FAILED")
            self.assertTrue((output_dir / "concept_result.json").exists())
            self.assertFalse((output_dir / "hero_front.png").exists())
            self.assertFalse((output_dir / "image_render_report.json").exists())

    def test_generate_and_render_cleans_temp_file_when_concept_result_write_fails(self) -> None:
        from temu_y2_women.generate_and_render_workflow import generate_and_render_dress_concept
        from temu_y2_women.image_generation_output import FakeImageProvider

        original_write_text = Path.write_text

        def exploding_write_text(path: Path, data: str, *args: object, **kwargs: object) -> int:
            if path.name == "concept_result.json.tmp":
                original_write_text(path, "partial", *args, **kwargs)
                raise OSError(5, "disk full", str(path))
            return original_write_text(path, data, *args, **kwargs)

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "render-output"
            with mock.patch.object(Path, "write_text", autospec=True, side_effect=exploding_write_text):
                result = generate_and_render_dress_concept(
                    request_path=_REQUEST_FIXTURE_PATH,
                    output_dir=output_dir,
                    provider_factory=lambda: FakeImageProvider(),
                )

            self.assertEqual(result["error"]["code"], "CONCEPT_RESULT_OUTPUT_FAILED")
            self.assertEqual(result["error"]["details"]["path"], str(output_dir / "concept_result.json.tmp"))
            self.assertFalse((output_dir / "concept_result.json.tmp").exists())
            self.assertFalse((output_dir / "concept_result.json").exists())

    def test_generate_and_render_returns_structured_error_when_provider_factory_fails(self) -> None:
        from temu_y2_women.generate_and_render_workflow import generate_and_render_dress_concept

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "render-output"
            result = generate_and_render_dress_concept(
                request_path=_REQUEST_FIXTURE_PATH,
                output_dir=output_dir,
                provider_factory=_raising_os_error_provider_factory,
            )

            self.assertEqual(result["error"]["code"], "IMAGE_PROVIDER_FAILED")
            self.assertEqual(result["error"]["details"]["stage"], "provider_factory")
            self.assertIn("provider factory failed", result["error"]["details"]["reason"])
            self.assertTrue((output_dir / "concept_result.json").exists())
            self.assertFalse((output_dir / "concept_result.json.tmp").exists())
            self.assertFalse((output_dir / "hero_front.png").exists())
            self.assertFalse((output_dir / "image_render_report.json").exists())


class _ExplodingProvider:
    def render(self, render_input: object) -> object:
        raise RuntimeError("provider boom")


class _RecordingProvider:
    def render(self, render_input: object) -> object:
        from temu_y2_women.image_generation_output import ImageProviderResult

        return ImageProviderResult(
            image_bytes=b"recording-provider-output",
            mime_type="image/png",
            provider_name="recording",
            model="recording-v1",
        )


def _raising_os_error_provider_factory() -> object:
    raise OSError(13, "provider factory failed", "provider-factory")


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _workspace_evidence_paths(workspace_root: Path):
    from temu_y2_women.evidence_paths import EvidencePaths

    evidence_root = workspace_root / "data" / "mvp" / "dress"
    return EvidencePaths(
        elements_path=evidence_root / "elements.json",
        strategies_path=evidence_root / "strategy_templates.json",
        taxonomy_path=evidence_root / "evidence_taxonomy.json",
    )
