# Refresh-to-Review Promotion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a refresh-run-aware promotion entrypoint so a `data/refresh/dress/<run_id>/` directory can flow directly through review preparation and reviewed apply without changing existing promotion merge rules.

**Architecture:** Keep `temu_y2_women/evidence_promotion.py` as the only place that understands promotion validation, merge semantics, and atomic writes. Add a thin `refresh_run_promotion.py` orchestration layer that resolves run-dir artifacts, validates the refresh-run contract, and forwards resolved paths into the existing promotion core. Extend `evidence_promotion_cli.py` so `prepare` and `apply` can run in either `--run-dir` mode or legacy explicit-file mode without mixing staged input sources.

**Tech Stack:** Python 3 standard library, existing `GenerationError` contract, JSON fixture payloads, `unittest`, PowerShell git workflow.

---

## File Map

- Create: `temu_y2_women/refresh_run_promotion.py`
  - Thin orchestration helpers for refresh-run validation, default artifact resolution, and forwarding into the existing promotion APIs.
- Modify: `temu_y2_women/evidence_promotion_cli.py`
  - Add `--run-dir` parsing, input-mode validation, and dispatch into either the new orchestration layer or the existing explicit-file path.
- Create: `tests/test_refresh_run_promotion.py`
  - Focused tests for run-dir contract validation, default review/report path behavior, and reviewed fallback rules.
- Modify: `tests/test_evidence_promotion_cli.py`
  - CLI coverage for run-dir prepare/apply flows plus input-mode validation failures.
- Reuse existing fixtures:
  - `tests/fixtures/promotion/dress/baseline/*.json`
  - `tests/fixtures/promotion/dress/create/*.json`
  - `tests/fixtures/promotion/dress/update/*.json`

## Task 1: Add refresh-run contract tests and path-resolution helpers

**Files:**
- Create: `tests/test_refresh_run_promotion.py`
- Create: `temu_y2_women/refresh_run_promotion.py`

- [ ] **Step 1: Write the failing run-dir contract tests**

```python
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


class RefreshRunPromotionPrepareTest(unittest.TestCase):
    def test_prepare_from_refresh_run_writes_default_promotion_review(self) -> None:
        from temu_y2_women.refresh_run_promotion import prepare_dress_promotion_from_refresh_run

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            run_dir = _seed_refresh_run(temp_root, scenario="create")
            elements_path, strategies_path = _seed_active_evidence(temp_root)

            result = prepare_dress_promotion_from_refresh_run(
                run_dir=run_dir,
                active_elements_path=elements_path,
                active_strategies_path=strategies_path,
            )

            self.assertEqual(result["schema_version"], "promotion-review-v1")
            self.assertTrue((run_dir / "promotion_review.json").exists())

    def test_prepare_from_refresh_run_rejects_missing_required_artifacts(self) -> None:
        from temu_y2_women.refresh_run_promotion import prepare_dress_promotion_from_refresh_run

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            run_dir = _seed_refresh_run(temp_root, scenario="create")
            (run_dir / "refresh_report.json").unlink()
            elements_path, strategies_path = _seed_active_evidence(temp_root)

            result = prepare_dress_promotion_from_refresh_run(
                run_dir=run_dir,
                active_elements_path=elements_path,
                active_strategies_path=strategies_path,
            )

            self.assertEqual(result["error"]["code"], "INVALID_REFRESH_RUN")
            self.assertEqual(result["error"]["details"]["field"], "refresh_report.json")
```

- [ ] **Step 2: Run the focused suite and verify it fails because the module does not exist yet**

Run:

```bash
python -m unittest tests.test_refresh_run_promotion -v
```

Expected:

```text
ERROR: No module named 'temu_y2_women.refresh_run_promotion'
```

- [ ] **Step 3: Add the minimal run-dir validation and path-resolution implementation**

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from temu_y2_women.errors import GenerationError


_REQUIRED_REFRESH_RUN_FILES = (
    "draft_elements.json",
    "draft_strategy_hints.json",
    "ingestion_report.json",
    "refresh_report.json",
)


def resolve_prepare_refresh_run_paths(
    run_dir: Path,
    output_path: Path | None = None,
) -> dict[str, Path]:
    _validate_refresh_run_dir(run_dir)
    return {
        "draft_elements_path": run_dir / "draft_elements.json",
        "draft_strategy_hints_path": run_dir / "draft_strategy_hints.json",
        "output_path": output_path or (run_dir / "promotion_review.json"),
    }


def _validate_refresh_run_dir(run_dir: Path) -> None:
    if not run_dir.is_dir():
        raise _refresh_run_error(run_dir, "run_dir", "refresh run directory does not exist")
    for filename in _REQUIRED_REFRESH_RUN_FILES:
        candidate = run_dir / filename
        if candidate.exists():
            continue
        raise _refresh_run_error(run_dir, filename, "refresh run directory is missing a required artifact")


def _refresh_run_error(run_dir: Path, field: str, message: str) -> GenerationError:
    return GenerationError(
        code="INVALID_REFRESH_RUN",
        message=message,
        details={"path": str(run_dir), "field": field},
    )
```

- [ ] **Step 4: Re-run the focused suite until the contract tests pass**

Run:

```bash
python -m unittest tests.test_refresh_run_promotion -v
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit the contract-test baseline**

```bash
git add tests/test_refresh_run_promotion.py temu_y2_women/refresh_run_promotion.py
git commit -m "test(promotion): add refresh run contract coverage"
```

## Task 2: Wire prepare/apply orchestration into the promotion core

**Files:**
- Modify: `temu_y2_women/refresh_run_promotion.py`
- Modify: `tests/test_refresh_run_promotion.py`

- [ ] **Step 1: Extend the test file with apply-path fallback and fail-closed coverage**

```python
class RefreshRunPromotionApplyTest(unittest.TestCase):
    def test_apply_from_refresh_run_prefers_promotion_review(self) -> None:
        from temu_y2_women.refresh_run_promotion import apply_reviewed_dress_promotion_from_refresh_run

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            run_dir = _seed_refresh_run(temp_root, scenario="create")
            elements_path, strategies_path = _seed_active_evidence(temp_root)
            review_payload = _read_json(_PROMOTION_FIXTURE_DIR / "create" / "reviewed_decisions.json")
            _write_json(run_dir / "promotion_review.json", review_payload)

            result = apply_reviewed_dress_promotion_from_refresh_run(
                run_dir=run_dir,
                active_elements_path=elements_path,
                active_strategies_path=strategies_path,
            )

            self.assertEqual(result["schema_version"], "promotion-report-v1")
            self.assertTrue((run_dir / "promotion_report.json").exists())

    def test_apply_from_refresh_run_falls_back_to_legacy_reviewed_decisions(self) -> None:
        from temu_y2_women.refresh_run_promotion import apply_reviewed_dress_promotion_from_refresh_run

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            run_dir = _seed_refresh_run(temp_root, scenario="update")
            elements_path, strategies_path = _seed_active_evidence(temp_root)
            review_payload = _read_json(_PROMOTION_FIXTURE_DIR / "update" / "reviewed_decisions.json")
            _write_json(run_dir / "reviewed_decisions.json", review_payload)

            result = apply_reviewed_dress_promotion_from_refresh_run(
                run_dir=run_dir,
                active_elements_path=elements_path,
                active_strategies_path=strategies_path,
            )

            self.assertEqual(result["schema_version"], "promotion-report-v1")

    def test_apply_from_refresh_run_rejects_missing_reviewed_artifact(self) -> None:
        from temu_y2_women.refresh_run_promotion import apply_reviewed_dress_promotion_from_refresh_run

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            run_dir = _seed_refresh_run(temp_root, scenario="create")
            elements_path, strategies_path = _seed_active_evidence(temp_root)

            result = apply_reviewed_dress_promotion_from_refresh_run(
                run_dir=run_dir,
                active_elements_path=elements_path,
                active_strategies_path=strategies_path,
            )

            self.assertEqual(result["error"]["code"], "INVALID_REFRESH_RUN")
            self.assertEqual(result["error"]["details"]["field"], "reviewed")
```

- [ ] **Step 2: Run the suite and confirm the new apply expectations fail because the public functions do not exist yet**

Run:

```bash
python -m unittest tests.test_refresh_run_promotion -v
```

Expected:

```text
AttributeError: module 'temu_y2_women.refresh_run_promotion' has no attribute 'apply_reviewed_dress_promotion_from_refresh_run'
```

- [ ] **Step 3: Implement the public prepare/apply forwarding functions and reviewed fallback logic**

```python
from temu_y2_women.evidence_promotion import (
    apply_reviewed_dress_promotion,
    prepare_dress_promotion_review,
)


def prepare_dress_promotion_from_refresh_run(
    run_dir: Path,
    active_elements_path: Path,
    active_strategies_path: Path,
    output_path: Path | None = None,
    taxonomy_path: Path | None = None,
) -> dict[str, Any]:
    try:
        resolved = resolve_prepare_refresh_run_paths(run_dir, output_path)
        result = prepare_dress_promotion_review(
            draft_elements_path=resolved["draft_elements_path"],
            draft_strategy_hints_path=resolved["draft_strategy_hints_path"],
            active_elements_path=active_elements_path,
            active_strategies_path=active_strategies_path,
            taxonomy_path=taxonomy_path or _default_taxonomy_path(),
        )
        if "error" not in result:
            _write_json(resolved["output_path"], result)
        return result
    except GenerationError as error:
        return error.to_dict()
    except OSError as error:
        return _io_error(error).to_dict()


def apply_reviewed_dress_promotion_from_refresh_run(
    run_dir: Path,
    active_elements_path: Path,
    active_strategies_path: Path,
    reviewed_path: Path | None = None,
    report_path: Path | None = None,
    taxonomy_path: Path | None = None,
) -> dict[str, Any]:
    try:
        resolved = resolve_apply_refresh_run_paths(run_dir, reviewed_path, report_path)
        return apply_reviewed_dress_promotion(
            reviewed_path=resolved["reviewed_path"],
            draft_elements_path=resolved["draft_elements_path"],
            draft_strategy_hints_path=resolved["draft_strategy_hints_path"],
            active_elements_path=active_elements_path,
            active_strategies_path=active_strategies_path,
            report_path=resolved["report_path"],
            taxonomy_path=taxonomy_path or _default_taxonomy_path(),
        )
    except GenerationError as error:
        return error.to_dict()
    except OSError as error:
        return _io_error(error).to_dict()
```

- [ ] **Step 4: Add the apply-path resolver and shared JSON writer without exceeding the 60-line function guardrail**

```python
def resolve_apply_refresh_run_paths(
    run_dir: Path,
    reviewed_path: Path | None = None,
    report_path: Path | None = None,
) -> dict[str, Path]:
    _validate_refresh_run_dir(run_dir)
    return {
        "draft_elements_path": run_dir / "draft_elements.json",
        "draft_strategy_hints_path": run_dir / "draft_strategy_hints.json",
        "reviewed_path": reviewed_path or _default_reviewed_path(run_dir),
        "report_path": report_path or (run_dir / "promotion_report.json"),
    }


def _default_reviewed_path(run_dir: Path) -> Path:
    primary = run_dir / "promotion_review.json"
    if primary.exists():
        return primary
    legacy = run_dir / "reviewed_decisions.json"
    if legacy.exists():
        return legacy
    raise _refresh_run_error(run_dir, "reviewed", "refresh run directory does not contain a reviewed promotion artifact")
```

- [ ] **Step 5: Re-run the focused suite until green**

Run:

```bash
python -m unittest tests.test_refresh_run_promotion -v
```

Expected:

```text
OK
```

- [ ] **Step 6: Commit the orchestration layer**

```bash
git add tests/test_refresh_run_promotion.py temu_y2_women/refresh_run_promotion.py
git commit -m "feat(promotion): add refresh run orchestration"
```

## Task 3: Extend the promotion CLI for run-dir mode without breaking explicit-file mode

**Files:**
- Modify: `temu_y2_women/evidence_promotion_cli.py`
- Modify: `tests/test_evidence_promotion_cli.py`

- [ ] **Step 1: Add failing CLI tests for run-dir defaults and mixed-mode rejection**

```python
class EvidencePromotionRunDirCliTest(unittest.TestCase):
    def test_prepare_cli_run_dir_defaults_output_to_promotion_review(self) -> None:
        from temu_y2_women.evidence_promotion_cli import main

        stdout = io.StringIO()
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            run_dir = _seed_refresh_run(temp_root, scenario="create")
            elements_path, strategies_path = _seed_active_evidence(temp_root)
            with patch("sys.stdout", stdout):
                exit_code = main(
                    [
                        "prepare",
                        "--run-dir",
                        str(run_dir),
                        "--active-elements",
                        str(elements_path),
                        "--active-strategies",
                        str(strategies_path),
                    ]
                )

        self.assertEqual(exit_code, 0)
        self.assertTrue((run_dir / "promotion_review.json").exists())

    def test_apply_cli_run_dir_defaults_reviewed_and_report_paths(self) -> None:
        from temu_y2_women.evidence_promotion_cli import main

        stdout = io.StringIO()
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            run_dir = _seed_refresh_run(temp_root, scenario="create")
            elements_path, strategies_path = _seed_active_evidence(temp_root)
            review_payload = _read_json(_PROMOTION_FIXTURE_DIR / "create" / "reviewed_decisions.json")
            _write_json(run_dir / "promotion_review.json", review_payload)
            with patch("sys.stdout", stdout):
                exit_code = main(
                    [
                        "apply",
                        "--run-dir",
                        str(run_dir),
                        "--active-elements",
                        str(elements_path),
                        "--active-strategies",
                        str(strategies_path),
                    ]
                )

        self.assertEqual(exit_code, 0)
        self.assertTrue((run_dir / "promotion_report.json").exists())

    def test_prepare_cli_rejects_run_dir_and_staged_inputs_together(self) -> None:
        from temu_y2_women.evidence_promotion_cli import main

        stdout = io.StringIO()
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            run_dir = _seed_refresh_run(temp_root, scenario="create")
            elements_path, strategies_path = _seed_active_evidence(temp_root)
            with patch("sys.stdout", stdout):
                exit_code = main(
                    [
                        "prepare",
                        "--run-dir",
                        str(run_dir),
                        "--draft-elements",
                        str(run_dir / "draft_elements.json"),
                        "--draft-strategy-hints",
                        str(run_dir / "draft_strategy_hints.json"),
                        "--active-elements",
                        str(elements_path),
                        "--active-strategies",
                        str(strategies_path),
                    ]
                )

        self.assertEqual(exit_code, 1)
        self.assertEqual(json.loads(stdout.getvalue())["error"]["code"], "INVALID_REFRESH_RUN")
```

- [ ] **Step 2: Run the CLI suite and confirm the new tests fail because `--run-dir` is not parsed yet**

Run:

```bash
python -m unittest tests.test_evidence_promotion_cli -v
```

Expected:

```text
usage: ... error: unrecognized arguments: --run-dir
```

- [ ] **Step 3: Add `--run-dir` arguments and route run-dir mode through the new orchestration functions**

```python
from temu_y2_women.refresh_run_promotion import (
    apply_reviewed_dress_promotion_from_refresh_run,
    prepare_dress_promotion_from_refresh_run,
)


def _add_prepare_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("prepare", help="Build a promotion review template from staged drafts.")
    parser.add_argument("--run-dir", help="Path to a refresh run directory containing staged promotion inputs.")
    parser.add_argument("--draft-elements", help="Path to staged draft_elements.json.")
    parser.add_argument("--draft-strategy-hints", help="Path to staged draft_strategy_hints.json.")
    parser.add_argument("--active-elements", required=True, help="Path to active elements.json.")
    parser.add_argument("--active-strategies", required=True, help="Path to active strategy_templates.json.")
    parser.add_argument("--taxonomy", help="Optional path to evidence_taxonomy.json.")
    parser.add_argument("--output", help="Path to write the generated review template JSON.")
```

- [ ] **Step 4: Add small validation helpers so mode checks stay out of the command handlers**

```python
def _validate_prepare_args(args: argparse.Namespace) -> None:
    if args.run_dir and (args.draft_elements or args.draft_strategy_hints):
        raise GenerationError(
            code="INVALID_REFRESH_RUN",
            message="run-dir mode cannot be combined with explicit staged input paths",
            details={"field": "run_dir"},
        )
    if args.run_dir:
        return
    if args.draft_elements and args.draft_strategy_hints and args.output:
        return
    raise GenerationError(
        code="INVALID_PROMOTION_INPUT",
        message="prepare requires either --run-dir or explicit staged input paths plus --output",
        details={"field": "prepare"},
    )


def _validate_apply_args(args: argparse.Namespace) -> None:
    if args.run_dir and (args.draft_elements or args.draft_strategy_hints):
        raise GenerationError(
            code="INVALID_REFRESH_RUN",
            message="run-dir mode cannot be combined with explicit staged input paths",
            details={"field": "run_dir"},
        )
    if args.run_dir:
        return
    if args.reviewed and args.draft_elements and args.draft_strategy_hints and args.report_output:
        return
    raise GenerationError(
        code="INVALID_PROMOTION_INPUT",
        message="apply requires either --run-dir or explicit reviewed and staged input paths plus --report-output",
        details={"field": "apply"},
    )
```

- [ ] **Step 5: Re-run the CLI suite until green**

Run:

```bash
python -m unittest tests.test_evidence_promotion_cli -v
```

Expected:

```text
OK
```

- [ ] **Step 6: Commit the CLI integration**

```bash
git add tests/test_evidence_promotion_cli.py temu_y2_women/evidence_promotion_cli.py
git commit -m "feat(cli): add refresh run promotion mode"
```

## Task 4: Run end-to-end regression and verify shipping readiness

**Files:**
- Modify if needed after failures:
  - `temu_y2_women/refresh_run_promotion.py`
  - `temu_y2_women/evidence_promotion_cli.py`
  - `tests/test_refresh_run_promotion.py`
  - `tests/test_evidence_promotion_cli.py`

- [ ] **Step 1: Run the promotion-focused regression suite**

Run:

```bash
python -m unittest tests.test_refresh_run_promotion tests.test_evidence_promotion_cli tests.test_evidence_promotion -v
```

Expected:

```text
Ran 20+ tests in ...s
OK
```

- [ ] **Step 2: Run the upstream refresh/ingestion regression that feeds this chain**

Run:

```bash
python -m unittest tests.test_public_signal_refresh_cli tests.test_public_signal_refresh tests.test_signal_ingestion -v
```

Expected:

```text
Ran 20+ tests in ...s
OK
```

- [ ] **Step 3: Run static verification and the function-length guard**

Run:

```bash
python -m py_compile temu_y2_women\refresh_run_promotion.py temu_y2_women\evidence_promotion_cli.py
python C:\Users\lxy\.codex\rules\hooks\validate_python_function_length.py .
```

Expected:

```text
OK
```

- [ ] **Step 4: Review the final diff for scope and PR cleanliness**

Run:

```bash
git diff --stat
git status --short
```

Expected:

```text
Only the new orchestration module, the CLI change, the new test file, and the updated CLI tests are modified.
```

- [ ] **Step 5: Create the final feature commit**

```bash
git add temu_y2_women/refresh_run_promotion.py temu_y2_women/evidence_promotion_cli.py tests/test_refresh_run_promotion.py tests/test_evidence_promotion_cli.py
git commit -m "feat(promotion): wire refresh runs into review workflow"
```
