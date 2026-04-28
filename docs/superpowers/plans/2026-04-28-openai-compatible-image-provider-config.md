# OpenAI-Compatible Image Provider Config Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let both image-generation CLIs resolve OpenAI-compatible endpoint settings from CLI arguments, environment variables, and local Codex config files without changing the six-image generation chain.

**Architecture:** Add a small shared config-resolution module, move OpenAI provider environment lookup out of the provider layer, wire both CLIs to the shared resolver, and extend render reports so the resolved `base_url` is visible while credentials stay hidden.

**Tech Stack:** Python 3 standard library, `tomllib`, JSON files, `unittest`, existing image generation workflows, OpenAI Python SDK.

---

## File Map

- Create: `temu_y2_women/image_provider_config.py`
  - Shared OpenAI-compatible provider config resolution.
- Modify: `temu_y2_women/image_generation_openai.py`
  - Accept resolved config including `base_url`.
- Modify: `temu_y2_women/generate_and_render_cli.py`
  - Add `--base-url` and `--api-key`, use shared resolver.
- Modify: `temu_y2_women/image_generation_cli.py`
  - Add `--base-url` and `--api-key`, use shared resolver.
- Modify: `temu_y2_women/image_generation_workflow.py`
  - Surface resolved `base_url` in render reports.
- Modify: `tests/test_image_generation_openai.py`
- Modify: `tests/test_generate_and_render_cli.py`
- Modify: `tests/test_image_generation_cli.py`
- Create: `tests/test_image_provider_config.py`

### Task 1: Add shared OpenAI-compatible config resolution

**Files:**
- Create: `temu_y2_women/image_provider_config.py`
- Create: `tests/test_image_provider_config.py`

- [ ] **Step 1: Write the failing resolver tests**

```python
def test_resolve_openai_provider_config_reads_auth_json_and_config_toml(self) -> None:
    resolved = resolve_openai_provider_config(
        ProviderCliOptions(),
        codex_home=self.codex_home,
        environ={},
    )
    self.assertEqual(resolved.api_key, "fixture-key")
    self.assertEqual(resolved.base_url, "https://example.test")
```

```python
def test_resolve_openai_provider_config_reads_selected_model_provider_base_url(self) -> None:
    resolved = resolve_openai_provider_config(
        ProviderCliOptions(),
        codex_home=self.codex_home,
        environ={},
    )
    self.assertEqual(resolved.base_url, "https://provider.test")
```

- [ ] **Step 2: Run the focused test suite and confirm failure**

Run: `python -m unittest tests.test_image_provider_config -v`
Expected: FAIL because `image_provider_config.py` and resolver API do not exist yet.

- [ ] **Step 3: Implement the resolver with explicit precedence**

```python
@dataclass(frozen=True, slots=True)
class ProviderCliOptions:
    api_key: str | None = None
    base_url: str | None = None
    model: str = "gpt-image-1"
```

```python
def resolve_openai_provider_config(
    options: ProviderCliOptions,
    *,
    codex_home: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> ResolvedOpenAIImageConfig:
    resolved_home = codex_home or Path.home() / ".codex"
    return ResolvedOpenAIImageConfig(
        api_key=_resolve_api_key(options, resolved_home, environ or os.environ),
        base_url=_resolve_base_url(options, resolved_home),
        model=options.model,
        size=options.size,
        quality=options.quality,
        background=options.background,
        style=options.style,
    )
```

- [ ] **Step 4: Re-run the resolver tests until green**

Run: `python -m unittest tests.test_image_provider_config -v`
Expected: PASS with precedence, missing-file, and invalid-file coverage.

### Task 2: Wire resolved config into the OpenAI provider layer

**Files:**
- Modify: `temu_y2_women/image_generation_openai.py`
- Modify: `tests/test_image_generation_openai.py`

- [ ] **Step 1: Write the failing provider tests**

```python
def test_build_openai_image_provider_accepts_base_url(self) -> None:
    provider = build_openai_image_provider(
        ResolvedOpenAIImageConfig(api_key="key", base_url="https://example.test", model="gpt-image-2"),
        client_factory=self.capture_client,
    )
    self.assertEqual(self.client_kwargs["base_url"], "https://example.test")
```

- [ ] **Step 2: Run the focused provider tests and confirm failure**

Run: `python -m unittest tests.test_image_generation_openai -v`
Expected: FAIL because the provider builder still expects environment lookup and cannot accept `base_url`.

- [ ] **Step 3: Refactor provider construction to consume resolved config only**

```python
def build_openai_image_provider(
    config: ResolvedOpenAIImageConfig,
    *,
    client_factory: Callable[..., Any] = OpenAI,
) -> OpenAIImageProvider:
    return OpenAIImageProvider(
        OpenAIImageProviderConfig(
            api_key=config.api_key,
            model=config.model,
            size=config.size,
            quality=config.quality,
            background=config.background,
            style=config.style,
            base_url=config.base_url,
        ),
        client_factory=client_factory,
    )
```

- [ ] **Step 4: Re-run provider tests until green**

Run: `python -m unittest tests.test_image_generation_openai -v`
Expected: PASS with `base_url` propagation and fail-closed config validation coverage.

### Task 3: Update both CLIs and render report metadata

**Files:**
- Modify: `temu_y2_women/generate_and_render_cli.py`
- Modify: `temu_y2_women/image_generation_cli.py`
- Modify: `temu_y2_women/image_generation_workflow.py`
- Modify: `tests/test_generate_and_render_cli.py`
- Modify: `tests/test_image_generation_cli.py`

- [ ] **Step 1: Write failing CLI tests for automatic local config resolution and explicit override**

```python
def test_cli_reads_openai_config_from_codex_home(self) -> None:
    exit_code = main([
        "--result", str(self.result_path),
        "--output-dir", str(self.output_dir),
        "--provider", "openai",
    ])
    self.assertEqual(exit_code, 0)
    self.assertEqual(payload["base_url"], "https://example.test")
```

- [ ] **Step 2: Run the focused CLI tests and confirm failure**

Run: `python -m unittest tests.test_generate_and_render_cli tests.test_image_generation_cli -v`
Expected: FAIL because the CLIs do not expose `--base-url` / `--api-key` and cannot read local Codex config.

- [ ] **Step 3: Implement CLI argument additions, shared resolver wiring, and report `base_url` propagation**

```python
parser.add_argument("--base-url", default=None, help="Override the OpenAI-compatible API base URL.")
parser.add_argument("--api-key", default=None, help="Override the OpenAI-compatible API key.")
```

```python
resolved = resolve_openai_provider_config(
    ProviderCliOptions(
        api_key=args.api_key,
        base_url=args.base_url,
        model=args.model,
        size=args.size,
        quality=args.quality,
        background=args.background,
        style=args.style,
    )
)
provider = build_openai_image_provider(resolved)
```

- [ ] **Step 4: Re-run the CLI suites until green**

Run: `python -m unittest tests.test_generate_and_render_cli tests.test_image_generation_cli -v`
Expected: PASS for fake-provider regression, automatic config resolution, explicit override, and structured missing-key failures.

### Task 4: Run regression verification and prepare the branch

**Files:**
- Verify only

- [ ] **Step 1: Run the targeted regression suite**

Run: `python -m unittest tests.test_image_provider_config tests.test_image_generation_openai tests.test_generate_and_render_cli tests.test_image_generation_cli tests.test_image_generation_workflow tests.test_generate_and_render_workflow -v`
Expected: PASS

- [ ] **Step 2: Run syntax validation**

Run: `python -m py_compile temu_y2_women\image_provider_config.py temu_y2_women\image_generation_openai.py temu_y2_women\generate_and_render_cli.py temu_y2_women\image_generation_cli.py temu_y2_women\image_generation_workflow.py`
Expected: PASS with no output

- [ ] **Step 3: Run function-length validation**

Run: `python C:\Users\lxy\.codex\rules\hooks\validate_python_function_length.py .`
Expected: PASS with no violations

- [ ] **Step 4: Review the final diff before commit**

Run: `git diff --stat`
Expected: only the shared config module, provider/CLI/workflow changes, tests, and docs for this change.
