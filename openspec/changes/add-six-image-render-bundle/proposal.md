## Why

The project can already generate a stronger `dress` concept result plus one rendered image, but the current render chain still stops at a single hero output. The next review step needs a deterministic six-image asset bundle now: three hero angles plus three close-up detail images.

## What Changes

- Add a deterministic six-job render bundle contract to successful `dress` concept results, covering `hero_front`, `hero_three_quarter`, `hero_back`, `construction_closeup`, `fabric_print_closeup`, and `hem_and_drape_closeup`.
- Extend prompt rendering so downstream image workflows receive stable render-job metadata, group labels, prompts, and output file names without losing compatibility with the existing hero prompt field.
- Extend saved-result rendering and one-shot generate-and-render workflows so they emit a six-image artifact bundle plus a machine-readable bundle report instead of only `rendered_image.png`.
- Preserve fail-closed output behavior and a legacy fallback path for saved concept results that only contain the older single-prompt contract.

## Capabilities

### New Capabilities
- `multi-image-render-bundle`: Covers deterministic six-image render-job generation, stable prompt IDs, group classification, and output naming for hero and detail views.

### Modified Capabilities
- `image-generation-output`: Saved-result rendering and one-shot CLI flows will render a six-image bundle and bundle report when `render_jobs` are present, while preserving a fallback path for legacy single-image results.

## Impact

- Affects `temu_y2_women/prompt_renderer.py`, `temu_y2_women/image_generation_output.py`, `temu_y2_women/image_generation_workflow.py`, `temu_y2_women/generate_and_render_workflow.py`, and `temu_y2_women/generate_and_render_cli.py`.
- Expands render-output contracts, tests, and fixtures for persisted image bundles and machine-readable reporting.
- Increases provider call count per concept run, so latency and cost per real render job will rise from one image request to six.
