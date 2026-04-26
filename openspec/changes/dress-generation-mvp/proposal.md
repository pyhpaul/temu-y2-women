## Why

The project already has a V2 system design, but it still lacks a narrow, verifiable first change that proves the end-to-end generation chain actually works. We need a minimal `dress`-only MVP now so later work on evidence quality, signal ingestion, image generation, and feedback can attach to a stable contract instead of a moving target.

## What Changes

- Add a `dress`-only MVP generation flow that accepts a normalized request and returns an explainable result package.
- Introduce the minimal request contract, result contract, and structured error contract for concept generation.
- Add a local MVP evidence store format for `dress` elements and strategy templates using structured files.
- Add a minimal composition flow for choosing elements, building a structured concept, and rendering A/B prompt bundles.
- Add fixed validation scenarios that prove success paths and explainable failure paths.

## Capabilities

### New Capabilities
- `dress-concept-generation`: Generate an explainable `dress` concept package from a constrained request using local MVP evidence files, seasonal strategy selection, structured composition, and A/B prompt rendering.

### Modified Capabilities
- None.

## Impact

- Adds a new OpenSpec capability for `dress` concept generation.
- Affects the future generation orchestration entrypoint, local MVP data files, prompt rendering flow, and validation fixtures.
- Establishes the contract that later changes will extend for evidence-store enrichment, signal ingestion, ranking hardening, image output integration, and feedback loops.
