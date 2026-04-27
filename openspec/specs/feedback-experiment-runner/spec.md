# feedback-experiment-runner Specification

## Purpose
Define the stable contract for preparing, applying, and reporting isolated `dress` feedback experiments against workspace-scoped evidence snapshots without mutating the default runtime evidence.
## Requirements
### Requirement: Isolated experiment workspace preparation
The system SHALL prepare each `dress` feedback experiment inside a dedicated workspace that contains copied active evidence, taxonomy, and feedback ledger inputs before any reviewed feedback is applied.

#### Scenario: Prepare a baseline experiment workspace
- **WHEN** the workflow receives a valid `dress` request JSON and an experiment root directory
- **THEN** it creates a workspace, copies the active `elements.json`, `strategy_templates.json`, `evidence_taxonomy.json`, and `feedback_ledger.json` into that workspace, runs baseline generation against the copied evidence, and writes a deterministic feedback review file plus manifest

#### Scenario: Keep default active evidence unchanged during prepare
- **WHEN** the workflow prepares an experiment workspace
- **THEN** it writes no mutations to the repository’s default active evidence or ledger files

### Requirement: Explicit evidence snapshot generation
The system SHALL allow `dress` generation to run against an explicit evidence snapshot without changing its default behavior when no explicit paths are provided.

#### Scenario: Generate from workspace evidence overrides
- **WHEN** generation is invoked with explicit workspace evidence and taxonomy paths
- **THEN** it loads elements, strategy templates, and taxonomy from those provided paths instead of the default active evidence paths

#### Scenario: Preserve default generation behavior
- **WHEN** generation is invoked without explicit evidence overrides
- **THEN** it reads the same default active evidence files and returns the same contract as before this change

### Requirement: Isolated feedback apply and rerun
The system SHALL apply reviewed concept feedback only against the workspace evidence snapshot recorded in the experiment manifest, then rerun the same request against that updated workspace snapshot.

#### Scenario: Apply reviewed feedback inside the workspace
- **WHEN** the workflow receives a reviewed feedback file and a valid experiment manifest
- **THEN** it applies the feedback only to the workspace `elements.json` and `feedback_ledger.json` referenced by that manifest and writes the feedback report inside the same workspace

#### Scenario: Rerun the same request against updated workspace evidence
- **WHEN** workspace feedback apply succeeds
- **THEN** the workflow reruns generation using the request recorded in the manifest and the updated workspace evidence paths and writes a post-apply generation result in that workspace

### Requirement: Deterministic experiment reporting
The system SHALL write a deterministic experiment report that summarizes the observable difference between baseline and rerun outputs.

#### Scenario: Report selected-element changes
- **WHEN** rerun generation selects a different element in one or more slots than the baseline result
- **THEN** the experiment report records those slot-level before/after selections and classifies the outcome as a selection change

#### Scenario: Report retrieval-side changes without selection drift
- **WHEN** rerun generation keeps the same selected elements but workspace feedback changes relevant retrieved-element scores or ranks
- **THEN** the experiment report records those retrieval deltas and classifies the outcome as retrieval changed only

#### Scenario: Report no observable drift
- **WHEN** rerun generation shows no selected-element or relevant retrieval-side differences after feedback apply
- **THEN** the experiment report classifies the outcome as no observable change while still preserving baseline and rerun summaries
