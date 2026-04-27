# One-shot Generate and Render CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dedicated one-shot CLI that reads a request JSON, generates a `dress` concept result, persists `concept_result.json`, and renders image artifacts from that persisted result in a single command.

**Architecture:** Keep the existing `temu_y2_women.cli` and `temu_y2_women.image_generation_cli` contracts unchanged. Add a small orchestration workflow that owns request loading, concept-result persistence, and render sequencing, then put a thin CLI wrapper in front of it so provider configuration is resolved only after the concept result has been written.

**Tech Stack:** Python 3 standard library, JSON files, `unittest`, existing `GenerationError`, existing `generate_dress_concept()`, existing `render_dress_concept_image()`, existing fake/OpenAI image providers, OpenSpec change files.

---

## File Map

- Create: `openspec/changes/add-generate-and-render-cli/.openspec.yaml`
  - OpenSpec change metadata for the new feature.
- Create: `openspec/changes/add-generate-and-render-cli/proposal.md`
  - Why/what/impact summary for the change.
- Create: `openspec/changes/add-generate-and-render-cli/design.md`
  - OpenSpec-local design summary aligned to the approved design doc.
- Create: `openspec/changes/add-generate-and-render-cli/tasks.md`
  - Checklist for implementation and verification.
- Create: `openspec/changes/add-generate-and-render-cli/specs/image-generation-output/spec.md`
  - Requirement delta that adds the one-shot CLI behavior to the existing image-generation capability.
- Create: `temu_y2_women/generate_and_render_workflow.py`
  - Focused orchestration layer for request loading, concept-result persistence, and render dispatch.
- Create: `temu_y2_women/generate_and_render_cli.py`
  - Thin CLI wrapper that parses args, constructs a delayed provider factory, and prints JSON.
- Create: `tests/test_generate_and_render_workflow.py`
  - Workflow regression tests for success, invalid input, generation error, concept-result output failure, and render failure.
- Create: `tests/test_generate_and_render_cli.py`
  - CLI regression tests for fake-provider success, OpenAI config failure after persistence, and module entrypoint execution.

### Task 1: Scaffold the OpenSpec change for the approved one-shot CLI

**Files:**
- Create: `openspec/changes/add-generate-and-render-cli/.openspec.yaml`
- Create: `openspec/changes/add-generate-and-render-cli/proposal.md`
- Create: `openspec/changes/add-generate-and-render-cli/design.md`
- Create: `openspec/changes/add-generate-and-render-cli/tasks.md`
- Create: `openspec/changes/add-generate-and-render-cli/specs/image-generation-output/spec.md`

- [ ] **Step 1: Write the OpenSpec change files**

Create `openspec/changes/add-generate-and-render-cli/.openspec.yaml`:

```yaml
schema: spec-driven
created: 2026-04-27
```

Create `openspec/changes/add-generate-and-render-cli/proposal.md`:

```markdown
## Why

The repository can already generate stable `dress` concept results and can already render an image from a saved successful result, but operators still have to run those as two separate commands. We need a one-shot path now so experiments can reach visible image output faster without changing the existing deterministic generation CLI or the existing saved-result render CLI.

## What Changes

- Add a dedicated one-shot workflow that reads a request JSON, generates a successful concept result, persists `concept_result.json`, and then renders image artifacts from that persisted result.
- Add a dedicated CLI for the one-shot workflow with the same provider options currently exposed by the saved-result render CLI.
- Preserve fail-closed render artifact behavior while keeping a successfully written `concept_result.json` when render-stage setup or provider dispatch fails.
- Add workflow and CLI regression coverage for success, invalid input, output-write failure, provider-config failure, and module entrypoint execution.

## Capabilities

### Modified Capabilities
- `image-generation-output`: add a one-shot CLI path that generates and renders in one command while preserving the existing two-step commands.

## Impact

- Adds one new workflow module and one new CLI module.
- Adds new regression coverage for the one-shot path.
- Adds an OpenSpec delta for one-shot generate-and-render behavior without changing the existing saved-result render contract.
```

Create `openspec/changes/add-generate-and-render-cli/design.md`:

```markdown
## Context

The repository already has two stable steps:

1. `python -m temu_y2_women.cli --input <request.json>`
2. `python -m temu_y2_women.image_generation_cli --result <result.json> --output-dir <dir>`

The missing slice is a shorter command that reaches the same rendered output without breaking either existing contract.

## Goals / Non-Goals

**Goals:**
- Add a dedicated one-shot CLI instead of changing the behavior of `temu_y2_women.cli`.
- Persist a readable `concept_result.json` before the render stage begins.
- Reuse the existing image-render workflow and its artifact contract.
- Preserve `concept_result.json` if provider configuration or provider execution fails after generation succeeds.

**Non-Goals:**
- Replacing the existing two-step workflow.
- Adding gallery/review UI or batch execution.
- Introducing new image providers.
- Adding a new render-report schema.

## Decisions

### 1. Add a new CLI instead of extending `temu_y2_women.cli`

This keeps the existing deterministic generation CLI stable and avoids surprising downstream consumers that expect raw concept-result JSON on stdout.

### 2. Add a small orchestration workflow instead of embedding logic in the CLI

The workflow will own request loading, concept generation, `concept_result.json` persistence, delayed provider creation, and render dispatch. The CLI will stay limited to argument parsing and JSON printing.

### 3. Delay provider construction until after `concept_result.json` is written

The provider factory must be called after concept-result persistence so provider-config errors still leave a reusable `concept_result.json` behind.

### 4. Keep stdout aligned with the existing render CLI

The one-shot CLI will print the final render report JSON on success and a structured error payload on failure. It will not add a separate one-shot report file.
```

Create `openspec/changes/add-generate-and-render-cli/tasks.md`:

```markdown
## 1. One-shot workflow

- [ ] 1.1 Add a dedicated workflow that loads a request JSON, generates a concept result, persists `concept_result.json`, and renders from that persisted result
- [ ] 1.2 Add structured invalid-input and concept-result-output failure handling while preserving `concept_result.json` on render-stage failures
- [ ] 1.3 Add workflow regression coverage for success, generation error, invalid input, concept-result output failure, and render failure

## 2. One-shot CLI

- [ ] 2.1 Add a dedicated CLI that accepts request input, output directory, and provider options
- [ ] 2.2 Resolve provider configuration only after `concept_result.json` has been written
- [ ] 2.3 Add CLI regression coverage for fake-provider success, OpenAI config failure, and module entrypoint execution outside the repo root

## 3. Verification and completion

- [ ] 3.1 Run focused workflow/CLI tests plus the full repository test suite
- [ ] 3.2 Run OpenSpec validation and the Python function-length guard
- [ ] 3.3 Mark the change tasks complete after all validation passes
```

Create `openspec/changes/add-generate-and-render-cli/specs/image-generation-output/spec.md`:

```markdown
## ADDED Requirements

### Requirement: One-shot generate-and-render CLI
The system SHALL provide a dedicated CLI that reads a `dress` request JSON, persists a successful concept result as `concept_result.json`, and renders image artifacts from that persisted result in one command.

#### Scenario: One-shot CLI writes the persisted concept result and render artifacts
- **WHEN** an operator runs the one-shot CLI with a valid `dress` request JSON, an output directory, and a valid image provider configuration
- **THEN** the workflow writes `concept_result.json`, `rendered_image.png`, and `image_render_report.json`
- **AND** the CLI prints the final render report JSON and exits successfully

#### Scenario: Generation failure stops before any output is written
- **WHEN** concept generation returns a structured error for the request input
- **THEN** the one-shot workflow returns that structured error
- **AND** it writes no local output artifacts

#### Scenario: Invalid request input is rejected before generation
- **WHEN** the one-shot workflow cannot read the request file, the JSON is invalid, or the request root is not an object
- **THEN** it returns a structured invalid-input error
- **AND** it writes no local output artifacts

#### Scenario: Render-stage failure preserves the persisted concept result
- **WHEN** concept generation succeeds and `concept_result.json` is written, but provider configuration, provider dispatch, or render output publication fails afterward
- **THEN** the workflow returns a structured render-stage error
- **AND** it keeps the successful `concept_result.json`
- **AND** it leaves no partial final render bundle behind
```

- [ ] **Step 2: Validate the new OpenSpec change**

Run:

```bash
openspec validate --strict --no-interactive
```

Expected: PASS with no validation errors for `add-generate-and-render-cli`.

- [ ] **Step 3: Commit the change scaffold**

```bash
git add openspec/changes/add-generate-and-render-cli/.openspec.yaml openspec/changes/add-generate-and-render-cli/proposal.md openspec/changes/add-generate-and-render-cli/design.md openspec/changes/add-generate-and-render-cli/tasks.md openspec/changes/add-generate-and-render-cli/specs/image-generation-output/spec.md
git commit -m "docs(openspec): propose one-shot generate and render cli"
```

### Task 2: Add the one-shot workflow success path and persisted concept-result artifact

**Files:**
- Create: `temu_y2_women/generate_and_render_workflow.py`
- Create: `tests/test_generate_and_render_workflow.py`

- [ ] **Step 1: Write the failing workflow success test**

Create `tests/test_generate_and_render_workflow.py`:

```python
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
```

- [ ] **Step 2: Run the targeted test to verify it fails**

Run:

```bash
python -m unittest tests.test_generate_and_render_workflow.GenerateAndRenderWorkflowSuccessTest -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'temu_y2_women.generate_and_render_workflow'`.

- [ ] **Step 3: Add the minimal workflow implementation**

Create `temu_y2_women/generate_and_render_workflow.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from temu_y2_women.image_generation_output import ImageProvider
from temu_y2_women.image_generation_workflow import render_dress_concept_image
from temu_y2_women.orchestrator import generate_dress_concept

_CONCEPT_RESULT_FILENAME = "concept_result.json"

ImageProviderFactory = Callable[[], ImageProvider]


def generate_and_render_dress_concept(
    request_path: Path,
    output_dir: Path,
    provider_factory: ImageProviderFactory,
) -> dict[str, Any]:
    payload = _load_request_payload(request_path)
    concept_result = generate_dress_concept(payload)
    if "error" in concept_result:
        return concept_result
    result_path = _write_concept_result(output_dir, concept_result)
    return render_dress_concept_image(
        result_path=result_path,
        output_dir=output_dir,
        provider=provider_factory(),
    )


def _load_request_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return payload
    raise ValueError("generate-and-render input root must be an object")


def _write_concept_result(output_dir: Path, concept_result: dict[str, Any]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / _CONCEPT_RESULT_FILENAME
    result_path.write_text(json.dumps(concept_result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result_path
```

- [ ] **Step 4: Run the workflow success test to verify it passes**

Run:

```bash
python -m unittest tests.test_generate_and_render_workflow.GenerateAndRenderWorkflowSuccessTest -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add temu_y2_women/generate_and_render_workflow.py tests/test_generate_and_render_workflow.py
git commit -m "feat(image): add one-shot generate and render workflow"
```

### Task 3: Harden the workflow error handling and preserve concept results on render-stage failures

**Files:**
- Modify: `temu_y2_women/generate_and_render_workflow.py`
- Modify: `tests/test_generate_and_render_workflow.py`

- [ ] **Step 1: Add the failing workflow error-handling tests**

Append these tests to `tests/test_generate_and_render_workflow.py`:

```python
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

    def test_generate_and_render_returns_generation_error_without_outputs(self) -> None:
        from temu_y2_women.generate_and_render_workflow import generate_and_render_dress_concept
        from temu_y2_women.image_generation_output import FakeImageProvider

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "render-output"
            result = generate_and_render_dress_concept(
                request_path=_FAILURE_FIXTURE_PATH,
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
            self.assertFalse((output_dir / "rendered_image.png").exists())
            self.assertFalse((output_dir / "image_render_report.json").exists())


class _ExplodingProvider:
    def render(self, render_input: object) -> object:
        raise RuntimeError("provider boom")
```

- [ ] **Step 2: Run the targeted workflow tests to verify they fail**

Run:

```bash
python -m unittest tests.test_generate_and_render_workflow.GenerateAndRenderWorkflowFailureTest -v
```

Expected: FAIL because the current workflow raises raw exceptions instead of returning structured input/output errors.

- [ ] **Step 3: Add structured input/output error handling and staged concept-result publication**

Replace `temu_y2_women/generate_and_render_workflow.py` with:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from temu_y2_women.errors import GenerationError
from temu_y2_women.image_generation_output import ImageProvider
from temu_y2_women.image_generation_workflow import render_dress_concept_image
from temu_y2_women.orchestrator import generate_dress_concept

_CONCEPT_RESULT_FILENAME = "concept_result.json"
_INVALID_INPUT_CODE = "INVALID_GENERATE_AND_RENDER_INPUT"

ImageProviderFactory = Callable[[], ImageProvider]


def generate_and_render_dress_concept(
    request_path: Path,
    output_dir: Path,
    provider_factory: ImageProviderFactory,
) -> dict[str, Any]:
    try:
        payload = _load_request_payload(request_path)
        concept_result = generate_dress_concept(payload)
        if "error" in concept_result:
            return concept_result
        result_path = _write_concept_result(output_dir, concept_result)
        return render_dress_concept_image(
            result_path=result_path,
            output_dir=output_dir,
            provider=provider_factory(),
        )
    except GenerationError as error:
        return error.to_dict()
    except OSError as error:
        return _concept_result_output_error(output_dir, error).to_dict()


def _load_request_payload(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise _invalid_input_error(path, "request", "generate-and-render input could not be read") from error
    except json.JSONDecodeError as error:
        raise _invalid_input_error(path, "request", "generate-and-render input must contain valid JSON") from error
    if isinstance(payload, dict):
        return payload
    raise _invalid_input_error(path, "request", "generate-and-render input root must be an object")


def _write_concept_result(output_dir: Path, concept_result: dict[str, Any]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / _CONCEPT_RESULT_FILENAME
    temp_path = result_path.with_suffix(f"{result_path.suffix}.tmp")
    temp_path.write_text(json.dumps(concept_result, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        temp_path.replace(result_path)
    except OSError:
        _cleanup_file(temp_path)
        raise
    return result_path


def _cleanup_file(path: Path) -> None:
    if path.exists():
        path.unlink()


def _invalid_input_error(path: Path, field: str, message: str) -> GenerationError:
    return GenerationError(
        code=_INVALID_INPUT_CODE,
        message=message,
        details={"path": str(path), "field": field},
    )


def _concept_result_output_error(output_dir: Path, error: OSError) -> GenerationError:
    return GenerationError(
        code="CONCEPT_RESULT_OUTPUT_FAILED",
        message="failed to write concept result output",
        details={"path": str(output_dir / _CONCEPT_RESULT_FILENAME), "reason": str(error)},
    )
```

- [ ] **Step 4: Run the workflow tests to verify they pass**

Run:

```bash
python -m unittest tests.test_generate_and_render_workflow -v
```

Expected: PASS for both success and failure coverage.

- [ ] **Step 5: Commit**

```bash
git add temu_y2_women/generate_and_render_workflow.py tests/test_generate_and_render_workflow.py
git commit -m "fix(image): harden one-shot workflow error handling"
```

### Task 4: Add the one-shot CLI and prove delayed provider resolution through CLI tests

**Files:**
- Create: `temu_y2_women/generate_and_render_cli.py`
- Create: `tests/test_generate_and_render_cli.py`

- [ ] **Step 1: Write the failing CLI regression tests**

Create `tests/test_generate_and_render_cli.py`:

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


_REQUEST_FIXTURE_PATH = Path("tests/fixtures/requests/dress-generation-mvp/success-summer-vacation-mode-a.json")


class GenerateAndRenderCliTest(unittest.TestCase):
    def test_cli_prints_render_report_and_writes_outputs_with_fake_provider(self) -> None:
        from temu_y2_women.generate_and_render_cli import main

        stdout = io.StringIO()
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "render-output"
            with patch("sys.stdout", stdout):
                exit_code = main(
                    [
                        "--input",
                        str(_REQUEST_FIXTURE_PATH),
                        "--output-dir",
                        str(output_dir),
                        "--provider",
                        "fake",
                    ]
                )

            payload = json.loads(stdout.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["provider"], "fake")
            self.assertTrue((output_dir / "concept_result.json").exists())
            self.assertTrue((output_dir / "rendered_image.png").exists())

    def test_cli_returns_provider_config_error_after_persisting_concept_result(self) -> None:
        from temu_y2_women.generate_and_render_cli import main

        stdout = io.StringIO()
        with TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True):
            output_dir = Path(temp_dir) / "render-output"
            with patch("sys.stdout", stdout):
                exit_code = main(
                    [
                        "--input",
                        str(_REQUEST_FIXTURE_PATH),
                        "--output-dir",
                        str(output_dir),
                        "--provider",
                        "openai",
                    ]
                )

            payload = json.loads(stdout.getvalue())
            self.assertEqual(exit_code, 1)
            self.assertEqual(payload["error"]["code"], "INVALID_IMAGE_PROVIDER_CONFIG")
            self.assertTrue((output_dir / "concept_result.json").exists())
            self.assertFalse((output_dir / "rendered_image.png").exists())
            self.assertFalse((output_dir / "image_render_report.json").exists())

    def test_cli_module_entrypoint_runs_outside_repo_root_with_fake_provider(self) -> None:
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "render-output"
            env = dict(os.environ)
            repo_root = Path.cwd()
            env["PYTHONPATH"] = str(repo_root)
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "temu_y2_women.generate_and_render_cli",
                    "--input",
                    str((repo_root / _REQUEST_FIXTURE_PATH).resolve()),
                    "--output-dir",
                    str(output_dir),
                    "--provider",
                    "fake",
                ],
                capture_output=True,
                cwd=temp_dir,
                env=env,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0)
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["provider"], "fake")
            self.assertTrue((output_dir / "concept_result.json").exists())
```

- [ ] **Step 2: Run the targeted CLI tests to verify they fail**

Run:

```bash
python -m unittest tests.test_generate_and_render_cli -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'temu_y2_women.generate_and_render_cli'`.

- [ ] **Step 3: Implement the CLI with delayed provider factories**

Create `temu_y2_women/generate_and_render_cli.py`:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable, Sequence

from temu_y2_women.generate_and_render_workflow import generate_and_render_dress_concept
from temu_y2_women.image_generation_openai import build_openai_image_provider
from temu_y2_women.image_generation_output import FakeImageProvider, ImageProvider


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a dress concept and render its image artifacts.")
    parser.add_argument("--input", required=True, help="Path to the request JSON file.")
    parser.add_argument("--output-dir", required=True, help="Directory for generated concept and render artifacts.")
    parser.add_argument("--provider", choices=("fake", "openai"), default="openai", help="Image provider to use.")
    parser.add_argument("--model", default="gpt-image-1", help="Image model name for the OpenAI provider.")
    parser.add_argument("--size", default="1024x1536", help="Image size for the OpenAI provider.")
    parser.add_argument("--quality", default="high", help="Image quality for the OpenAI provider.")
    parser.add_argument("--background", default="auto", help="Background mode for the OpenAI provider.")
    parser.add_argument("--style", default="natural", help="Image style for the OpenAI provider.")
    args = parser.parse_args(argv)
    result = generate_and_render_dress_concept(
        request_path=Path(args.input),
        output_dir=Path(args.output_dir),
        provider_factory=_provider_factory_from_args(args),
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0 if "error" not in result else 1


def _provider_factory_from_args(args: argparse.Namespace) -> Callable[[], ImageProvider]:
    if args.provider == "fake":
        return FakeImageProvider
    return lambda: build_openai_image_provider(
        model=args.model,
        size=args.size,
        quality=args.quality,
        background=args.background,
        style=args.style,
    )


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the CLI and workflow tests to verify they pass**

Run:

```bash
python -m unittest tests.test_generate_and_render_cli tests.test_generate_and_render_workflow -v
```

Expected: PASS for all one-shot CLI and workflow tests.

- [ ] **Step 5: Commit**

```bash
git add temu_y2_women/generate_and_render_cli.py tests/test_generate_and_render_cli.py
git commit -m "feat(image): add one-shot generate and render cli"
```

### Task 5: Mark the OpenSpec change complete and run the full verification suite

**Files:**
- Modify: `openspec/changes/add-generate-and-render-cli/tasks.md`

- [ ] **Step 1: Mark the OpenSpec tasks complete**

Replace `openspec/changes/add-generate-and-render-cli/tasks.md` with:

```markdown
## 1. One-shot workflow

- [x] 1.1 Add a dedicated workflow that loads a request JSON, generates a concept result, persists `concept_result.json`, and renders from that persisted result
- [x] 1.2 Add structured invalid-input and concept-result-output failure handling while preserving `concept_result.json` on render-stage failures
- [x] 1.3 Add workflow regression coverage for success, generation error, invalid input, concept-result output failure, and render failure

## 2. One-shot CLI

- [x] 2.1 Add a dedicated CLI that accepts request input, output directory, and provider options
- [x] 2.2 Resolve provider configuration only after `concept_result.json` has been written
- [x] 2.3 Add CLI regression coverage for fake-provider success, OpenAI config failure, and module entrypoint execution outside the repo root

## 3. Verification and completion

- [x] 3.1 Run focused workflow/CLI tests plus the full repository test suite
- [x] 3.2 Run OpenSpec validation and the Python function-length guard
- [x] 3.3 Mark the change tasks complete after all validation passes
```

- [ ] **Step 2: Run repository verification**

Run:

```bash
python -m unittest
openspec validate --specs --strict --no-interactive
python C:\Users\lxy\.codex\rules\hooks\validate_python_function_length.py .
```

Expected:
- `python -m unittest` exits `0`
- `openspec validate --specs --strict --no-interactive` exits `0`
- function-length guard exits `0`

- [ ] **Step 3: Commit the completion update**

```bash
git add openspec/changes/add-generate-and-render-cli/tasks.md
git commit -m "chore(openspec): complete one-shot generate and render change"
```
