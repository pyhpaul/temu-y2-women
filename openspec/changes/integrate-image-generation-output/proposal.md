## Why

The `dress` generation chain now stops at `prompt_bundle`, so the repository still cannot produce the visible image output that the V2 flow was designed to reach. We need a repo-managed image rendering step now so operators can turn a successful concept result into reviewable image artifacts without mixing network-dependent behavior into the deterministic generation core.

## What Changes

- Add a dedicated image-generation workflow that accepts a successful `dress` concept result JSON and renders image artifacts from its `prompt_bundle`.
- Add a provider boundary plus the first real image provider integration so tests can stay offline while production runs can generate actual images.
- Add deterministic output artifacts and reporting for rendered images, including provider metadata and source-result provenance.
- Add a dedicated CLI for rendering images from saved concept results and surfacing structured errors for invalid inputs, provider failures, and output write failures.

## Capabilities

### New Capabilities
- `image-generation-output`: Render reviewable image artifacts from successful `dress` concept results using the saved prompt bundle and a configured image provider.

### Modified Capabilities
- None.

## Impact

- Adds new workflow and CLI modules for image rendering.
- Introduces an external image provider dependency behind a local adapter boundary.
- Adds file-backed output artifacts and regression fixtures for rendered-image reports and failure handling.
