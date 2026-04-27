## Why

The current `factory_spec` draft is useful as a first pass, but it is still too thin for sample-review conversations. Reviewers need richer deterministic guidance around sampling priorities, QA watchpoints, and commercial review cues without pretending the system already knows supplier-grade numeric production data.

## What Changes

- Expand the existing `factory_spec` draft with richer deterministic review guidance for sampling, QA, fit, and visible construction checks.
- Preserve the current `known / inferred / unresolved` contract while adding more structured request context and higher-signal review notes.
- Keep unsupported numeric production metadata unresolved instead of fabricating GSM, tolerances, POM measurements, seam allowances, or BOM-ready trim specifications.
- Extend fixtures and regression coverage for the richer draft output so downstream consumers can rely on the enhanced contract.

## Capabilities

### New Capabilities

### Modified Capabilities
- `factory-spec-output`: The draft `factory_spec` contract will expose richer deterministic guidance for sample review and QA while preserving non-fabricated unresolved production fields.

## Impact

- Affects `temu_y2_women/factory_spec_builder.py`, `temu_y2_women/orchestrator.py`, `temu_y2_women/result_packager.py`, and successful result fixtures.
- Expands result-contract tests around `factory_spec` shape and deterministic guidance content.
- Does not introduce new external data sources or supplier-grade numeric production metadata in this phase.
