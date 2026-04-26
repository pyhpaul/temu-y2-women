## Why

The MVP proved that the `dress` generation chain can run end-to-end, but the current local evidence store is still a thin demo dataset. Before adding ingestion, ranking hardening, or image output, we need a curated offline `dress` evidence store with explicit dictionaries and stronger validation so the existing capability behaves more consistently across a broader request set.

## What Changes

- Expand the local `dress` element evidence store beyond demo-only coverage while keeping the request and result contracts unchanged.
- Add explicit `slot`, `tag`, and `risk` dictionaries plus validation rules that gate element and strategy records before generation uses them.
- Enforce evidence quality checks such as unique active records, canonical slot/value usage, score bounds, and maintainable `evidence_summary` authoring rules.
- Extend regression fixtures and validation scenarios to cover multiple request archetypes plus invalid evidence-store cases.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `dress-concept-generation`: Strengthen the evidence-store requirements behind candidate retrieval and validation without changing the top-level API contract.

## Impact

- Affects `data/mvp/dress/*` evidence files and adds a taxonomy file for supported dictionaries.
- Affects `temu_y2_women/evidence_repository.py` and related tests that load, validate, and retrieve evidence-backed candidates.
- Extends validation fixtures and automated regression coverage for both successful generation flows and invalid evidence-store failures.
