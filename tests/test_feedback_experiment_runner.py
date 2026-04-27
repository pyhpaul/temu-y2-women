from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


_REQUEST_FIXTURE_PATH = Path("tests/fixtures/requests/dress-generation-mvp/success-baseline-transitional-mode-a.json")
_ACTIVE_ELEMENTS_PATH = Path("data/mvp/dress/elements.json")
_ACTIVE_STRATEGIES_PATH = Path("data/mvp/dress/strategy_templates.json")
_TAXONOMY_PATH = Path("data/mvp/dress/evidence_taxonomy.json")
_LEDGER_PATH = Path("data/feedback/dress/feedback_ledger.json")


class EvidencePathOverrideTest(unittest.TestCase):
    def test_generate_dress_concept_uses_explicit_evidence_paths(self) -> None:
        from temu_y2_women.evidence_paths import EvidencePaths
        from temu_y2_women.orchestrator import generate_dress_concept

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            source_paths = _seed_source_bundle(temp_root, v_neck_score=0.90)
            payload = _read_json(_REQUEST_FIXTURE_PATH)

            result = generate_dress_concept(payload, evidence_paths=source_paths)

        v_neckline = _find_retrieved(result, "dress-neckline-v-neckline-001")
        self.assertEqual(v_neckline["effective_score"], 0.95)
        self.assertEqual(
            result["composed_concept"]["selected_elements"]["neckline"]["element_id"],
            "dress-neckline-v-neckline-001",
        )

    def test_evidence_paths_defaults_are_repo_root_anchored(self) -> None:
        from temu_y2_women.evidence_paths import EvidencePaths

        paths = EvidencePaths.defaults()

        self.assertTrue(paths.elements_path.is_absolute())
        self.assertTrue(paths.strategies_path.is_absolute())
        self.assertTrue(paths.taxonomy_path.is_absolute())

    def test_generate_dress_concept_default_paths_still_work(self) -> None:
        from temu_y2_women.orchestrator import generate_dress_concept

        result = generate_dress_concept(_read_json(_REQUEST_FIXTURE_PATH))

        self.assertEqual(
            result["composed_concept"]["selected_elements"]["neckline"]["element_id"],
            "dress-neckline-v-neckline-001",
        )


class FeedbackExperimentPrepareTest(unittest.TestCase):
    def test_prepare_feedback_experiment_creates_workspace_manifest_and_review(self) -> None:
        from unittest.mock import patch

        from temu_y2_women.evidence_paths import EvidencePaths
        from temu_y2_women.feedback_experiment_runner import (
            ExperimentSourcePaths,
            prepare_feedback_experiment,
        )

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            source_bundle = _seed_full_source_bundle(temp_root, v_neck_score=0.90)
            experiment_root = temp_root / "experiments"
            with patch(
                "temu_y2_women.feedback_experiment_runner._next_experiment_id",
                return_value="exp-fixed-001",
            ), patch(
                "temu_y2_women.feedback_experiment_runner._current_timestamp",
                return_value="2026-04-27T13:00:00Z",
            ):
                result = prepare_feedback_experiment(
                    request_path=_REQUEST_FIXTURE_PATH,
                    experiment_root=experiment_root,
                    workspace_name="baseline-v-neck",
                    source_paths=ExperimentSourcePaths(
                        evidence_paths=EvidencePaths(
                            elements_path=source_bundle["elements_path"],
                            strategies_path=source_bundle["strategies_path"],
                            taxonomy_path=source_bundle["taxonomy_path"],
                        ),
                        ledger_path=source_bundle["ledger_path"],
                    ),
                )

            manifest = _read_json(Path(result["manifest_path"]))
            baseline = _read_json(Path(result["baseline_result_path"]))
            review = _read_json(Path(result["feedback_review_path"]))
            self.assertEqual(result["experiment_id"], "exp-fixed-001")
            self.assertEqual(manifest["workspace_root"], str(experiment_root / "baseline-v-neck"))
            self.assertEqual(review["schema_version"], "feedback-review-v1")
            self.assertEqual(
                baseline["composed_concept"]["selected_elements"]["neckline"]["element_id"],
                "dress-neckline-v-neckline-001",
            )
            self.assertTrue((experiment_root / "baseline-v-neck" / "data" / "mvp" / "dress" / "elements.json").exists())
            self.assertTrue(
                (experiment_root / "baseline-v-neck" / "data" / "feedback" / "dress" / "feedback_ledger.json").exists()
            )


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _find_retrieved(result: dict[str, object], element_id: str) -> dict[str, object]:
    for item in result["retrieved_elements"]:
        if item["element_id"] == element_id:
            return item
    raise AssertionError(f"retrieved element not found: {element_id}")


def _seed_source_bundle(temp_root: Path, v_neck_score: float) -> "EvidencePaths":
    from temu_y2_women.evidence_paths import EvidencePaths

    elements_path = temp_root / "elements.json"
    strategies_path = temp_root / "strategy_templates.json"
    taxonomy_path = temp_root / "evidence_taxonomy.json"
    ledger_path = temp_root / "feedback_ledger.json"

    elements_payload = _read_json(_ACTIVE_ELEMENTS_PATH)
    for element in elements_payload["elements"]:
        if element["element_id"] == "dress-neckline-v-neckline-001":
            element["base_score"] = v_neck_score

    _write_json(elements_path, elements_payload)
    strategies_path.write_text(_ACTIVE_STRATEGIES_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    taxonomy_path.write_text(_TAXONOMY_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    ledger_path.write_text(_LEDGER_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    return EvidencePaths(
        elements_path=elements_path,
        strategies_path=strategies_path,
        taxonomy_path=taxonomy_path,
    )


def _seed_full_source_bundle(temp_root: Path, v_neck_score: float) -> dict[str, Path]:
    bundle_root = temp_root / "source"
    bundle_root.mkdir(parents=True, exist_ok=True)
    elements_path = bundle_root / "elements.json"
    strategies_path = bundle_root / "strategy_templates.json"
    taxonomy_path = bundle_root / "evidence_taxonomy.json"
    ledger_path = bundle_root / "feedback_ledger.json"

    elements_payload = _read_json(_ACTIVE_ELEMENTS_PATH)
    for element in elements_payload["elements"]:
        if element["element_id"] == "dress-neckline-v-neckline-001":
            element["base_score"] = v_neck_score

    _write_json(elements_path, elements_payload)
    strategies_path.write_text(_ACTIVE_STRATEGIES_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    taxonomy_path.write_text(_TAXONOMY_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    ledger_path.write_text(_LEDGER_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    return {
        "elements_path": elements_path,
        "strategies_path": strategies_path,
        "taxonomy_path": taxonomy_path,
        "ledger_path": ledger_path,
    }
