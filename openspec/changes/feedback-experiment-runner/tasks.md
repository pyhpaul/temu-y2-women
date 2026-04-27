## 1. Generation override foundation

- [x] 1.1 Add a focused evidence-path configuration object for explicit `elements`, `strategy_templates`, and `taxonomy` paths
- [x] 1.2 Update `generate_dress_concept()` to use explicit evidence paths when provided while preserving the default runtime behavior
- [x] 1.3 Add regression coverage for override-based generation and unchanged default generation behavior

## 2. Experiment prepare workflow

- [x] 2.1 Implement workspace creation plus source-file copying for active evidence, taxonomy, and feedback ledger inputs
- [x] 2.2 Implement baseline generation, feedback review preparation, and deterministic manifest writing inside the workspace
- [x] 2.3 Add workflow tests for prepare outputs, workspace isolation, and manifest contents

## 3. Experiment apply and reporting

- [x] 3.1 Implement manifest-driven workspace feedback apply and rerun generation
- [x] 3.2 Implement deterministic experiment reporting for selected-element changes, retrieval-side changes, and no observable change
- [x] 3.3 Add regression coverage for reject-driven selection drift and keep-driven retrieval-only drift

## 4. CLI and verification

- [x] 4.1 Add a dedicated feedback experiment CLI with `prepare` and `apply` commands
- [x] 4.2 Add CLI regression coverage including module entrypoint execution outside the repo root
- [x] 4.3 Run repository tests, OpenSpec validation, and the function-length guard, then mark the change tasks complete
