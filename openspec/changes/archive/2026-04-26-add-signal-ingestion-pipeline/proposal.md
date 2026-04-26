## Why

The `dress` generation chain now runs on a curated local evidence store, but that store is still updated by hand. Before ranking hardening or image output work, the project needs a repeatable ingestion path that turns raw market signals into reviewable evidence candidates with traceable provenance.

## What Changes

- Add an offline signal-ingestion pipeline for `dress` that accepts structured raw signal records from public or manual sources.
- Normalize and validate signal records into a stable intermediate format before any extraction logic runs.
- Extract draft element candidates and strategy hints from normalized signals into reviewable output files instead of mutating active evidence files directly.
- Generate an ingestion report that records accepted signals, skipped signals, extracted candidates, and validation warnings.
- Add regression fixtures and tests that cover successful ingestion, invalid signal input, and deterministic draft output behavior.

## Capabilities

### New Capabilities
- `signal-ingestion-pipeline`: Ingest structured `dress` market signals into validated, reviewable draft evidence artifacts with provenance and repeatable reporting.

### Modified Capabilities
- None.

## Impact

- Adds a new OpenSpec capability for offline signal ingestion.
- Affects new ingestion-oriented modules, CLI entrypoints, staged data directories, and regression fixtures.
- Keeps the existing `dress-concept-generation` runtime contract unchanged while creating the upstream pipeline that later ranking and evidence changes can build on.
