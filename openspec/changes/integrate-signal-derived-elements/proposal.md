## Why

The repository already has the first version of signal ingestion and evidence promotion, but the current staged drafts are still too weak to support confident day-to-day element refreshes. Before signal-derived elements can become a practical upstream source for concept generation, the staging and promotion chain needs stronger provenance, coverage reporting, and deterministic merge semantics.

## What Changes

- Enrich staged signal-ingestion outputs with stronger extraction provenance and reviewable coverage reporting for emitted draft elements and strategy hints.
- Strengthen promotion review and apply behavior so signal-derived drafts carry clearer merge rationale and validation through the active-evidence update flow.
- Keep ingestion staging-only and promotion human-reviewed; this phase improves readiness for integration without automatically wiring staged drafts into runtime concept generation.
- Expand deterministic regression coverage for successful and failing signal-derived promotion paths.

## Capabilities

### New Capabilities

### Modified Capabilities
- `signal-ingestion-pipeline`: Staged draft outputs and ingestion reports will expose stronger extraction provenance, coverage, and deterministic merge-readiness metadata.
- `evidence-promotion-workflow`: Review template generation and promotion apply validation will surface clearer merge rationale and preserve deterministic all-or-nothing semantics for signal-derived updates.

## Impact

- Affects `temu_y2_women/signal_ingestion.py`, `temu_y2_women/evidence_promotion.py`, both CLIs, and staged draft fixtures.
- Improves readiness for future evidence refresh workflows without changing the current orchestrator to consume staged drafts directly.
- Keeps all mutations to active evidence gated behind reviewed promotion files.
