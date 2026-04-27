## Why

The repository can already ingest signals, promote reviewed evidence, and generate `dress` concepts, but reviewer judgments on generated concepts still disappear after each run. Without a review-gated feedback workflow, `keep` and `reject` decisions never flow back into curated active evidence, so repeated experiments cannot improve element scoring or demonstrate a true closed loop.

## What Changes

- Add a file-backed feedback workflow that prepares a deterministic review template from a successful `dress` concept result payload.
- Validate reviewed concept feedback fail-closed before any active evidence files change.
- Append accepted feedback decisions to a persistent feedback ledger and apply bounded score deltas to the selected active `dress` elements.
- Write a deterministic feedback report and preserve all-or-nothing file replacement behavior across active evidence, ledger, and report outputs.
- Replace the remaining placeholder Purpose text in `openspec/specs/signal-ingestion-pipeline/spec.md`.

## Capabilities

### New Capabilities
- `concept-feedback-loop`: Prepare reviewable concept-feedback input from successful `dress` generation outputs and apply reviewer-approved keep/reject decisions back into active `dress` evidence.

### Modified Capabilities
- None.

## Impact

- Adds feedback-oriented modules and a dedicated CLI path on top of the existing `dress` generation runtime.
- Adds fixtures for successful result payloads, review templates, reviewed decisions, expected ledger snapshots, expected active-evidence mutations, and feedback reports.
- Introduces a persistent feedback ledger under `data/feedback/dress/`.
- Mutates `data/mvp/dress/elements.json` only through validated, review-gated feedback apply writes.
