## Why

`signal-ingestion-pipeline` now produces deterministic staged draft artifacts, but the repository still has no controlled path that turns those drafts into validated active evidence. Without an explicit promotion workflow, every refresh still depends on hand-editing `data/mvp/dress/*.json`, which breaks provenance, review discipline, and repeatability.

## What Changes

- Add a review-gated promotion workflow that converts staged draft elements and draft strategy hints into curated active evidence updates.
- Generate a deterministic review template from staged ingestion artifacts so reviewers can accept, reject, or edit draft records before any active files change.
- Validate reviewed promotion decisions against the existing evidence taxonomy and active-evidence rules before mutating `elements.json` or `strategy_templates.json`.
- Write accepted promotions back into the active `dress` evidence store with deterministic merge semantics and a promotion report.

## Capabilities

### New Capabilities
- `evidence-promotion-workflow`: Prepare reviewable promotion input from staged ingestion artifacts and apply validated, reviewer-approved updates into active `dress` evidence files.

### Modified Capabilities
- None.

## Impact

- Adds promotion-oriented modules and/or CLI entrypoints on top of the existing ingestion pipeline.
- Adds fixtures for staged promotion input, reviewed decision files, expected active-evidence mutations, and promotion reports.
- Mutates `data/mvp/dress/elements.json` and `data/mvp/dress/strategy_templates.json` only through validated, review-gated file writes.
