## 1. Generation override foundation

- [ ] 1.1 Add a focused evidence-path configuration object for explicit `elements`, `strategy_templates`, and `taxonomy` paths
- [ ] 1.2 Update `generate_dress_concept()` to use explicit evidence paths when provided while preserving the default runtime behavior
- [ ] 1.3 Add regression coverage for override-based generation and unchanged default generation behavior

## 2. Experiment prepare workflow

- [ ] 2.1 Implement workspace creation plus source-file copying for active evidence, taxonomy, and feedback ledger inputs
- [ ] 2.2 Implement baseline generation, feedback review preparation, and deterministic manifest writing inside the workspace
- [ ] 2.3 Add workflow tests for prepare outputs, workspace isolation, and manifest contents

## 3. Experiment apply and reporting

- [ ] 3.1 Implement manifest-driven workspace feedback apply and rerun generation
- [ ] 3.2 Implement deterministic experiment reporting for selected-element changes, retrieval-side changes, and no observable change
- [ ] 3.3 Add regression coverage for reject-driven selection drift and keep-driven retrieval-only drift

## 4. CLI and verification

- [ ] 4.1 Add a dedicated feedback experiment CLI with `prepare` and `apply` commands
- [ ] 4.2 Add CLI regression coverage including module entrypoint execution outside the repo root
- [ ] 4.3 Run repository tests, OpenSpec validation, and the function-length guard, then mark the change tasks complete
