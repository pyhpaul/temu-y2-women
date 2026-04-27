## Why

The project can now generate stronger production-oriented visual prompts and detail prompts, but it still lacks a structured draft output for factory-facing review. We need a `factory_spec` draft now so concept runs can surface known construction signals, inferred production guidance, and unresolved production fields without pretending to be a full tech pack.

## What Changes

- Add a structured `factory_spec` draft output to successful `dress` concept generation results.
- Classify production-facing information into `known`, `inferred`, and `unresolved` sections so the output remains useful without inventing unsupported manufacturing values.
- Derive draft production guidance only from existing selected elements, strategy context, and deterministic rules already supported by the repository.
- Explicitly record the future expansion path for detailed production metadata such as fiber content, GSM, lining, closure details, measurements, tolerances, and BOM-level data.

## Capabilities

### New Capabilities
- `factory-spec-output`: Covers the draft factory-spec schema, deterministic draft-generation rules, and unresolved-field reporting for production-oriented concept review.

### Modified Capabilities
- `dress-concept-generation`: Successful generation results will include a `factory_spec` draft artifact alongside the existing concept, prompt, and warning outputs.

## Impact

- Affects concept-generation result packaging and any workflow that consumes successful concept results as structured review artifacts.
- Adds deterministic draft-spec generation logic and regression fixtures for successful `dress` generation flows.
- Does not yet introduce full production metadata authoring, supplier-grade measurements, or tech-pack completeness; those remain future roadmap items.
