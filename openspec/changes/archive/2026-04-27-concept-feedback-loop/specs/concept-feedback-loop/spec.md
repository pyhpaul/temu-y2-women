## ADDED Requirements

### Requirement: Concept feedback review template generation
The system SHALL generate a deterministic concept-feedback review file from a successful `dress` concept result payload before any active evidence files are mutated.

#### Scenario: Build a review template from a successful concept result
- **WHEN** the workflow receives a successful `dress` concept result payload with selected active elements
- **THEN** it emits a review file that captures the normalized request, selected-element target set, concept score, stable fingerprints, and reviewer-editable decision and notes fields

#### Scenario: Reject unsupported feedback source payloads
- **WHEN** the workflow receives an error payload, a non-`dress` result, or a result with no selected active elements
- **THEN** it returns a structured error and writes no review file

### Requirement: Reviewed concept feedback validation
The system SHALL validate reviewed concept-feedback decisions fail-closed before ledger records or active evidence files are written.

#### Scenario: Reject unresolved or malformed reviewed feedback
- **WHEN** a reviewed feedback file contains a missing decision, an unsupported decision value, or an invalid notes field
- **THEN** the system returns a structured error and does not mutate active evidence or the feedback ledger

#### Scenario: Reject tampered feedback target fields
- **WHEN** a reviewed feedback file changes locked target fields such as the normalized request, selected element IDs, concept score, or stable fingerprints
- **THEN** the system returns a structured error and does not mutate active evidence or the feedback ledger

#### Scenario: Reject feedback that targets missing active elements
- **WHEN** a reviewed feedback file references a selected `element_id` that no longer exists in active `dress` evidence
- **THEN** the system returns a structured error and does not mutate active evidence or the feedback ledger

### Requirement: Bounded feedback application to active evidence
The system SHALL apply reviewed `keep` and `reject` concept feedback to the selected active `dress` elements using deterministic bounded score deltas.

#### Scenario: Apply keep feedback to selected active elements
- **WHEN** a reviewed feedback file is accepted with decision `keep`
- **THEN** the system increases the `base_score` of each selected active element by the configured positive delta and records the apply outcome

#### Scenario: Apply reject feedback to selected active elements
- **WHEN** a reviewed feedback file is accepted with decision `reject`
- **THEN** the system decreases the `base_score` of each selected active element by the configured negative delta and records the apply outcome

#### Scenario: Clamp score updates to taxonomy bounds
- **WHEN** a feedback score adjustment would move an element outside the allowed taxonomy `base_score` range
- **THEN** the system clamps the resulting score to the nearest allowed bound and records that clamp in the apply output

### Requirement: Feedback ledger persistence and atomic reporting
The system SHALL persist successful reviewed feedback into a ledger and write a deterministic report without partial mutation.

#### Scenario: Write ledger and report for a successful apply run
- **WHEN** a feedback apply run succeeds
- **THEN** the system appends a ledger record with decision, target element IDs, score delta, fingerprints, notes, and recorded timestamp and writes a report summarizing affected elements and score changes

#### Scenario: Preserve all-or-nothing behavior on validation or write failure
- **WHEN** validation fails or any output write fails during feedback apply
- **THEN** the system leaves the active element store and feedback ledger unchanged and writes no partial report output
