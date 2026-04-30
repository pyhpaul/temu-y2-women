from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tests.test_public_signal_refresh import _fixture_fetcher_by_url


_REQUEST_SET_PATH = Path("tests/fixtures/refresh_experiment/request_set.json")
_PROMOTION_FIXTURE_DIR = Path("tests/fixtures/promotion/dress")


class RefreshExperimentPrepareTest(unittest.TestCase):
    def test_prepare_creates_workspace_manifest_baseline_and_review(self) -> None:
        from temu_y2_women.refresh_experiment_runner import prepare_refresh_experiment

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            run_dir = _seed_refresh_run(temp_root, scenario="create")
            experiment_root = temp_root / "experiments"
            with patch(
                "temu_y2_women.refresh_experiment_runner._next_experiment_id",
                return_value="exp-refresh-001",
            ), patch(
                "temu_y2_women.refresh_experiment_runner._current_timestamp",
                return_value="2026-04-29T08:00:00Z",
            ):
                result = prepare_refresh_experiment(
                    run_dir=run_dir,
                    request_set_path=_REQUEST_SET_PATH,
                    experiment_root=experiment_root,
                    workspace_name="refresh-demo",
                )

            manifest = _read_json(Path(result["manifest_path"]))
            baseline = _read_json(Path(result["baseline_results_path"]))
            review = _read_json(Path(result["promotion_review_path"]))
            self.assertEqual(result["experiment_id"], "exp-refresh-001")
            self.assertEqual(manifest["workspace_root"], str(experiment_root / "refresh-demo"))
            self.assertEqual(review["schema_version"], "promotion-review-v1")
            self.assertEqual(sorted(baseline["results"]), ["baseline-transitional", "summer-vacation"])
            self.assertEqual(
                baseline["results"]["summer-vacation"]["selected_elements"]["detail"]["element_id"],
                "dress-detail-neck-scarf-001",
            )
            self.assertTrue((experiment_root / "refresh-demo" / "refresh_run" / "draft_elements.json").exists())


class RefreshExperimentApplyTest(unittest.TestCase):
    def test_apply_runs_reviewed_promotion_and_writes_compare_report(self) -> None:
        from temu_y2_women.refresh_experiment_runner import apply_refresh_experiment

        with TemporaryDirectory() as temp_dir:
            prepared = _prepare_experiment(Path(temp_dir))
            review_path = Path(prepared["promotion_review_path"])
            review_payload = _read_json(_PROMOTION_FIXTURE_DIR / "create" / "reviewed_decisions.json")
            _write_json(review_path, review_payload)

            with patch(
                "temu_y2_women.refresh_experiment_runner._current_timestamp",
                return_value="2026-04-29T08:10:00Z",
            ):
                result = apply_refresh_experiment(
                    manifest_path=Path(prepared["manifest_path"]),
                    reviewed_path=review_path,
                )

            report = _read_json(Path(result["experiment_report_path"]))
            compare = report["requests"]["summer-vacation"]
            baseline_compare = report["requests"]["baseline-transitional"]
            self.assertEqual(compare["change_type"], "strategy_changed_only")
            self.assertFalse(compare["selected_element_changes"])
            self.assertIn("dress-us-summer-waist-tie-vacation", compare["selected_strategy_ids"]["after"])
            self.assertNotEqual(compare["concept_score_delta"], 0.0)
            self.assertEqual(baseline_compare["change_type"], "no_observable_change")
            self.assertEqual(baseline_compare["concept_score_delta"], 0.0)
            self.assertFalse(baseline_compare["selected_element_changes"])

    def test_apply_reports_strategy_changed_only_when_strategy_ids_change_without_selection_drift(self) -> None:
        from temu_y2_women.refresh_experiment_runner import _request_compare

        before = {
            "selected_strategy_ids": ["dress-us-baseline"],
            "selected_elements": {
                "silhouette": {"element_id": "dress-silhouette-a-line-001", "value": "a-line"},
            },
            "concept_score": 0.78,
            "retrieved_elements": [
                {"element_id": "dress-silhouette-a-line-001", "effective_score": 0.85},
            ],
        }
        after = {
            "selected_strategy_ids": ["dress-us-summer-vacation"],
            "selected_elements": {
                "silhouette": {"element_id": "dress-silhouette-a-line-001", "value": "a-line"},
            },
            "concept_score": 0.81,
            "retrieved_elements": [
                {"element_id": "dress-silhouette-a-line-001", "effective_score": 0.9},
            ],
        }

        result = _request_compare(before, after)

        self.assertEqual(result["change_type"], "strategy_changed_only")
        self.assertEqual(result["selected_strategy_ids"]["before"], ["dress-us-baseline"])
        self.assertEqual(result["selected_strategy_ids"]["after"], ["dress-us-summer-vacation"])

    def test_apply_reports_strategy_drift_in_end_to_end_public_refresh_flow(self) -> None:
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
            run_dir = temp_root / refresh["run_id"]
            prepared = prepare_refresh_experiment(
                run_dir=run_dir,
                request_set_path=_REQUEST_SET_PATH,
                experiment_root=temp_root / "experiments",
                workspace_name="public-refresh-e2e",
            )
            review_path = Path(prepared["promotion_review_path"])
            review = _read_json(review_path)
            for element in review["elements"]:
                element["decision"] = "accept"
            for strategy in review["strategy_hints"]:
                strategy["decision"] = "accept"
                strategy["proposed_strategy_template"]["score_boost"] = 0.08
                strategy["proposed_strategy_template"]["score_cap"] = 0.12
            _write_json(review_path, review)

            result = apply_refresh_experiment(
                manifest_path=Path(prepared["manifest_path"]),
                reviewed_path=review_path,
            )

            report = _read_json(Path(result["experiment_report_path"]))
            self.assertEqual(
                report["summary"],
                {
                    "selection_changed": 0,
                    "strategy_changed_only": 2,
                    "retrieval_changed_only": 0,
                    "no_observable_change": 0,
                },
            )
            self.assertEqual(
                report["requests"]["baseline-transitional"]["change_type"],
                "strategy_changed_only",
            )
            self.assertEqual(
                report["requests"]["summer-vacation"]["selected_strategy_ids"]["after"],
                ["dress-us-summer-vacation", "dress-us-spring-vacation"],
            )

    def test_apply_can_auto_accept_pending_review_template(self) -> None:
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
                request_set_path=_REQUEST_SET_PATH,
                experiment_root=temp_root / "experiments",
                workspace_name="auto-accept",
            )

            result = apply_refresh_experiment(
                manifest_path=Path(prepared["manifest_path"]),
                reviewed_path=None,
                auto_accept_pending=True,
            )

            report = _read_json(Path(result["experiment_report_path"]))
            auto_reviewed_path = Path(prepared["workspace_root"]) / "auto_reviewed_decisions.json"
            auto_reviewed = _read_json(auto_reviewed_path)
            self.assertEqual(report["summary"]["no_observable_change"], 0)
            self.assertTrue(auto_reviewed_path.exists())
            self.assertTrue(all(item["decision"] == "accept" for item in auto_reviewed["elements"]))
            self.assertTrue(all(item["decision"] == "accept" for item in auto_reviewed["strategy_hints"]))


def _prepare_experiment(temp_root: Path) -> dict[str, object]:
    from unittest.mock import patch

    from temu_y2_women.refresh_experiment_runner import prepare_refresh_experiment

    run_dir = _seed_refresh_run(temp_root, scenario="create")
    experiment_root = temp_root / "experiments"
    with patch(
        "temu_y2_women.refresh_experiment_runner._next_experiment_id",
        return_value="exp-refresh-002",
    ), patch(
        "temu_y2_women.refresh_experiment_runner._current_timestamp",
        return_value="2026-04-29T08:05:00Z",
    ):
        return prepare_refresh_experiment(
            run_dir=run_dir,
            request_set_path=_REQUEST_SET_PATH,
            experiment_root=experiment_root,
            workspace_name="refresh-apply",
        )


def _seed_refresh_run(temp_root: Path, scenario: str) -> Path:
    run_dir = temp_root / "refresh-run"
    run_dir.mkdir()
    for filename in ("draft_elements.json", "draft_strategy_hints.json"):
        (run_dir / filename).write_text(
            (_PROMOTION_FIXTURE_DIR / scenario / filename).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    _write_json(run_dir / "ingestion_report.json", {"schema_version": "signal-ingestion-v1"})
    _write_json(run_dir / "refresh_report.json", {"schema_version": "public-refresh-report-v1"})
    return run_dir


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
