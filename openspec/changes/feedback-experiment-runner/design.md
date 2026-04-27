## Context

The repository already has four important building blocks:

- deterministic `dress` generation from active evidence
- file-backed active evidence and taxonomy
- review-gated evidence promotion
- review-gated concept feedback that can mutate active element scores

What is still missing is the experiment harness that proves the feedback loop is doing useful work. Right now a reviewer can apply `keep` or `reject`, but there is no repository-managed path that safely snapshots inputs, reruns the same request, and records whether retrieval, selection, or concept scoring actually changed. That leaves the feedback loop operationally incomplete for experimentation.

## Goals / Non-Goals

**Goals:**
- create an isolated workspace for each feedback experiment
- copy active evidence, taxonomy, and feedback ledger inputs into that workspace before the experiment begins
- run baseline generation plus feedback-review preparation inside the workspace
- apply reviewed feedback only against workspace copies, rerun the same request, and write a deterministic experiment report
- keep the default generation contract and default active evidence paths unchanged unless explicit overrides are provided

**Non-Goals:**
- new feedback decision types beyond `keep` and `reject`
- strategy feedback or image-level satisfaction feedback
- idempotency or deduplication rules for repeated concept feedback
- batch experiment scheduling
- a browser UI or visualization layer

## Decisions

### 1. Use workspace copies instead of touching the default active evidence files

Each experiment should begin by copying the current active evidence snapshot into a dedicated workspace directory. The apply phase then mutates only those workspace copies.

Rationale:
- protects the repository’s default runtime evidence from accidental experiment writes
- makes each experiment self-contained and replayable
- keeps input, output, and intermediate artifacts together for review

Alternatives considered:
- **Run directly on the default active evidence files**: rejected because it is unsafe and makes experiment replay harder
- **Write only reports and never mutate any evidence snapshot**: rejected because rerun generation would not reflect the feedback effect

### 2. Introduce a small explicit evidence-path configuration object for generation

The generation entrypoint should accept an optional path object containing `elements`, `strategy_templates`, and `taxonomy` paths. The default path set should remain the same when no override is supplied.

Rationale:
- isolates path-injection concerns at the orchestration boundary
- avoids scattering raw file-path parameters through lower-level generation helpers
- lets the experiment runner reuse the normal generation code instead of duplicating it

Alternatives considered:
- **Patch module-level constants during experiments**: rejected because it is brittle and hard to reason about
- **Thread independent file paths through every helper signature**: rejected because it creates unnecessary churn across the generation stack

### 3. Make the manifest the single source of truth for experiment replay

The prepare step should write a manifest that records the workspace root, request path, baseline result path, feedback review path, and workspace copy paths. The apply step should load that manifest and refuse to infer those paths from other inputs.

Rationale:
- keeps apply deterministic and resistant to path drift
- reduces operator error during manual review/apply cycles
- makes each experiment re-runnable from one stable file

Alternatives considered:
- **Reconstruct paths from conventions during apply**: rejected because it is more fragile and harder to validate

### 4. Report observable change at the experiment layer, not inside the generation result schema

The rerun experiment report should summarize baseline vs rerun concept score, selected-element changes, retrieval-side score/rank deltas, and feedback apply score deltas. The generation result schema itself should remain unchanged.

Rationale:
- keeps experiment-specific concerns downstream of the stable generation contract
- makes the experiment output easier to interpret without complicating the generation payload
- supports “selection changed” and “retrieval changed only” outcomes without redefining generation success

Alternatives considered:
- **Add experiment metadata directly into generation results**: rejected because it pollutes the stable runtime contract
- **Store only raw baseline/rerun JSON files and require manual diffing**: rejected because the main value of this change is direct observability

## Risks / Trade-offs

- **[Risk] A feedback apply can change scores without changing final selected elements** → Mitigation: classify that case explicitly in the experiment report instead of treating it as failure
- **[Risk] Generation path overrides touch a core entrypoint** → Mitigation: keep the override surface small and preserve the current default behavior when no override is provided
- **[Risk] Workspace copying duplicates small evidence files for each run** → Mitigation: accept the storage cost for now because isolation and replayability matter more in this slice

## Migration Plan

1. Add the explicit evidence-path configuration object and update generation to use it optionally.
2. Implement the experiment prepare workflow that copies source files, runs baseline generation, and writes feedback review plus manifest artifacts.
3. Implement the apply workflow that reuses existing concept feedback apply logic against workspace copies, reruns the request, and writes the experiment report.
4. Add the dedicated CLI and regression tests.
5. Validate the change with targeted workflow tests, full repository tests, OpenSpec validation, and the function-length guard.

Rollback is straightforward because the default active evidence files are not the experiment runner’s write target. Reverting the implementation removes the experiment workflow without requiring repository data migration.

## Open Questions

- No blocking open questions remain for this slice.
- A future change may add batch experiment orchestration or richer visualization, but this change should stay file-backed and CLI-first.
