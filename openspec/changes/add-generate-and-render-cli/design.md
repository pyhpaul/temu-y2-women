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
