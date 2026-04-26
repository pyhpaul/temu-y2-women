## Why

The `dress` generation chain already runs end-to-end, but the shipped runtime exposed a clear quality gap: `pattern` and `detail` were still chosen greedily, so individually strong elements could combine into style-conflicting results. The implementation for compatibility-aware reranking is already merged, but the OpenSpec change record was never created, so the spec history does not yet explain that shipped behavior.

## What Changes

- Add a file-backed compatibility rule set for curated `pattern/detail` pairs and validate it fail-closed.
- Introduce centralized compatibility evaluation for strong-conflict rejection, weak-conflict penalties, and explainability notes.
- Rerank optional `pattern/detail` combinations with bounded search while keeping the top-level request and result contracts stable.
- Propagate compatibility notes, penalties, and strong-conflict omission effects into composed-concept scoring and constraint handling.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `dress-concept-generation`: Harden optional `pattern/detail` selection with explicit compatibility rules, bounded reranking, and explainable conflict handling.

## Impact

- Adds `data/mvp/dress/compatibility_rules.json` and invalid compatibility-rule fixtures.
- Adds `temu_y2_women/compatibility_evaluator.py` and extends `temu_y2_women/composition_engine.py`.
- Extends regression coverage for compatibility loading, compatibility evaluation, composition reranking, score propagation, and conflict handling.
