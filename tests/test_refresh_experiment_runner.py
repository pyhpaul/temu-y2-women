from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from temu_y2_women.evidence_paths import EvidencePaths


_REPO_ROOT = Path(__file__).resolve().parent.parent
_SUMMER_REQUEST_FIXTURE_PATH = _REPO_ROOT / "tests/fixtures/requests/dress-generation-mvp/success-summer-vacation-mode-a.json"
_SUMMER_B_REQUEST_FIXTURE_PATH = _REPO_ROOT / "tests/fixtures/requests/dress-generation-mvp/success-summer-vacation-mode-b.json"
_TRANSITIONAL_REQUEST_FIXTURE_PATH = _REPO_ROOT / "tests/fixtures/requests/dress-generation-mvp/success-baseline-transitional-mode-a.json"
_PROMOTION_FIXTURE_DIR = _REPO_ROOT / "tests/fixtures/promotion/dress"
_DATA_DIR = _REPO_ROOT / "data/mvp/dress"


class RefreshExperimentPrepareValidationTest(unittest.TestCase):
    def test_prepare_rejects_duplicate_request_ids(self) -> None:
        from temu_y2_women.refresh_experiment_runner import (
            RefreshExperimentSourcePaths,
            prepare_refresh_experiment,
        )

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            request_set_path = _write_request_set(
                temp_root,
                [
                    ("dup", _SUMMER_REQUEST_FIXTURE_PATH),
                    ("dup", _TRANSITIONAL_REQUEST_FIXTURE_PATH),
                ],
            )

            result = prepare_refresh_experiment(
                run_dir=_seed_refresh_run(temp_root, scenario="create"),
                request_set_path=request_set_path,
                experiment_root=temp_root / "experiments",
                source_paths=RefreshExperimentSourcePaths(
                    evidence_paths=_seed_experiment_source_bundle(temp_root),
                ),
            )

        self.assertEqual(result["error"]["code"], "INVALID_REFRESH_EXPERIMENT_INPUT")
        self.assertEqual(result["error"]["details"]["field"], "request_id")

    def test_prepare_rejects_workspace_name_outside_experiment_root(self) -> None:
        from temu_y2_women.refresh_experiment_runner import (
            RefreshExperimentSourcePaths,
            prepare_refresh_experiment,
        )

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            request_set_path = _write_request_set(
                temp_root,
                [("summer-vacation-a", _SUMMER_REQUEST_FIXTURE_PATH)],
            )
            result = prepare_refresh_experiment(
                run_dir=_seed_refresh_run(temp_root, scenario="create"),
                request_set_path=request_set_path,
                experiment_root=temp_root / "experiments",
                workspace_name="../escape",
                source_paths=RefreshExperimentSourcePaths(
                    evidence_paths=_seed_experiment_source_bundle(temp_root),
                ),
            )

        self.assertEqual(result["error"]["code"], "INVALID_REFRESH_EXPERIMENT_INPUT")
        self.assertEqual(result["error"]["details"]["field"], "workspace_name")

    def test_prepare_rejects_absolute_workspace_name(self) -> None:
        from temu_y2_women.refresh_experiment_runner import (
            RefreshExperimentSourcePaths,
            prepare_refresh_experiment,
        )

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            request_set_path = _write_request_set(
                temp_root,
                [("summer-vacation-a", _SUMMER_REQUEST_FIXTURE_PATH)],
            )
            result = prepare_refresh_experiment(
                run_dir=_seed_refresh_run(temp_root, scenario="create"),
                request_set_path=request_set_path,
                experiment_root=temp_root / "experiments",
                workspace_name=str(temp_root / "absolute-escape"),
                source_paths=RefreshExperimentSourcePaths(
                    evidence_paths=_seed_experiment_source_bundle(temp_root),
                ),
            )

        self.assertEqual(result["error"]["code"], "INVALID_REFRESH_EXPERIMENT_INPUT")
        self.assertEqual(result["error"]["details"]["field"], "workspace_name")


class RefreshExperimentPrepareTest(unittest.TestCase):
    def test_prepare_creates_workspace_manifest_review_and_baselines(self) -> None:
        from temu_y2_women.refresh_experiment_runner import (
            RefreshExperimentSourcePaths,
            prepare_refresh_experiment,
        )

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            request_set_path = _write_request_set(
                temp_root,
                [
                    ("summer-vacation-a", _SUMMER_REQUEST_FIXTURE_PATH),
                    ("summer-vacation-b", _SUMMER_B_REQUEST_FIXTURE_PATH),
                ],
            )
            with patch(
                "temu_y2_women.refresh_experiment_runner._next_experiment_id",
                return_value="exp-refresh-001",
            ), patch(
                "temu_y2_women.refresh_experiment_runner._current_timestamp",
                return_value="2026-04-28T12:00:00Z",
            ):
                result = prepare_refresh_experiment(
                    run_dir=_seed_refresh_run(temp_root, scenario="create"),
                    request_set_path=request_set_path,
                    experiment_root=temp_root / "experiments",
                    workspace_name="batch-a",
                    source_paths=RefreshExperimentSourcePaths(
                        evidence_paths=_seed_experiment_source_bundle(temp_root),
                    ),
                )

            manifest = _read_json(Path(result["manifest_path"]))
            review = _read_json(Path(result["promotion_review_path"]))
            baseline = _read_json(Path(result["baseline_dir"]) / "summer-vacation-a.json")

            self.assertEqual(result["experiment_id"], "exp-refresh-001")
            self.assertEqual(manifest["request_count"], 2)
            self.assertEqual(manifest["request_set_schema_version"], "refresh-experiment-request-set-v1")
            self.assertEqual(review["schema_version"], "promotion-review-v1")
            self.assertEqual(
                baseline["composed_concept"]["selected_elements"]["detail"]["element_id"],
                "dress-detail-smocked-bodice-001",
            )
            self.assertTrue((Path(result["workspace_root"]) / "data" / "mvp" / "dress" / "elements.json").exists())

    def test_prepare_records_absolute_manifest_paths_for_cross_cwd_apply(self) -> None:
        from temu_y2_women.refresh_experiment_runner import (
            RefreshExperimentSourcePaths,
            apply_refresh_experiment,
            prepare_refresh_experiment,
        )

        with TemporaryDirectory() as temp_dir, TemporaryDirectory() as other_dir:
            temp_root = Path(temp_dir)
            _seed_refresh_run(temp_root, scenario="create")
            request_set_path = _write_request_set(
                temp_root,
                [("summer-vacation-a", _SUMMER_REQUEST_FIXTURE_PATH)],
                use_relative_paths=True,
            )
            with _pushd(temp_root):
                prepared = prepare_refresh_experiment(
                    run_dir=Path("refresh-run"),
                    request_set_path=Path("request-set.json"),
                    experiment_root=Path("experiments"),
                    workspace_name="cross-cwd",
                    source_paths=RefreshExperimentSourcePaths(
                        evidence_paths=_seed_experiment_source_bundle(temp_root, use_relative_paths=True),
                    ),
                )
                _write_json(
                    temp_root / Path(prepared["promotion_review_path"]),
                    _read_json(_PROMOTION_FIXTURE_DIR / "create" / "reviewed_decisions.json"),
                )
                manifest_path = temp_root / Path(prepared["manifest_path"])
                manifest = _read_json(manifest_path)

            self.assertTrue(Path(manifest["run_dir"]).is_absolute())
            self.assertTrue(Path(manifest["workspace_root"]).is_absolute())
            self.assertTrue(Path(manifest["active_elements_path"]).is_absolute())
            self.assertTrue(Path(manifest["requests"][0]["baseline_result_path"]).is_absolute())

            with _pushd(Path(other_dir)):
                result = apply_refresh_experiment(manifest_path=manifest_path)

            self.assertIn("experiment_report_path", result)


class RefreshExperimentApplyTest(unittest.TestCase):
    def test_apply_uses_workspace_reviewed_by_default_and_writes_compare_reports(self) -> None:
        from temu_y2_women.refresh_experiment_runner import apply_refresh_experiment

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            source_paths = _seed_experiment_source_bundle(temp_root)
            prepared = _prepare_experiment(
                temp_root=temp_root,
                scenario="create",
                request_entries=[
                    ("summer-vacation-a", _SUMMER_REQUEST_FIXTURE_PATH),
                    ("transitional-a", _TRANSITIONAL_REQUEST_FIXTURE_PATH),
                ],
                source_paths=source_paths,
            )
            review_path = Path(prepared["promotion_review_path"])
            _write_json(review_path, _read_json(_PROMOTION_FIXTURE_DIR / "create" / "reviewed_decisions.json"))
            source_before = _read_json(source_paths.elements_path)

            result = apply_refresh_experiment(
                manifest_path=Path(prepared["manifest_path"]),
            )

            report = _read_json(Path(result["experiment_report_path"]))
            compare = _read_json(Path(result["compare_dir"]) / "summer-vacation-a.json")
            workspace_elements_path = Path(prepared["workspace_root"]) / "data" / "mvp" / "dress" / "elements.json"
            source_after = _read_json(source_paths.elements_path)
            workspace_after = _read_json(workspace_elements_path)

            self.assertEqual(report["request_count"], 2)
            self.assertEqual(report["change_summary"]["selection_changed"], 2)
            self.assertEqual(compare["change_type"], "selection_changed")
            self.assertEqual(
                compare["diff"]["selected_element_changes"]["detail"]["before"]["element_id"],
                "dress-detail-smocked-bodice-001",
            )
            self.assertEqual(
                compare["diff"]["selected_element_changes"]["detail"]["after"]["element_id"],
                "dress-detail-waist-tie-001",
            )
            self.assertIn("dress-detail-waist-tie-001", report["accepted_evidence_summary"]["element_ids"])
            self.assertEqual(source_after, source_before)
            self.assertNotEqual(workspace_after, source_before)

    def test_apply_fail_closed_rejects_invalid_review_and_does_not_write_compare_outputs(self) -> None:
        from temu_y2_women.refresh_experiment_runner import apply_refresh_experiment

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            prepared = _prepare_experiment(
                temp_root=temp_root,
                scenario="create",
                request_entries=[("summer-vacation-a", _SUMMER_REQUEST_FIXTURE_PATH)],
                source_paths=_seed_experiment_source_bundle(temp_root),
            )
            review_path = Path(prepared["promotion_review_path"])
            review_path.write_text("{", encoding="utf-8")

            result = apply_refresh_experiment(
                manifest_path=Path(prepared["manifest_path"]),
            )

        self.assertEqual(result["error"]["code"], "INVALID_PROMOTION_REVIEW")
        self.assertFalse((Path(prepared["workspace_root"]) / "compare").exists())
        self.assertFalse((Path(prepared["workspace_root"]) / "experiment_report.json").exists())

    def test_apply_rejects_tampered_manifest_paths_outside_workspace(self) -> None:
        from temu_y2_women.refresh_experiment_runner import apply_refresh_experiment

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            source_paths = _seed_experiment_source_bundle(temp_root)
            prepared = _prepare_experiment(
                temp_root=temp_root,
                scenario="create",
                request_entries=[("summer-vacation-a", _SUMMER_REQUEST_FIXTURE_PATH)],
                source_paths=source_paths,
            )
            review_path = Path(prepared["promotion_review_path"])
            _write_json(review_path, _read_json(_PROMOTION_FIXTURE_DIR / "create" / "reviewed_decisions.json"))
            manifest_path = Path(prepared["manifest_path"])
            manifest = _read_json(manifest_path)
            manifest["active_elements_path"] = str(source_paths.elements_path)
            _write_json(manifest_path, manifest)

            result = apply_refresh_experiment(manifest_path=manifest_path)

        self.assertEqual(result["error"]["code"], "INVALID_REFRESH_EXPERIMENT_INPUT")
        self.assertEqual(result["error"]["details"]["field"], "active_elements_path")

    def test_apply_rejects_request_payload_drift_after_prepare(self) -> None:
        from temu_y2_women.refresh_experiment_runner import apply_refresh_experiment

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            mutable_request = temp_root / "mutable-request.json"
            mutable_request.write_text(_SUMMER_REQUEST_FIXTURE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
            prepared = _prepare_experiment(
                temp_root=temp_root,
                scenario="create",
                request_entries=[("summer-vacation-a", mutable_request)],
                source_paths=_seed_experiment_source_bundle(temp_root),
            )
            review_path = Path(prepared["promotion_review_path"])
            _write_json(review_path, _read_json(_PROMOTION_FIXTURE_DIR / "create" / "reviewed_decisions.json"))
            payload = _read_json(mutable_request)
            payload["target_launch_date"] = "2026-07-01"
            _write_json(mutable_request, payload)

            result = apply_refresh_experiment(manifest_path=Path(prepared["manifest_path"]))

        self.assertEqual(result["error"]["code"], "INVALID_REFRESH_EXPERIMENT_INPUT")
        self.assertEqual(result["error"]["details"]["field"], "request_fingerprint")

    def test_apply_cleans_partial_outputs_when_compare_write_fails(self) -> None:
        from temu_y2_women.refresh_experiment_runner import apply_refresh_experiment

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            prepared = _prepare_experiment(
                temp_root=temp_root,
                scenario="create",
                request_entries=[
                    ("summer-vacation-a", _SUMMER_REQUEST_FIXTURE_PATH),
                    ("transitional-a", _TRANSITIONAL_REQUEST_FIXTURE_PATH),
                ],
                source_paths=_seed_experiment_source_bundle(temp_root),
            )
            review_path = Path(prepared["promotion_review_path"])
            _write_json(review_path, _read_json(_PROMOTION_FIXTURE_DIR / "create" / "reviewed_decisions.json"))
            module_write_json = "temu_y2_women.refresh_experiment_runner._write_json"

            def flaky_write(path: Path, payload: dict[str, object]) -> None:
                if path.parent.name.startswith(".compare") and path.name == "summer-vacation-a.json":
                    raise OSError("simulated compare write failure")
                _write_json(path, payload)

            with patch(module_write_json, side_effect=flaky_write):
                result = apply_refresh_experiment(manifest_path=Path(prepared["manifest_path"]))

            self.assertEqual(result["error"]["code"], "REFRESH_EXPERIMENT_FAILED")
            self.assertFalse((Path(prepared["workspace_root"]) / "compare").exists())
            self.assertFalse((Path(prepared["workspace_root"]) / "post_apply").exists())
            self.assertFalse((Path(prepared["workspace_root"]) / "experiment_report.json").exists())

    def test_apply_cleans_outputs_when_publish_replace_fails(self) -> None:
        from temu_y2_women.refresh_experiment_runner import apply_refresh_experiment

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            prepared = _prepare_experiment(
                temp_root=temp_root,
                scenario="create",
                request_entries=[("summer-vacation-a", _SUMMER_REQUEST_FIXTURE_PATH)],
                source_paths=_seed_experiment_source_bundle(temp_root),
            )
            review_path = Path(prepared["promotion_review_path"])
            _write_json(review_path, _read_json(_PROMOTION_FIXTURE_DIR / "create" / "reviewed_decisions.json"))
            call_count = 0
            original_replace = None

            def flaky_replace(destination: Path, source: Path) -> None:
                nonlocal call_count
                call_count += 1
                if call_count == 2:
                    raise OSError("simulated publish failure")
                original_replace(destination, source)

            original_replace = _load_replace_path()
            with patch("temu_y2_women.refresh_experiment_runner._replace_path", side_effect=flaky_replace):
                result = apply_refresh_experiment(manifest_path=Path(prepared["manifest_path"]))

            self.assertEqual(result["error"]["code"], "REFRESH_EXPERIMENT_FAILED")
            self.assertFalse((Path(prepared["workspace_root"]) / "compare").exists())
            self.assertFalse((Path(prepared["workspace_root"]) / "post_apply").exists())
            self.assertFalse((Path(prepared["workspace_root"]) / "experiment_report.json").exists())


def _prepare_experiment(
    temp_root: Path,
    scenario: str,
    request_entries: list[tuple[str, Path]],
    source_paths: EvidencePaths,
) -> dict[str, object]:
    from temu_y2_women.refresh_experiment_runner import (
        RefreshExperimentSourcePaths,
        prepare_refresh_experiment,
    )

    request_set_path = _write_request_set(temp_root, request_entries)
    with patch("temu_y2_women.refresh_experiment_runner._next_experiment_id", return_value="exp-refresh-002"), patch(
        "temu_y2_women.refresh_experiment_runner._current_timestamp",
        return_value="2026-04-28T12:10:00Z",
    ):
        return prepare_refresh_experiment(
            run_dir=_seed_refresh_run(temp_root, scenario=scenario),
            request_set_path=request_set_path,
            experiment_root=temp_root / "experiments",
            workspace_name="batch-apply",
            source_paths=RefreshExperimentSourcePaths(evidence_paths=source_paths),
        )


def _seed_experiment_source_bundle(temp_root: Path, use_relative_paths: bool = False) -> EvidencePaths:
    source_root = temp_root / "source" / "data" / "mvp" / "dress"
    source_root.mkdir(parents=True, exist_ok=True)
    for filename in ("elements.json", "strategy_templates.json", "evidence_taxonomy.json"):
        shutil.copyfile(_DATA_DIR / filename, source_root / filename)
    if use_relative_paths:
        return EvidencePaths(
            elements_path=Path("source/data/mvp/dress/elements.json"),
            strategies_path=Path("source/data/mvp/dress/strategy_templates.json"),
            taxonomy_path=Path("source/data/mvp/dress/evidence_taxonomy.json"),
        )
    return EvidencePaths(
        elements_path=source_root / "elements.json",
        strategies_path=source_root / "strategy_templates.json",
        taxonomy_path=source_root / "evidence_taxonomy.json",
    )


def _seed_refresh_run(temp_root: Path, scenario: str) -> Path:
    run_dir = temp_root / "refresh-run"
    run_dir.mkdir()
    for filename in ("draft_elements.json", "draft_strategy_hints.json", "reviewed_decisions.json"):
        source = _PROMOTION_FIXTURE_DIR / scenario / filename
        if source.exists():
            shutil.copyfile(source, run_dir / filename)
    (run_dir / "ingestion_report.json").write_text(
        json.dumps({"schema_version": "signal-ingestion-v1"}),
        encoding="utf-8",
    )
    (run_dir / "refresh_report.json").write_text(
        json.dumps({"schema_version": "public-signal-refresh-v1"}),
        encoding="utf-8",
    )
    return run_dir


def _write_request_set(
    temp_root: Path,
    request_entries: list[tuple[str, Path]],
    use_relative_paths: bool = False,
) -> Path:
    path = temp_root / "request-set.json"
    _write_json(
        path,
        {
            "schema_version": "refresh-experiment-request-set-v1",
            "category": "dress",
            "requests": [
                {
                    "request_id": request_id,
                    "request_path": str(os.path.relpath(request_path.resolve(), start=temp_root))
                    if use_relative_paths
                    else str(request_path.resolve()),
                }
                for request_id, request_path in request_entries
            ],
        },
    )
    return path


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_replace_path():
    from temu_y2_women import refresh_experiment_runner

    return refresh_experiment_runner._replace_path


@contextmanager
def _pushd(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)
