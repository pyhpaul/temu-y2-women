# Feedback Experiment Runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an isolated offline experiment workflow that runs baseline generation, prepares concept feedback, applies reviewed feedback into workspace copies of active evidence, reruns the same request, and writes a deterministic before/after experiment report.

**Architecture:** Keep the default generation contract unchanged, but introduce a small `EvidencePaths` configuration object so `generate_dress_concept()` can read either the default active evidence or a workspace copy. Build a dedicated `feedback_experiment_runner` orchestration module that copies source evidence into a workspace, calls the existing generation and feedback modules, then compares baseline and rerun outputs without mutating the repository’s default `data/mvp/dress/*` files.

**Tech Stack:** Python 3 standard library, JSON data files, `unittest`, existing `GenerationError`, existing `feedback_loop` / `evidence_repository` helpers, PowerShell git workflow.

---

## File Map

- Create: `temu_y2_women/evidence_paths.py`
  - Focused path configuration object for active evidence and taxonomy overrides.
- Modify: `temu_y2_women/orchestrator.py`
  - Accept optional `EvidencePaths` overrides and forward them into repository loads.
- Create: `temu_y2_women/feedback_experiment_runner.py`
  - Prepare/apply orchestration, workspace copying, manifest writing, rerun generation, and experiment report diffing.
- Create: `temu_y2_women/feedback_experiment_cli.py`
  - CLI for `prepare` and `apply`.
- Create: `tests/test_feedback_experiment_runner.py`
  - Workflow tests for path overrides, workspace isolation, prepare outputs, apply reruns, and report classification.
- Create: `tests/test_feedback_experiment_cli.py`
  - CLI regression tests and module entrypoint coverage.
- Modify: `openspec/changes/feedback-experiment-runner/tasks.md`
  - Mark the implementation tasks complete once the change lands.

### Task 1: Add evidence-path overrides to generation without changing the default contract

**Files:**
- Create: `temu_y2_women/evidence_paths.py`
- Modify: `temu_y2_women/orchestrator.py`
- Create: `tests/test_feedback_experiment_runner.py`

- [ ] **Step 1: Write the failing path-override tests**

Create `tests/test_feedback_experiment_runner.py` with these initial tests and helpers:

```python
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
            source_paths = _seed_source_bundle(temp_root, square_score=0.82)
            payload = _read_json(_REQUEST_FIXTURE_PATH)

            result = generate_dress_concept(payload, evidence_paths=source_paths)

        self.assertEqual(
            result["composed_concept"]["selected_elements"]["neckline"]["element_id"],
            "dress-neckline-v-neckline-001",
        )
        self.assertEqual(
            result["retrieved_elements"][3]["element_id"],
            "dress-neckline-square-001",
        )

    def test_generate_dress_concept_default_paths_still_work(self) -> None:
        from temu_y2_women.orchestrator import generate_dress_concept

        result = generate_dress_concept(_read_json(_REQUEST_FIXTURE_PATH))

        self.assertEqual(
            result["composed_concept"]["selected_elements"]["neckline"]["element_id"],
            "dress-neckline-v-neckline-001",
        )


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _seed_source_bundle(temp_root: Path, square_score: float) -> "EvidencePaths":
    from temu_y2_women.evidence_paths import EvidencePaths

    elements_path = temp_root / "elements.json"
    strategies_path = temp_root / "strategy_templates.json"
    taxonomy_path = temp_root / "evidence_taxonomy.json"
    ledger_path = temp_root / "feedback_ledger.json"

    elements_payload = _read_json(_ACTIVE_ELEMENTS_PATH)
    for element in elements_payload["elements"]:
        if element["element_id"] == "dress-neckline-square-001":
            element["base_score"] = square_score

    _write_json(elements_path, elements_payload)
    strategies_path.write_text(_ACTIVE_STRATEGIES_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    taxonomy_path.write_text(_TAXONOMY_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    ledger_path.write_text(_LEDGER_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    return EvidencePaths(
        elements_path=elements_path,
        strategies_path=strategies_path,
        taxonomy_path=taxonomy_path,
    )
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run:

```bash
python -m unittest tests.test_feedback_experiment_runner.EvidencePathOverrideTest -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'temu_y2_women.evidence_paths'`.

- [ ] **Step 3: Add the path object and wire it into orchestration**

Create `temu_y2_women/evidence_paths.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


_DEFAULT_DATA_ROOT = Path(__file__).resolve().parent.parent / "data" / "mvp" / "dress"


@dataclass(frozen=True, slots=True)
class EvidencePaths:
    elements_path: Path
    strategies_path: Path
    taxonomy_path: Path

    @classmethod
    def defaults(cls) -> "EvidencePaths":
        return cls(
            elements_path=_DEFAULT_DATA_ROOT / "elements.json",
            strategies_path=_DEFAULT_DATA_ROOT / "strategy_templates.json",
            taxonomy_path=_DEFAULT_DATA_ROOT / "evidence_taxonomy.json",
        )
```

Modify `temu_y2_women/orchestrator.py`:

```python
from __future__ import annotations

from typing import Any

from temu_y2_women.composition_engine import compose_concept
from temu_y2_women.evidence_paths import EvidencePaths
from temu_y2_women.evidence_repository import (
    flatten_candidates,
    load_elements,
    load_strategy_templates,
    retrieve_candidates,
)
from temu_y2_women.errors import GenerationError
from temu_y2_women.prompt_renderer import render_prompt_bundle
from temu_y2_women.request_normalizer import normalize_request
from temu_y2_women.result_packager import package_success_result
from temu_y2_women.strategy_selector import select_strategies


def generate_dress_concept(
    payload: dict[str, Any],
    evidence_paths: EvidencePaths | None = None,
) -> dict[str, Any]:
    try:
        resolved_paths = evidence_paths or EvidencePaths.defaults()
        request = normalize_request(payload)
        strategies = load_strategy_templates(
            path=resolved_paths.strategies_path,
            taxonomy_path=resolved_paths.taxonomy_path,
            elements_path=resolved_paths.elements_path,
        )
        strategy_result = select_strategies(request, strategies)
        elements = load_elements(
            path=resolved_paths.elements_path,
            taxonomy_path=resolved_paths.taxonomy_path,
        )
        grouped_candidates, retrieval_warnings = retrieve_candidates(request, elements, strategy_result.selected)
        concept = compose_concept(request, grouped_candidates)
        prompt_bundle = render_prompt_bundle(
            request=request,
            concept=concept,
            selected_strategies=strategy_result.selected,
            warnings=strategy_result.warnings + retrieval_warnings,
        )
        return package_success_result(
            request=request,
            selected_strategies=strategy_result.selected,
            retrieved_elements=flatten_candidates(grouped_candidates),
            composed_concept=concept,
            prompt_bundle=prompt_bundle,
            warnings=strategy_result.warnings + retrieval_warnings,
        )
    except GenerationError as error:
        return error.to_dict()
```

- [ ] **Step 4: Run the override tests to verify they pass**

Run:

```bash
python -m unittest tests.test_feedback_experiment_runner.EvidencePathOverrideTest -v
```

Expected: PASS for both tests.

- [ ] **Step 5: Commit**

```bash
git add temu_y2_women/evidence_paths.py temu_y2_women/orchestrator.py tests/test_feedback_experiment_runner.py
git commit -m "refactor: add evidence path overrides"
```

### Task 2: Add experiment prepare orchestration, workspace copies, and manifest writing

**Files:**
- Create: `temu_y2_women/feedback_experiment_runner.py`
- Modify: `tests/test_feedback_experiment_runner.py`

- [ ] **Step 1: Write the failing prepare tests**

Append these tests to `tests/test_feedback_experiment_runner.py`:

```python
class FeedbackExperimentPrepareTest(unittest.TestCase):
    def test_prepare_feedback_experiment_creates_workspace_manifest_and_review(self) -> None:
        from unittest.mock import patch
        from temu_y2_women.feedback_experiment_runner import (
            ExperimentSourcePaths,
            prepare_feedback_experiment,
        )
        from temu_y2_women.evidence_paths import EvidencePaths

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            source_bundle = _seed_full_source_bundle(temp_root, square_score=0.82)
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
                    workspace_name="baseline-reject",
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
        self.assertEqual(manifest["workspace_root"], str(experiment_root / "baseline-reject"))
        self.assertEqual(review["schema_version"], "feedback-review-v1")
        self.assertEqual(
            baseline["composed_concept"]["selected_elements"]["neckline"]["element_id"],
            "dress-neckline-v-neckline-001",
        )
        self.assertTrue((experiment_root / "baseline-reject" / "data" / "mvp" / "dress" / "elements.json").exists())
        self.assertTrue((experiment_root / "baseline-reject" / "data" / "feedback" / "dress" / "feedback_ledger.json").exists())
```

Add this helper near the bottom of the same test file:

```python
def _seed_full_source_bundle(temp_root: Path, square_score: float) -> dict[str, Path]:
    bundle_root = temp_root / "source"
    bundle_root.mkdir(parents=True, exist_ok=True)
    elements_path = bundle_root / "elements.json"
    strategies_path = bundle_root / "strategy_templates.json"
    taxonomy_path = bundle_root / "evidence_taxonomy.json"
    ledger_path = bundle_root / "feedback_ledger.json"

    elements_payload = _read_json(_ACTIVE_ELEMENTS_PATH)
    for element in elements_payload["elements"]:
        if element["element_id"] == "dress-neckline-square-001":
            element["base_score"] = square_score

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
```

- [ ] **Step 2: Run the targeted prepare tests to verify they fail**

Run:

```bash
python -m unittest tests.test_feedback_experiment_runner.FeedbackExperimentPrepareTest -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'temu_y2_women.feedback_experiment_runner'`.

- [ ] **Step 3: Implement the prepare workflow**

Create `temu_y2_women/feedback_experiment_runner.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any
from uuid import uuid4

from temu_y2_women.evidence_paths import EvidencePaths
from temu_y2_women.feedback_loop import prepare_dress_concept_feedback
from temu_y2_women.orchestrator import generate_dress_concept


_DEFAULT_LEDGER_PATH = Path(__file__).resolve().parent.parent / "data" / "feedback" / "dress" / "feedback_ledger.json"


@dataclass(frozen=True, slots=True)
class ExperimentSourcePaths:
    evidence_paths: EvidencePaths
    ledger_path: Path


def prepare_feedback_experiment(
    request_path: Path,
    experiment_root: Path,
    workspace_name: str | None = None,
    source_paths: ExperimentSourcePaths | None = None,
) -> dict[str, Any]:
    resolved_source = source_paths or ExperimentSourcePaths(
        evidence_paths=EvidencePaths.defaults(),
        ledger_path=_DEFAULT_LEDGER_PATH,
    )
    request_payload = _load_json_object(request_path)
    experiment_id = _next_experiment_id()
    workspace_root = _resolve_workspace_root(experiment_root, workspace_name, experiment_id)
    workspace_paths = _workspace_paths(workspace_root)
    _copy_workspace_inputs(resolved_source, workspace_paths)
    baseline_result = generate_dress_concept(
        request_payload,
        evidence_paths=workspace_paths["evidence_paths"],
    )
    baseline_result_path = workspace_root / "baseline_result.json"
    _write_json(baseline_result_path, baseline_result)
    review = prepare_dress_concept_feedback(result_path=baseline_result_path)
    review_path = workspace_root / "feedback_review.json"
    _write_json(review_path, review)
    manifest = _build_manifest(
        experiment_id=experiment_id,
        request_path=request_path,
        workspace_root=workspace_root,
        workspace_paths=workspace_paths,
        baseline_result_path=baseline_result_path,
        feedback_review_path=review_path,
        request_payload=request_payload,
    )
    manifest_path = workspace_root / "experiment_manifest.json"
    _write_json(manifest_path, manifest)
    return {
        "experiment_id": experiment_id,
        "workspace_root": str(workspace_root),
        "manifest_path": str(manifest_path),
        "baseline_result_path": str(baseline_result_path),
        "feedback_review_path": str(review_path),
    }


def _workspace_paths(workspace_root: Path) -> dict[str, Any]:
    data_root = workspace_root / "data"
    evidence_root = data_root / "mvp" / "dress"
    feedback_root = data_root / "feedback" / "dress"
    return {
        "evidence_paths": EvidencePaths(
            elements_path=evidence_root / "elements.json",
            strategies_path=evidence_root / "strategy_templates.json",
            taxonomy_path=evidence_root / "evidence_taxonomy.json",
        ),
        "ledger_path": feedback_root / "feedback_ledger.json",
    }


def _copy_workspace_inputs(source_paths: ExperimentSourcePaths, workspace_paths: dict[str, Any]) -> None:
    workspace_paths["evidence_paths"].elements_path.parent.mkdir(parents=True, exist_ok=True)
    workspace_paths["ledger_path"].parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_paths.evidence_paths.elements_path, workspace_paths["evidence_paths"].elements_path)
    shutil.copyfile(source_paths.evidence_paths.strategies_path, workspace_paths["evidence_paths"].strategies_path)
    shutil.copyfile(source_paths.evidence_paths.taxonomy_path, workspace_paths["evidence_paths"].taxonomy_path)
    shutil.copyfile(source_paths.ledger_path, workspace_paths["ledger_path"])
```

Also add `_resolve_workspace_root`, `_build_manifest`, `_request_fingerprint`, `_load_json_object`, `_write_json`, `_current_timestamp`, and `_next_experiment_id` in the same file as focused helpers under 60 lines each.

- [ ] **Step 4: Run the prepare tests to verify they pass**

Run:

```bash
python -m unittest tests.test_feedback_experiment_runner.FeedbackExperimentPrepareTest -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add temu_y2_women/feedback_experiment_runner.py tests/test_feedback_experiment_runner.py
git commit -m "feat: add feedback experiment prepare workflow"
```

### Task 3: Add experiment apply, rerun generation, and before/after report classification

**Files:**
- Modify: `temu_y2_women/feedback_experiment_runner.py`
- Modify: `tests/test_feedback_experiment_runner.py`

- [ ] **Step 1: Write the failing apply and report tests**

Append these tests to `tests/test_feedback_experiment_runner.py`:

```python
class FeedbackExperimentApplyTest(unittest.TestCase):
    def test_apply_feedback_experiment_marks_selection_changed_for_reject(self) -> None:
        from unittest.mock import patch
        from temu_y2_women.evidence_paths import EvidencePaths
        from temu_y2_women.feedback_experiment_runner import (
            ExperimentSourcePaths,
            apply_feedback_experiment,
            prepare_feedback_experiment,
        )

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            source_bundle = _seed_full_source_bundle(temp_root, square_score=0.82)
            experiment_root = temp_root / "experiments"
            with patch(
                "temu_y2_women.feedback_experiment_runner._next_experiment_id",
                return_value="exp-fixed-002",
            ), patch(
                "temu_y2_women.feedback_experiment_runner._current_timestamp",
                return_value="2026-04-27T14:00:00Z",
            ):
                prepared = prepare_feedback_experiment(
                    request_path=_REQUEST_FIXTURE_PATH,
                    experiment_root=experiment_root,
                    workspace_name="reject-shift",
                    source_paths=ExperimentSourcePaths(
                        evidence_paths=EvidencePaths(
                            elements_path=source_bundle["elements_path"],
                            strategies_path=source_bundle["strategies_path"],
                            taxonomy_path=source_bundle["taxonomy_path"],
                        ),
                        ledger_path=source_bundle["ledger_path"],
                    ),
                )

            review_path = Path(prepared["feedback_review_path"])
            review_payload = _read_json(review_path)
            review_payload["decision"] = "reject"
            review_payload["notes"] = "force neckline reevaluation"
            _write_json(review_path, review_payload)

            with patch(
                "temu_y2_women.feedback_loop._current_timestamp",
                return_value="2026-04-27T14:10:00Z",
            ), patch(
                "temu_y2_women.feedback_experiment_runner._current_timestamp",
                return_value="2026-04-27T14:11:00Z",
            ):
                result = apply_feedback_experiment(
                    reviewed_path=review_path,
                    manifest_path=Path(prepared["manifest_path"]),
                )

            report = _read_json(Path(result["experiment_report_path"]))
            rerun = _read_json(Path(result["post_apply_result_path"]))

        self.assertEqual(report["change_type"], "selection_changed")
        self.assertEqual(
            rerun["composed_concept"]["selected_elements"]["neckline"]["element_id"],
            "dress-neckline-square-001",
        )
        self.assertEqual(
            report["selected_element_changes"]["neckline"]["before"]["element_id"],
            "dress-neckline-v-neckline-001",
        )

    def test_apply_feedback_experiment_marks_retrieval_changed_only_for_keep(self) -> None:
        from unittest.mock import patch
        from temu_y2_women.evidence_paths import EvidencePaths
        from temu_y2_women.feedback_experiment_runner import (
            ExperimentSourcePaths,
            apply_feedback_experiment,
            prepare_feedback_experiment,
        )

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            source_bundle = _seed_full_source_bundle(temp_root, square_score=0.80)
            experiment_root = temp_root / "experiments"
            with patch(
                "temu_y2_women.feedback_experiment_runner._next_experiment_id",
                return_value="exp-fixed-003",
            ), patch(
                "temu_y2_women.feedback_experiment_runner._current_timestamp",
                return_value="2026-04-27T15:00:00Z",
            ):
                prepared = prepare_feedback_experiment(
                    request_path=_REQUEST_FIXTURE_PATH,
                    experiment_root=experiment_root,
                    workspace_name="keep-stable",
                    source_paths=ExperimentSourcePaths(
                        evidence_paths=EvidencePaths(
                            elements_path=source_bundle["elements_path"],
                            strategies_path=source_bundle["strategies_path"],
                            taxonomy_path=source_bundle["taxonomy_path"],
                        ),
                        ledger_path=source_bundle["ledger_path"],
                    ),
                )

            review_path = Path(prepared["feedback_review_path"])
            review_payload = _read_json(review_path)
            review_payload["decision"] = "keep"
            review_payload["notes"] = "reinforce current neckline"
            _write_json(review_path, review_payload)

            with patch(
                "temu_y2_women.feedback_loop._current_timestamp",
                return_value="2026-04-27T15:10:00Z",
            ), patch(
                "temu_y2_women.feedback_experiment_runner._current_timestamp",
                return_value="2026-04-27T15:11:00Z",
            ):
                result = apply_feedback_experiment(
                    reviewed_path=review_path,
                    manifest_path=Path(prepared["manifest_path"]),
                )

            report = _read_json(Path(result["experiment_report_path"]))

        self.assertEqual(report["change_type"], "retrieval_changed_only")
        self.assertFalse(report["selected_element_changes"])
        self.assertTrue(report["retrieval_rank_changes"])
```

- [ ] **Step 2: Run the targeted apply tests to verify they fail**

Run:

```bash
python -m unittest tests.test_feedback_experiment_runner.FeedbackExperimentApplyTest -v
```

Expected: FAIL because `apply_feedback_experiment` does not exist yet.

- [ ] **Step 3: Implement feedback apply, rerun generation, and experiment diffing**

Extend `temu_y2_women/feedback_experiment_runner.py` with:

```python
from temu_y2_women.feedback_loop import apply_reviewed_dress_concept_feedback


def apply_feedback_experiment(reviewed_path: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = _load_json_object(manifest_path)
    workspace_root = Path(manifest["workspace_root"])
    workspace_paths = _workspace_paths(workspace_root)
    feedback_report_path = workspace_root / "feedback_report.json"
    apply_report = apply_reviewed_dress_concept_feedback(
        reviewed_path=reviewed_path,
        result_path=Path(manifest["baseline_result_path"]),
        active_elements_path=workspace_paths["evidence_paths"].elements_path,
        ledger_path=workspace_paths["ledger_path"],
        report_path=feedback_report_path,
        taxonomy_path=workspace_paths["evidence_paths"].taxonomy_path,
    )
    request_payload = _load_json_object(Path(manifest["request_path"]))
    rerun = generate_dress_concept(
        request_payload,
        evidence_paths=workspace_paths["evidence_paths"],
    )
    rerun_path = workspace_root / "post_apply_result.json"
    _write_json(rerun_path, rerun)
    report = _build_experiment_report(
        manifest=manifest,
        reviewed=_load_json_object(reviewed_path),
        baseline=_load_json_object(Path(manifest["baseline_result_path"])),
        rerun=rerun,
        apply_report=apply_report,
    )
    experiment_report_path = workspace_root / "experiment_report.json"
    _write_json(experiment_report_path, report)
    return {
        "experiment_id": manifest["experiment_id"],
        "feedback_report_path": str(feedback_report_path),
        "post_apply_result_path": str(rerun_path),
        "experiment_report_path": str(experiment_report_path),
    }


def _build_experiment_report(
    manifest: dict[str, Any],
    reviewed: dict[str, Any],
    baseline: dict[str, Any],
    rerun: dict[str, Any],
    apply_report: dict[str, Any],
) -> dict[str, Any]:
    selected_changes = _selected_element_changes(
        baseline["composed_concept"]["selected_elements"],
        rerun["composed_concept"]["selected_elements"],
    )
    retrieval_changes = _retrieval_rank_changes(
        baseline["retrieved_elements"],
        rerun["retrieved_elements"],
        reviewed["feedback_target"]["selected_element_ids"],
    )
    change_type = _classify_change(selected_changes, retrieval_changes)
    return {
        "schema_version": "feedback-experiment-report-v1",
        "experiment_id": manifest["experiment_id"],
        "decision": reviewed["decision"],
        "change_type": change_type,
        "baseline_summary": {
            "concept_score": baseline["composed_concept"]["concept_score"],
            "selected_elements": baseline["composed_concept"]["selected_elements"],
        },
        "rerun_summary": {
            "concept_score": rerun["composed_concept"]["concept_score"],
            "selected_elements": rerun["composed_concept"]["selected_elements"],
        },
        "score_deltas": apply_report.get("affected_elements", []),
        "selected_element_changes": selected_changes,
        "retrieval_rank_changes": retrieval_changes,
        "warnings": apply_report.get("warnings", []),
        "recorded_at": _current_timestamp(),
    }
```

Also add focused helpers for `_selected_element_changes`, `_retrieval_rank_changes`, `_rank_index`, and `_classify_change` so each function stays under 60 lines.

- [ ] **Step 4: Run the apply tests to verify they pass**

Run:

```bash
python -m unittest tests.test_feedback_experiment_runner.FeedbackExperimentApplyTest -v
```

Expected: PASS for both reject and keep report classifications.

- [ ] **Step 5: Commit**

```bash
git add temu_y2_women/feedback_experiment_runner.py tests/test_feedback_experiment_runner.py
git commit -m "feat: add feedback experiment apply workflow"
```

### Task 4: Add the experiment CLI and module entrypoint coverage

**Files:**
- Create: `temu_y2_women/feedback_experiment_cli.py`
- Create: `tests/test_feedback_experiment_cli.py`

- [ ] **Step 1: Write the failing CLI tests**

Create `tests/test_feedback_experiment_cli.py`:

```python
from __future__ import annotations

import io
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


_REQUEST_FIXTURE_PATH = Path("tests/fixtures/requests/dress-generation-mvp/success-baseline-transitional-mode-a.json")


class FeedbackExperimentCliTest(unittest.TestCase):
    def test_prepare_cli_prints_manifest_summary_and_writes_workspace(self) -> None:
        from temu_y2_women.feedback_experiment_cli import main

        stdout = io.StringIO()
        with TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir) / "experiments"
            with patch("sys.stdout", stdout), patch(
                "temu_y2_women.feedback_experiment_runner._next_experiment_id",
                return_value="exp-cli-001",
            ), patch(
                "temu_y2_women.feedback_experiment_runner._current_timestamp",
                return_value="2026-04-27T16:00:00Z",
            ):
                exit_code = main(
                    [
                        "prepare",
                        "--request",
                        str(_REQUEST_FIXTURE_PATH),
                        "--experiment-root",
                        str(workspace_root),
                        "--workspace-name",
                        "cli-prepare",
                    ]
                )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["experiment_id"], "exp-cli-001")
        self.assertTrue((workspace_root / "cli-prepare" / "experiment_manifest.json").exists())

    def test_apply_cli_prints_report_summary(self) -> None:
        from temu_y2_women.feedback_experiment_cli import main
        from temu_y2_women.feedback_experiment_runner import prepare_feedback_experiment

        stdout = io.StringIO()
        with TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir) / "experiments"
            with patch(
                "temu_y2_women.feedback_experiment_runner._next_experiment_id",
                return_value="exp-cli-002",
            ), patch(
                "temu_y2_women.feedback_experiment_runner._current_timestamp",
                return_value="2026-04-27T16:10:00Z",
            ):
                prepared = prepare_feedback_experiment(
                    request_path=_REQUEST_FIXTURE_PATH,
                    experiment_root=workspace_root,
                    workspace_name="cli-apply",
                )

            review_path = Path(prepared["feedback_review_path"])
            review_payload = json.loads(review_path.read_text(encoding="utf-8"))
            review_payload["decision"] = "keep"
            review_payload["notes"] = "cli apply"
            review_path.write_text(json.dumps(review_payload, ensure_ascii=False, indent=2), encoding="utf-8")

            with patch("sys.stdout", stdout), patch(
                "temu_y2_women.feedback_loop._current_timestamp",
                return_value="2026-04-27T16:11:00Z",
            ), patch(
                "temu_y2_women.feedback_experiment_runner._current_timestamp",
                return_value="2026-04-27T16:12:00Z",
            ):
                exit_code = main(
                    [
                        "apply",
                        "--reviewed",
                        str(review_path),
                        "--manifest",
                        str(prepared["manifest_path"]),
                    ]
                )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertIn("experiment_report_path", payload)

    def test_prepare_cli_module_entrypoint_runs_outside_repo_root(self) -> None:
        with TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "experiments"
            env = dict(os.environ)
            repo_root = Path.cwd()
            env["PYTHONPATH"] = str(repo_root)
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "temu_y2_women.feedback_experiment_cli",
                    "prepare",
                    "--request",
                    str((repo_root / _REQUEST_FIXTURE_PATH).resolve()),
                    "--experiment-root",
                    str(output_root),
                    "--workspace-name",
                    "module-entrypoint",
                ],
                capture_output=True,
                cwd=temp_dir,
                env=env,
                text=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 0)
        payload = json.loads(completed.stdout)
        self.assertTrue((output_root / "module-entrypoint" / "experiment_manifest.json").exists())
        self.assertIn("feedback_review_path", payload)
```

- [ ] **Step 2: Run the targeted CLI tests to verify they fail**

Run:

```bash
python -m unittest tests.test_feedback_experiment_cli -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'temu_y2_women.feedback_experiment_cli'`.

- [ ] **Step 3: Implement the CLI**

Create `temu_y2_women/feedback_experiment_cli.py`:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from temu_y2_women.feedback_experiment_runner import (
    apply_feedback_experiment,
    prepare_feedback_experiment,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare or apply isolated feedback experiments.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare", help="Create a workspace and baseline feedback review.")
    prepare.add_argument("--request", required=True, help="Path to the source request JSON.")
    prepare.add_argument("--experiment-root", required=True, help="Directory that will contain experiment workspaces.")
    prepare.add_argument("--workspace-name", help="Optional fixed workspace directory name.")
    apply = subparsers.add_parser("apply", help="Apply reviewed feedback inside an experiment workspace.")
    apply.add_argument("--reviewed", required=True, help="Path to the reviewed feedback JSON.")
    apply.add_argument("--manifest", required=True, help="Path to the experiment manifest JSON.")
    args = parser.parse_args(argv)
    result = _run_command(args)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if "error" not in result else 1


def _run_command(args: argparse.Namespace) -> dict[str, object]:
    if args.command == "prepare":
        return prepare_feedback_experiment(
            request_path=Path(args.request),
            experiment_root=Path(args.experiment_root),
            workspace_name=args.workspace_name,
        )
    return apply_feedback_experiment(
        reviewed_path=Path(args.reviewed),
        manifest_path=Path(args.manifest),
    )
```

- [ ] **Step 4: Run the CLI tests to verify they pass**

Run:

```bash
python -m unittest tests.test_feedback_experiment_cli -v
```

Expected: PASS for prepare, apply, and module entrypoint coverage.

- [ ] **Step 5: Commit**

```bash
git add temu_y2_women/feedback_experiment_cli.py tests/test_feedback_experiment_cli.py
git commit -m "feat: add feedback experiment cli"
```

### Task 5: Update OpenSpec tasks and run full verification before shipping

**Files:**
- Modify: `openspec/changes/feedback-experiment-runner/tasks.md`

- [ ] **Step 1: Mark the completed OpenSpec tasks**

Update `openspec/changes/feedback-experiment-runner/tasks.md` so every implemented item flips from `- [ ]` to `- [x]`.

- [ ] **Step 2: Run focused experiment tests**

Run:

```bash
python -m unittest tests.test_feedback_experiment_runner tests.test_feedback_experiment_cli -v
```

Expected: PASS.

- [ ] **Step 3: Run repository regression and guardrails**

Run:

```bash
python -m unittest
openspec validate feedback-experiment-runner --type change --strict --no-interactive
openspec validate --specs --strict --no-interactive
python C:\Users\lxy\.codex\rules\hooks\validate_python_function_length.py .
```

Expected:
- `python -m unittest` -> all tests PASS
- `openspec validate feedback-experiment-runner ...` -> `Change 'feedback-experiment-runner' is valid`
- `openspec validate --specs ...` -> all specs PASS
- function-length hook -> `OK`

- [ ] **Step 4: Review the diff and commit the completed implementation**

Run:

```bash
git status --short --branch
git diff --stat
git add temu_y2_women/evidence_paths.py temu_y2_women/orchestrator.py temu_y2_women/feedback_experiment_runner.py temu_y2_women/feedback_experiment_cli.py tests/test_feedback_experiment_runner.py tests/test_feedback_experiment_cli.py openspec/changes/feedback-experiment-runner/tasks.md
git commit -m "feat: add feedback experiment runner"
```

- [ ] **Step 5: Ship on the branch workflow**

Run:

```bash
powershell -ExecutionPolicy Bypass -File C:\Users\lxy\.codex\skills\git-pr-ship\scripts\git_snapshot.ps1
```

Expected: clean worktree on the feature branch with local commits ready for push/PR creation.
