# Concept Feedback Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a review-gated concept feedback workflow that turns `keep` and `reject` decisions on successful `dress` concept results into ledgered, bounded updates to active element scores.

**Architecture:** Keep the runtime generation contract unchanged and add a downstream `feedback_loop` workflow that mirrors evidence promotion: prepare a deterministic review file, validate the reviewed file fail-closed, then atomically write updated `elements.json`, a persistent `feedback_ledger.json`, and a deterministic report. Keep orchestration inside `temu_y2_women/feedback_loop.py`, isolate JSON/file I/O from fingerprinting and score math helpers, and keep every function under 60 lines.

**Tech Stack:** Python 3 standard library, JSON data files, `unittest`, existing `GenerationError`, existing evidence taxonomy/validation helpers, PowerShell git workflow.

---

## File Map

- Create: `data/feedback/dress/feedback_ledger.json`
  - Persistent ledger root for successful concept feedback records.
- Create: `tests/fixtures/feedback/dress/result_success.json`
  - Successful concept result payload used as the canonical prepare/apply source.
- Create: `tests/fixtures/feedback/dress/expected_review_template.json`
  - Deterministic `feedback-review-v1` template generated from the success payload.
- Create: `tests/fixtures/feedback/dress/reviewed_keep.json`
  - Reviewed feedback file with `decision=keep`.
- Create: `tests/fixtures/feedback/dress/reviewed_reject.json`
  - Reviewed feedback file with `decision=reject`.
- Create: `tests/fixtures/feedback/dress/expected_keep_report.json`
  - Deterministic report for a successful keep apply.
- Create: `tests/fixtures/feedback/dress/expected_reject_report.json`
  - Deterministic report for a successful reject apply.
- Create: `tests/fixtures/feedback/dress/expected_elements_after_keep.json`
  - Expected active evidence snapshot after keep.
- Create: `tests/fixtures/feedback/dress/expected_elements_after_reject.json`
  - Expected active evidence snapshot after reject.
- Create: `tests/fixtures/feedback/dress/expected_ledger_after_keep.json`
  - Expected ledger snapshot after keep.
- Create: `tests/fixtures/feedback/dress/expected_ledger_after_reject.json`
  - Expected ledger snapshot after reject.
- Create: `temu_y2_women/feedback_loop.py`
  - Prepare/apply orchestration, fingerprinting, validation, clamping, ledger/report writing.
- Create: `temu_y2_women/feedback_loop_cli.py`
  - CLI for `prepare` and `apply`.
- Create: `tests/test_feedback_loop.py`
  - Unit and workflow tests for prepare/apply/rollback.
- Create: `tests/test_feedback_loop_cli.py`
  - CLI regression tests mirroring existing CLI patterns.
- Modify: `openspec/specs/signal-ingestion-pipeline/spec.md`
  - Replace the lingering `Purpose` placeholder.
- Modify: `openspec/changes/concept-feedback-loop/tasks.md`
  - Mark tasks complete as each implementation slice lands.

### Task 1: Add fixtures, review-template shape, and prepare-path tests

**Files:**
- Create: `data/feedback/dress/feedback_ledger.json`
- Create: `tests/fixtures/feedback/dress/result_success.json`
- Create: `tests/fixtures/feedback/dress/expected_review_template.json`
- Create: `tests/fixtures/feedback/dress/reviewed_keep.json`
- Create: `tests/fixtures/feedback/dress/reviewed_reject.json`
- Create: `temu_y2_women/feedback_loop.py`
- Create: `tests/test_feedback_loop.py`
- Modify: `openspec/specs/signal-ingestion-pipeline/spec.md`

- [ ] **Step 1: Write the failing prepare tests**

Add these tests to `tests/test_feedback_loop.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
import unittest


_FEEDBACK_FIXTURE_DIR = Path("tests/fixtures/feedback/dress")


class FeedbackPrepareTest(unittest.TestCase):
    def test_prepare_dress_concept_feedback_matches_expected_fixture(self) -> None:
        from temu_y2_women.feedback_loop import prepare_dress_concept_feedback

        result = prepare_dress_concept_feedback(
            result_path=_FEEDBACK_FIXTURE_DIR / "result_success.json",
        )

        self.assertEqual(result, _read_json(_FEEDBACK_FIXTURE_DIR / "expected_review_template.json"))

    def test_prepare_dress_concept_feedback_rejects_error_payload(self) -> None:
        from tempfile import TemporaryDirectory
        from temu_y2_women.feedback_loop import prepare_dress_concept_feedback

        with TemporaryDirectory() as temp_dir:
            invalid_path = Path(temp_dir) / "error.json"
            invalid_path.write_text(
                json.dumps({"error": {"code": "NO_CANDIDATES", "message": "bad", "details": {}}}),
                encoding="utf-8",
            )
            result = prepare_dress_concept_feedback(result_path=invalid_path)

        self.assertEqual(result["error"]["code"], "INVALID_FEEDBACK_INPUT")
        self.assertEqual(result["error"]["details"]["field"], "result")


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run:

```bash
python -m unittest tests.test_feedback_loop.FeedbackPrepareTest -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'temu_y2_women.feedback_loop'`.

- [ ] **Step 3: Add fixtures, ledger seed, spec purpose fix, and minimal prepare implementation**

Create `data/feedback/dress/feedback_ledger.json`:

```json
{
  "schema_version": "feedback-ledger-v1",
  "records": []
}
```

Create `temu_y2_women/feedback_loop.py` with a minimal prepare path:

```python
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from temu_y2_women.errors import GenerationError


def prepare_dress_concept_feedback(result_path: Path) -> dict[str, Any]:
    try:
        result = _load_success_result(result_path)
        return _build_review_template(result)
    except GenerationError as error:
        return error.to_dict()
    except OSError as error:
        return _io_error(error).to_dict()


def _load_success_result(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or "error" in payload:
        raise GenerationError(
            code="INVALID_FEEDBACK_INPUT",
            message="feedback input must be a successful concept result",
            details={"path": str(path), "field": "result"},
        )
    if payload.get("request_normalized", {}).get("category") != "dress":
        raise GenerationError(
            code="INVALID_FEEDBACK_INPUT",
            message="feedback input category is unsupported",
            details={"path": str(path), "field": "category"},
        )
    selected = payload.get("composed_concept", {}).get("selected_elements", {})
    if not isinstance(selected, dict) or not selected:
        raise GenerationError(
            code="INVALID_FEEDBACK_INPUT",
            message="feedback input must contain selected active elements",
            details={"path": str(path), "field": "selected_elements"},
        )
    return payload


def _build_review_template(result: dict[str, Any]) -> dict[str, Any]:
    selected = result["composed_concept"]["selected_elements"]
    selected_items = [
        {
            "slot": slot,
            "element_id": item["element_id"],
            "value": item["value"],
        }
        for slot, item in selected.items()
    ]
    request = result["request_normalized"]
    return {
        "schema_version": "feedback-review-v1",
        "category": "dress",
        "feedback_target": {
            "request_normalized": request,
            "selected_elements": selected_items,
            "selected_element_ids": [item["element_id"] for item in selected_items],
            "concept_score": result["composed_concept"]["concept_score"],
            "request_fingerprint": _fingerprint(request),
            "concept_fingerprint": _fingerprint(selected_items),
        },
        "decision": "pending",
        "notes": "",
    }


def _fingerprint(payload: Any) -> str:
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _io_error(error: OSError) -> GenerationError:
    return GenerationError(
        code="FEEDBACK_IO_FAILED",
        message="failed to read feedback inputs",
        details={"path": str(getattr(error, "filename", ""))},
    )
```

Replace the `Purpose` line in `openspec/specs/signal-ingestion-pipeline/spec.md` with:

```markdown
Define the stable contract for ingesting file-backed `dress` market signals into deterministic staged draft evidence artifacts without mutating active runtime evidence.
```

- [ ] **Step 4: Run the prepare tests to verify they pass**

Run:

```bash
python -m unittest tests.test_feedback_loop.FeedbackPrepareTest -v
```

Expected: PASS for both prepare tests.

- [ ] **Step 5: Commit**

```bash
git add data/feedback/dress/feedback_ledger.json tests/fixtures/feedback/dress temu_y2_women/feedback_loop.py tests/test_feedback_loop.py openspec/specs/signal-ingestion-pipeline/spec.md
git commit -m "feat: add concept feedback prepare flow"
```

### Task 2: Validate reviewed feedback and implement score apply + ledger/report writes

**Files:**
- Modify: `temu_y2_women/feedback_loop.py`
- Modify: `tests/test_feedback_loop.py`
- Create: `tests/fixtures/feedback/dress/expected_keep_report.json`
- Create: `tests/fixtures/feedback/dress/expected_reject_report.json`
- Create: `tests/fixtures/feedback/dress/expected_elements_after_keep.json`
- Create: `tests/fixtures/feedback/dress/expected_elements_after_reject.json`
- Create: `tests/fixtures/feedback/dress/expected_ledger_after_keep.json`
- Create: `tests/fixtures/feedback/dress/expected_ledger_after_reject.json`

- [ ] **Step 1: Write failing validation/apply tests**

Append these tests to `tests/test_feedback_loop.py`:

```python
class FeedbackApplyTest(unittest.TestCase):
    def test_apply_reviewed_keep_feedback_updates_elements_ledger_and_report(self) -> None:
        from tempfile import TemporaryDirectory
        from temu_y2_women.feedback_loop import apply_reviewed_dress_concept_feedback

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            elements_path = _seed_elements(temp_root)
            ledger_path = _seed_ledger(temp_root)
            report_path = temp_root / "feedback_report.json"
            result = apply_reviewed_dress_concept_feedback(
                reviewed_path=_FEEDBACK_FIXTURE_DIR / "reviewed_keep.json",
                result_path=_FEEDBACK_FIXTURE_DIR / "result_success.json",
                active_elements_path=elements_path,
                ledger_path=ledger_path,
                report_path=report_path,
            )

            self.assertEqual(result, _read_json(_FEEDBACK_FIXTURE_DIR / "expected_keep_report.json"))
            self.assertEqual(_read_json(elements_path), _read_json(_FEEDBACK_FIXTURE_DIR / "expected_elements_after_keep.json"))
            self.assertEqual(_read_json(ledger_path), _read_json(_FEEDBACK_FIXTURE_DIR / "expected_ledger_after_keep.json"))

    def test_apply_reviewed_feedback_rejects_tampered_selected_ids(self) -> None:
        from tempfile import TemporaryDirectory
        from temu_y2_women.feedback_loop import apply_reviewed_dress_concept_feedback

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            reviewed = _read_json(_FEEDBACK_FIXTURE_DIR / "reviewed_keep.json")
            reviewed["feedback_target"]["selected_element_ids"] = ["tampered"]
            reviewed_path = temp_root / "tampered.json"
            reviewed_path.write_text(json.dumps(reviewed), encoding="utf-8")
            result = apply_reviewed_dress_concept_feedback(
                reviewed_path=reviewed_path,
                result_path=_FEEDBACK_FIXTURE_DIR / "result_success.json",
                active_elements_path=_seed_elements(temp_root),
                ledger_path=_seed_ledger(temp_root),
                report_path=temp_root / "feedback_report.json",
            )

        self.assertEqual(result["error"]["code"], "INVALID_FEEDBACK_REVIEW")
        self.assertEqual(result["error"]["details"]["field"], "selected_element_ids")
```

- [ ] **Step 2: Run the targeted apply tests to verify they fail**

Run:

```bash
python -m unittest tests.test_feedback_loop.FeedbackApplyTest -v
```

Expected: FAIL because `apply_reviewed_dress_concept_feedback` does not exist yet.

- [ ] **Step 3: Implement reviewed validation, clamped score math, ledger append, and atomic writes**

Add these pieces to `temu_y2_women/feedback_loop.py`:

```python
from temu_y2_women.evidence_repository import load_elements, load_evidence_taxonomy, validate_element_records


def apply_reviewed_dress_concept_feedback(
    reviewed_path: Path,
    result_path: Path,
    active_elements_path: Path,
    ledger_path: Path,
    report_path: Path,
    taxonomy_path: Path = Path("data/mvp/dress/evidence_taxonomy.json"),
) -> dict[str, Any]:
    try:
        expected = _build_review_template(_load_success_result(result_path))
        reviewed = _load_review_bundle(reviewed_path)
        _validate_review_bundle(reviewed_path, reviewed, expected)
        taxonomy = load_evidence_taxonomy(taxonomy_path)
        active_elements = load_elements(active_elements_path, taxonomy_path=taxonomy_path)
        updated_elements, affected, clamped = _apply_score_delta(active_elements, reviewed, taxonomy)
        ledger = _append_ledger_record(ledger_path, reviewed, expected)
        report = _build_feedback_report(reviewed_path, result_path, reviewed, affected, clamped)
        _write_output_files(
            (active_elements_path, {"schema_version": "mvp-v1", "elements": updated_elements}),
            (ledger_path, ledger),
            (report_path, report),
        )
        return report
    except GenerationError as error:
        return error.to_dict()
    except OSError as error:
        return _io_error(error).to_dict()


def _validate_review_bundle(path: Path, reviewed: dict[str, Any], expected: dict[str, Any]) -> None:
    if reviewed.get("decision") not in {"keep", "reject"}:
        raise GenerationError(
            code="INVALID_FEEDBACK_REVIEW",
            message="feedback review decision must be keep or reject",
            details={"path": str(path), "field": "decision"},
        )
    if reviewed.get("notes") is None or not isinstance(reviewed.get("notes"), str):
        raise GenerationError(
            code="INVALID_FEEDBACK_REVIEW",
            message="feedback review notes must be a string",
            details={"path": str(path), "field": "notes"},
        )
    for field in ("category", "feedback_target"):
        if reviewed.get(field) != expected.get(field):
            raise GenerationError(
                code="INVALID_FEEDBACK_REVIEW",
                message=f"feedback review field '{field}' must match the generated template",
                details={"path": str(path), "field": field},
            )


def _apply_score_delta(
    active_elements: list[dict[str, Any]],
    reviewed: dict[str, Any],
    taxonomy: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    delta = 0.02 if reviewed["decision"] == "keep" else -0.02
    allowed = taxonomy["base_score"]
    target_ids = set(reviewed["feedback_target"]["selected_element_ids"])
    updated: list[dict[str, Any]] = []
    affected: list[dict[str, Any]] = []
    clamped_count = 0
    for element in active_elements:
        current = dict(element)
        if current["element_id"] not in target_ids:
            updated.append(current)
            continue
        old_score = float(current["base_score"])
        raw_score = round(old_score + delta, 4)
        new_score = min(max(raw_score, float(allowed["min"])), float(allowed["max"]))
        if new_score != raw_score:
            clamped_count += 1
        current["base_score"] = round(new_score, 4)
        updated.append(current)
        affected.append(
            {
                "element_id": current["element_id"],
                "old_base_score": old_score,
                "new_base_score": current["base_score"],
            }
        )
    validate_element_records(updated, taxonomy, path=Path("<feedback-apply>"))
    if len(affected) != len(target_ids):
        raise GenerationError(
            code="INVALID_FEEDBACK_REVIEW",
            message="feedback review references missing active element targets",
            details={"field": "selected_element_ids"},
        )
    return updated, affected, clamped_count
```

- [ ] **Step 4: Run the apply tests to verify they pass**

Run:

```bash
python -m unittest tests.test_feedback_loop.FeedbackApplyTest -v
```

Expected: PASS for keep apply and tamper rejection.

- [ ] **Step 5: Commit**

```bash
git add tests/test_feedback_loop.py tests/fixtures/feedback/dress temu_y2_women/feedback_loop.py
git commit -m "feat: apply concept feedback to active evidence"
```

### Task 3: Add rollback coverage, CLI entrypoint, and module-level regression

**Files:**
- Create: `temu_y2_women/feedback_loop_cli.py`
- Create: `tests/test_feedback_loop_cli.py`
- Modify: `tests/test_feedback_loop.py`
- Modify: `temu_y2_women/feedback_loop.py`

- [ ] **Step 1: Write failing CLI and rollback tests**

Create `tests/test_feedback_loop_cli.py`:

```python
from __future__ import annotations

import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


_FEEDBACK_FIXTURE_DIR = Path("tests/fixtures/feedback/dress")


class FeedbackLoopCliTest(unittest.TestCase):
    def test_prepare_cli_prints_review_and_writes_output(self) -> None:
        from temu_y2_women.feedback_loop_cli import main

        stdout = io.StringIO()
        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "review.json"
            with patch("sys.stdout", stdout):
                exit_code = main(["prepare", "--result", str(_FEEDBACK_FIXTURE_DIR / "result_success.json"), "--output", str(output_path)])

        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(stdout.getvalue()), _read_json(_FEEDBACK_FIXTURE_DIR / "expected_review_template.json"))

    def test_apply_cli_prints_failure_json(self) -> None:
        from temu_y2_women.feedback_loop_cli import main

        stdout = io.StringIO()
        with TemporaryDirectory() as temp_dir:
            with patch("sys.stdout", stdout):
                exit_code = main(
                    [
                        "apply",
                        "--reviewed",
                        str(_FEEDBACK_FIXTURE_DIR / "reviewed_keep.json"),
                        "--result",
                        str(_FEEDBACK_FIXTURE_DIR / "result_success.json"),
                        "--active-elements",
                        str(Path(temp_dir) / "missing-elements.json"),
                        "--ledger",
                        str(Path(temp_dir) / "ledger.json"),
                        "--report-output",
                        str(Path(temp_dir) / "report.json"),
                    ]
                )

        self.assertEqual(exit_code, 1)
        self.assertEqual(json.loads(stdout.getvalue())["error"]["code"], "FEEDBACK_IO_FAILED")
```

Extend `tests/test_feedback_loop.py` with a rollback test that points `report_path` at a missing directory and asserts `elements.json` and `feedback_ledger.json` stay unchanged.

- [ ] **Step 2: Run the new tests to verify they fail**

Run:

```bash
python -m unittest tests.test_feedback_loop_cli tests.test_feedback_loop.FeedbackApplyTest -v
```

Expected: FAIL because the CLI module does not exist and rollback behavior is not asserted yet.

- [ ] **Step 3: Implement the CLI and finish write-stage rollback behavior**

Create `temu_y2_women/feedback_loop_cli.py`:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from temu_y2_women.feedback_loop import (
    apply_reviewed_dress_concept_feedback,
    prepare_dress_concept_feedback,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare or apply review-gated dress concept feedback.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare", help="Build a concept feedback review template.")
    prepare.add_argument("--result", required=True, help="Path to a successful concept result JSON.")
    prepare.add_argument("--output", required=True, help="Path to write the feedback review JSON.")
    apply = subparsers.add_parser("apply", help="Apply reviewed concept feedback to active evidence.")
    apply.add_argument("--reviewed", required=True, help="Path to the reviewed feedback JSON.")
    apply.add_argument("--result", required=True, help="Path to the original successful concept result JSON.")
    apply.add_argument("--active-elements", required=True, help="Path to active elements.json.")
    apply.add_argument("--ledger", required=True, help="Path to feedback_ledger.json.")
    apply.add_argument("--report-output", required=True, help="Path to feedback_report.json.")
    args = parser.parse_args(argv)
    result = _run(args)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if "error" not in result else 1
```

Keep `_run`, `_write_json`, and argument-specific helpers in focused functions under 60 lines each. Reuse the temp-file/rollback helpers already written in `feedback_loop.py`; do not duplicate atomic-write logic in the CLI.

- [ ] **Step 4: Run the focused CLI tests to verify they pass**

Run:

```bash
python -m unittest tests.test_feedback_loop_cli -v
```

Expected: PASS for prepare success and apply failure JSON behavior.

- [ ] **Step 5: Commit**

```bash
git add temu_y2_women/feedback_loop_cli.py tests/test_feedback_loop_cli.py tests/test_feedback_loop.py temu_y2_women/feedback_loop.py
git commit -m "feat: add concept feedback cli"
```

### Task 4: Run full verification, update OpenSpec tasks, and prepare for PR shipping

**Files:**
- Modify: `openspec/changes/concept-feedback-loop/tasks.md`

- [ ] **Step 1: Mark the completed OpenSpec tasks**

Update `openspec/changes/concept-feedback-loop/tasks.md` so every implemented item flips from `- [ ]` to `- [x]`.

- [ ] **Step 2: Run focused workflow tests**

Run:

```bash
python -m unittest tests.test_feedback_loop tests.test_feedback_loop_cli -v
```

Expected: PASS.

- [ ] **Step 3: Run repository regression and guardrails**

Run:

```bash
python -m unittest
openspec validate concept-feedback-loop --type change --strict --no-interactive
openspec validate --specs --strict --no-interactive
python C:\Users\lxy\.codex\rules\hooks\validate_python_function_length.py .
```

Expected:
- `python -m unittest` -> all tests PASS
- `openspec validate concept-feedback-loop ...` -> `Change 'concept-feedback-loop' is valid`
- `openspec validate --specs ...` -> all specs PASS
- function-length hook -> `OK`

- [ ] **Step 4: Review the diff and commit the completed implementation**

Run:

```bash
git status --short --branch
git diff --stat
git add data/feedback/dress/feedback_ledger.json tests/fixtures/feedback/dress temu_y2_women/feedback_loop.py temu_y2_women/feedback_loop_cli.py tests/test_feedback_loop.py tests/test_feedback_loop_cli.py openspec/changes/concept-feedback-loop/tasks.md
git commit -m "feat: close the concept feedback loop"
```

- [ ] **Step 5: Ship on the branch workflow**

Run:

```bash
powershell -ExecutionPolicy Bypass -File C:\Users\lxy\.codex\skills\git-pr-ship\scripts\git_snapshot.ps1
```

Expected: clean worktree on `codex/concept-feedback-loop-spec` with local commits ready for push/PR creation.
