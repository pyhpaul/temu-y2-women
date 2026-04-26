## ADDED Requirements

### Requirement: Curated evidence-store validation
The system SHALL validate the local `dress` evidence store against explicit dictionaries and quality rules before any strategy selection or candidate retrieval uses it.

#### Scenario: Reject unsupported dictionary values
- **WHEN** an active element or strategy record contains a `slot`, tag, season tag, occasion tag, suppress/boost tag, or `risk_flags` value outside the supported dictionaries
- **THEN** the system returns a structured error with code `INVALID_EVIDENCE_STORE` and identifies the offending field and record

#### Scenario: Reject duplicate or conflicting active element records
- **WHEN** two active `dress` element records reuse the same `element_id` or the same canonical `slot` plus `value`
- **THEN** the system returns a structured error with code `INVALID_EVIDENCE_STORE` before generation proceeds

#### Scenario: Reject invalid score or summary authoring
- **WHEN** an active element record uses a `base_score` outside the supported range or an `evidence_summary` that violates the configured authoring rules
- **THEN** the system returns a structured error with code `INVALID_EVIDENCE_STORE`

#### Scenario: Reject strategy references to unknown slot values
- **WHEN** an active strategy template points a slot preference at a value that does not exist in the validated active evidence for that slot
- **THEN** the system returns a structured error with code `INVALID_EVIDENCE_STORE`

## MODIFIED Requirements

### Requirement: Evidence-backed candidate retrieval
The system SHALL retrieve `dress` candidates from validated local evidence-store files and apply supported filters before composition.

#### Scenario: Retrieve eligible candidates from validated local evidence
- **WHEN** the normalized request is valid and active evidence records pass schema, dictionary, and quality validation
- **THEN** the system returns candidate elements grouped by slot and scored with the active strategy effects included

#### Scenario: Exclude avoided candidates
- **WHEN** the request includes `avoid_tags`
- **THEN** the system excludes candidates that match those tags before composition and records that filtering in the result warnings or notes

#### Scenario: Fail when no candidates remain
- **WHEN** candidate filtering leaves no eligible elements for the request
- **THEN** the system returns a structured error with code `NO_CANDIDATES`

### Requirement: Repeatable MVP validation scenarios
The system SHALL provide fixed validation scenarios that exercise successful, failing, and invalid-evidence paths for the curated `dress` evidence store.

#### Scenario: Validate multiple successful request archetypes
- **WHEN** the validation suite runs against predefined `dress` requests for at least a seasonal request and a baseline request
- **THEN** it verifies that each flow produces a normalized request, selected strategy set, composed concept, and prompt bundle without error

#### Scenario: Validate a constrained failure path
- **WHEN** the validation suite runs against a predefined request whose constraints eliminate all valid outcomes
- **THEN** it verifies that the system returns the expected structured failure instead of a partial or silent success

#### Scenario: Validate an invalid evidence-store fixture
- **WHEN** the validation suite runs against a predefined evidence fixture that violates the supported dictionaries or quality rules
- **THEN** it verifies that the system returns the expected `INVALID_EVIDENCE_STORE` failure before generation continues
