## Why

The repository can already generate `dress` concepts and apply review-gated concept feedback, but it still lacks a safe, repeatable way to prove whether one feedback decision actually changes the next run. Running that experiment against the default active evidence files is risky and hard to replay, so the next slice should make the feedback effect observable inside an isolated workspace.

## What Changes

- Add an isolated feedback experiment workflow that creates a workspace copy of active evidence, taxonomy, and feedback ledger files before any feedback apply step runs.
- Add a baseline `dress` generation step plus deterministic feedback-review preparation inside that workspace.
- Add an apply step that reuses the existing concept feedback flow against workspace copies only, reruns the same request, and writes a deterministic experiment report.
- Add a small evidence-path override capability so generation can read a workspace evidence snapshot without changing the default runtime contract.
- Add a dedicated CLI for experiment prepare/apply flows and regression coverage for workspace isolation, rerun behavior, and before/after reporting.

## Capabilities

### New Capabilities
- `feedback-experiment-runner`: Prepare and apply isolated `dress` feedback experiments that compare baseline and rerun outputs without mutating the repository’s default active evidence files.

### Modified Capabilities
- None.

## Impact

- Adds an experiment orchestration module and CLI on top of the existing generation and feedback workflows.
- Touches the generation entrypoint so it can optionally read explicit evidence paths while keeping default behavior unchanged.
- Adds workflow tests for workspace copying, manifest/report writing, isolated feedback apply, and rerun diffing.
- Enables reproducible offline feedback experiments without introducing new runtime dependencies or changing the default active evidence paths.
