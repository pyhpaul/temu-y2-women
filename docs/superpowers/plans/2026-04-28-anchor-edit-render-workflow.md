# Anchor + Edit Render Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current six independent image generations with an explicit `hero_front generate + remaining jobs edit from hero_front` workflow that fails fast on consistency-chain errors.

**Architecture:** Extend the prompt bundle contract so each render job declares its execution strategy and reference source, then teach the workflow to cache anchor image bytes and dispatch either `images.generate` or `images.edit` through the OpenAI-compatible provider. Keep legacy single-image inputs readable and keep the dual-key routing semantics aligned with `generate` vs `edit`.

**Tech Stack:** Python 3 standard library, existing prompt/workflow modules, OpenAI Python SDK image APIs, `unittest`, PowerShell smoke commands.

---

## File Map

- Modify: `temu_y2_women/prompt_renderer.py`
  - Produce `visual-prompt-v2` jobs with `render_strategy` and `reference_prompt_id`.
- Modify: `temu_y2_women/image_generation_output.py`
  - Parse the new job contract and carry runtime reference image bytes.
- Modify: `temu_y2_women/image_generation_openai.py`
  - Add OpenAI-compatible `images.edit` execution.
- Modify: `temu_y2_women/image_generation_workflow.py`
  - Execute `generate` then `edit` sequentially with cached reference bytes and fail-fast behavior.
- Modify: `tests/test_prompt_renderer.py`
- Modify: `tests/test_image_generation_output.py`
- Modify: `tests/test_image_generation_openai.py`
- Modify: `tests/test_image_generation_workflow.py`
- Optional verify-only: `tests/test_generate_and_render_cli.py`, `tests/test_generate_and_render_workflow.py`

### Task 1: Upgrade the render job contract to an explicit execution plan

**Files:**
- Modify: `temu_y2_women/prompt_renderer.py`
- Modify: `temu_y2_women/image_generation_output.py`
- Modify: `tests/test_prompt_renderer.py`
- Modify: `tests/test_image_generation_output.py`

- [ ] **Step 1: Write the failing prompt renderer assertions**

```python
def test_render_mode_a_uses_anchor_generate_and_edit_jobs(self) -> None:
    bundle = render_prompt_bundle(
        request=_request(mode="A"),
        concept=_concept(),
        selected_strategies=(_strategy(),),
        warnings=(),
    )
    self.assertEqual(bundle["template_version"], "visual-prompt-v2")
    render_jobs = bundle["render_jobs"]
    self.assertEqual(render_jobs[0]["render_strategy"], "generate")
    self.assertIsNone(render_jobs[0]["reference_prompt_id"])
    self.assertTrue(all(item["render_strategy"] == "edit" for item in render_jobs[1:]))
    self.assertTrue(all(item["reference_prompt_id"] == "hero_front" for item in render_jobs[1:]))
```

```python
def test_load_dress_image_render_input_reads_render_strategy_fields(self) -> None:
    render_input = load_dress_image_render_input(result_path)
    self.assertEqual(render_input.render_jobs[0].render_strategy, "generate")
    self.assertIsNone(render_input.render_jobs[0].reference_prompt_id)
    self.assertEqual(render_input.render_jobs[1].render_strategy, "edit")
    self.assertEqual(render_input.render_jobs[1].reference_prompt_id, "hero_front")
```

- [ ] **Step 2: Run the focused suites and confirm failure**

Run: `python -m unittest tests.test_prompt_renderer tests.test_image_generation_output -v`

Expected:
- `FAIL` on missing `visual-prompt-v2`
- `FAIL` on missing `render_strategy`
- `FAIL` on missing `reference_prompt_id`

- [ ] **Step 3: Implement the new job contract and legacy defaults**

```python
return {
    "prompt_id": prompt_id,
    "group": "hero",
    "output_name": output_name,
    "prompt": _build_prompt(...),
    "render_strategy": "generate" if prompt_id == "hero_front" else "edit",
    "reference_prompt_id": None if prompt_id == "hero_front" else "hero_front",
}
```

```python
@dataclass(frozen=True, slots=True)
class ImageRenderJob:
    prompt_id: str
    group: str
    output_name: str
    prompt: str
    render_strategy: str = "generate"
    reference_prompt_id: str | None = None
```

```python
@dataclass(frozen=True, slots=True)
class ImageRenderInput:
    source_result_path: Path
    category: str
    mode: str
    prompt: str
    prompt_id: str
    group: str
    output_name: str
    render_strategy: str
    reference_prompt_id: str | None
    reference_image_bytes: bytes | None
    render_notes: tuple[str, ...]
    render_jobs: tuple[ImageRenderJob, ...]
```

- [ ] **Step 4: Re-run the focused suites until green**

Run: `python -m unittest tests.test_prompt_renderer tests.test_image_generation_output -v`

Expected:
- `PASS`
- legacy single-image tests still green

- [ ] **Step 5: Commit**

```bash
git add temu_y2_women/prompt_renderer.py temu_y2_women/image_generation_output.py tests/test_prompt_renderer.py tests/test_image_generation_output.py
git commit -m "feat(image): define anchor-edit render jobs"
```

### Task 2: Add OpenAI-compatible image edit execution

**Files:**
- Modify: `temu_y2_women/image_generation_openai.py`
- Modify: `tests/test_image_generation_openai.py`

- [ ] **Step 1: Write the failing provider tests for edit execution**

```python
def test_openai_provider_uses_images_edit_for_edit_jobs(self) -> None:
    provider = build_routed_openai_image_provider(
        ResolvedOpenAIProviderConfigs(
            default_config=_resolved_config("anchor-key"),
            expansion_config=_resolved_config("expansion-key"),
        ),
        client_factory=_recording_client_factory,
    )
    result = provider.render(_render_input("hero_back", "edit", b"anchor-bytes"))
    self.assertEqual(result.image_bytes, b"expansion-edit")
    self.assertEqual(self.calls[-1]["method"], "edit")
    self.assertEqual(self.calls[-1]["kwargs"]["input_fidelity"], "high")
```

```python
def test_openai_provider_rejects_edit_without_reference_bytes(self) -> None:
    with self.assertRaises(GenerationError) as error_context:
        provider.render(_render_input("hero_back", "edit", None))
    self.assertEqual(error_context.exception.details["field"], "reference_image_bytes")
```

- [ ] **Step 2: Run the focused provider suite and confirm failure**

Run: `python -m unittest tests.test_image_generation_openai -v`

Expected:
- `FAIL` because provider only calls `images.generate`
- `FAIL` because edit validation does not exist

- [ ] **Step 3: Implement generate/edit dispatch inside the provider**

```python
def render(self, render_input: object) -> ImageProviderResult:
    if getattr(render_input, "render_strategy", "generate") == "edit":
        return self._render_edit(render_input)
    return self._render_generate(render_input)
```

```python
def _render_edit(self, render_input: object) -> ImageProviderResult:
    reference_bytes = _required_reference_bytes(render_input)
    response = self._client.images.edit(
        image=("reference.png", reference_bytes, "image/png"),
        prompt=getattr(render_input, "prompt"),
        model=self._config.model,
        size=self._config.size,
        quality=self._config.quality,
        input_fidelity="high",
        response_format="b64_json",
    )
    return _provider_result_from_response(response, self._config)
```

- [ ] **Step 4: Re-run the provider suite until green**

Run: `python -m unittest tests.test_image_generation_openai -v`

Expected:
- `PASS`
- both routed-key tests and edit-path tests green

- [ ] **Step 5: Commit**

```bash
git add temu_y2_women/image_generation_openai.py tests/test_image_generation_openai.py
git commit -m "feat(image): add openai-compatible edit execution"
```

### Task 3: Convert the workflow from stateless fan-out to anchor-then-edit sequencing

**Files:**
- Modify: `temu_y2_women/image_generation_workflow.py`
- Modify: `tests/test_image_generation_workflow.py`

- [ ] **Step 1: Write the failing workflow tests**

```python
def test_render_dress_concept_image_runs_edit_jobs_with_anchor_reference(self) -> None:
    result = render_dress_concept_image(
        result_path=result_path,
        output_dir=output_dir,
        provider=_RecordingWorkflowProvider(),
    )
    self.assertEqual(
        _RecordingWorkflowProvider.calls,
        [
            ("hero_front", "generate", None),
            ("hero_back", "edit", b"hero_front-bytes"),
        ],
    )
    self.assertEqual(result["images"][1]["render_strategy"], "edit")
    self.assertEqual(result["images"][1]["reference_prompt_id"], "hero_front")
```

```python
def test_render_dress_concept_image_fails_fast_when_reference_is_missing(self) -> None:
    result = render_dress_concept_image(
        result_path=result_path,
        output_dir=output_dir,
        provider=_MissingReferenceProvider(),
    )
    self.assertEqual(result["error"]["code"], "IMAGE_PROVIDER_FAILED")
    self.assertFalse((output_dir / "hero_back.png").exists())
```

- [ ] **Step 2: Run the focused workflow suite and confirm failure**

Run: `python -m unittest tests.test_image_generation_workflow -v`

Expected:
- `FAIL` because current workflow does not cache anchor bytes
- `FAIL` because report entries do not include `render_strategy`

- [ ] **Step 3: Implement sequential execution with cached references and fail-fast**

```python
def _render_bundle(provider: ImageProvider, render_input: ImageRenderInput) -> list[dict[str, Any]]:
    rendered_images: list[dict[str, Any]] = []
    rendered_bytes: dict[str, bytes] = {}
    for job in render_input.render_jobs:
        job_input = _job_render_input(render_input, job, rendered_bytes.get(job.reference_prompt_id or ""))
        provider_result = _render_with_provider(provider, job_input)
        rendered_bytes[job.prompt_id] = provider_result.image_bytes
        rendered_images.append(
            {
                "prompt_id": job.prompt_id,
                "group": job.group,
                "output_name": job.output_name,
                "render_strategy": job.render_strategy,
                "reference_prompt_id": job.reference_prompt_id,
                "prompt_fingerprint": _fingerprint(job.prompt),
                "image_bytes": provider_result.image_bytes,
                "provider": provider_result.provider_name,
                "model": provider_result.model,
                "base_url": provider_result.base_url,
                "mime_type": provider_result.mime_type,
            }
        )
    return rendered_images
```

```python
def _job_render_input(
    render_input: ImageRenderInput,
    job: ImageRenderJob,
    reference_image_bytes: bytes | None,
) -> ImageRenderInput:
    return ImageRenderInput(
        source_result_path=render_input.source_result_path,
        category=render_input.category,
        mode=render_input.mode,
        prompt=job.prompt,
        prompt_id=job.prompt_id,
        group=job.group,
        output_name=job.output_name,
        render_strategy=job.render_strategy,
        reference_prompt_id=job.reference_prompt_id,
        reference_image_bytes=reference_image_bytes,
        render_notes=render_input.render_notes,
        render_jobs=(job,),
    )
```

- [ ] **Step 4: Re-run the workflow suite until green**

Run: `python -m unittest tests.test_image_generation_workflow -v`

Expected:
- `PASS`
- report entries include `render_strategy` and `reference_prompt_id`

- [ ] **Step 5: Commit**

```bash
git add temu_y2_women/image_generation_workflow.py tests/test_image_generation_workflow.py
git commit -m "feat(image): run anchor-edit render workflow sequentially"
```

### Task 4: Regression verification and real smoke test

**Files:**
- Verify only

- [ ] **Step 1: Run the full targeted regression suite**

Run: `python -m unittest tests.test_prompt_renderer tests.test_image_generation_output tests.test_image_generation_openai tests.test_image_generation_workflow tests.test_generate_and_render_cli tests.test_generate_and_render_workflow -v`

Expected: `PASS`

- [ ] **Step 2: Run syntax validation**

Run: `python -m py_compile temu_y2_women\prompt_renderer.py temu_y2_women\image_generation_output.py temu_y2_women\image_generation_openai.py temu_y2_women\image_generation_workflow.py tests\test_prompt_renderer.py tests\test_image_generation_output.py tests\test_image_generation_openai.py tests\test_image_generation_workflow.py`

Expected: no output

- [ ] **Step 3: Run function-length validation**

Run: `python C:\Users\lxy\.codex\rules\hooks\validate_python_function_length.py .`

Expected: `OK`

- [ ] **Step 4: Run a real two-job smoke test (`hero_front generate` + `hero_back edit`)**

Run:

```powershell
$envMap = @{}
Get-Content .env | ForEach-Object {
  if ($_ -match '^(.*?)=(.*)$') { $envMap[$matches[1]] = $matches[2] }
}
$tempDir = Join-Path $env:TEMP 'temu-anchor-edit-smoke'
Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $tempDir | Out-Null
$resultPath = Join-Path $tempDir 'result_two_jobs.json'
$payload = Get-Content tests\fixtures\feedback\dress\result_success.json -Raw | ConvertFrom-Json -AsHashtable
$payload['prompt_bundle']['render_jobs'] = @(
  @{
    prompt_id = 'hero_front'
    group = 'hero'
    output_name = 'hero_front.png'
    prompt = 'studio fashion product photo of a tiny red circle on a white background'
    render_strategy = 'generate'
    reference_prompt_id = $null
  },
  @{
    prompt_id = 'hero_back'
    group = 'hero'
    output_name = 'hero_back.png'
    prompt = 'Keep the exact same garment identity and only rotate to a back view. Preserve silhouette, print placement, fabric, and styling.'
    render_strategy = 'edit'
    reference_prompt_id = 'hero_front'
  }
)
$payload | ConvertTo-Json -Depth 20 | Set-Content -Path $resultPath -Encoding UTF8
$env:OPENAI_COMPAT_BASE_URL = $envMap['OPENAI_COMPAT_BASE_URL']
$env:OPENAI_COMPAT_ANCHOR_API_KEY = $envMap['OPENAI_COMPAT_ANCHOR_API_KEY']
$env:OPENAI_COMPAT_EXPANSION_API_KEY = $envMap['OPENAI_COMPAT_EXPANSION_API_KEY']
python -m temu_y2_women.image_generation_cli --result $resultPath --output-dir (Join-Path $tempDir 'out') --provider openai --model gpt-image-2
```

Expected:
- exit code `0`
- outputs include `hero_front.png` and `hero_back.png`
- second image entry reports `render_strategy = "edit"`

- [ ] **Step 5: Review final diff and commit any remaining fixture/test updates**

Run: `git diff --stat`

Expected: only prompt contract, provider, workflow, tests, and docs for this change
