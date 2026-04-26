# dress-concept-generation Specification

## Purpose
Define the stable contract for explainable `dress` concept generation, including request normalization, strategy selection, evidence-backed retrieval, structured composition, prompt rendering, and repeatable validation.
## Requirements
### Requirement: Dress generation request normalization
The system SHALL accept a concept-generation request for the `dress` category and normalize it into a validated internal request object before any strategy or evidence lookup occurs.

#### Scenario: Accept a valid dress request
- **WHEN** a request includes `category=dress`, a valid `target_launch_date`, and `mode` set to `A` or `B`
- **THEN** the system returns a normalized request object that preserves supported optional filters such as `price_band`, `occasion_tags`, `must_have_tags`, and `avoid_tags`

#### Scenario: Reject an unsupported category
- **WHEN** a request uses a category other than `dress`
- **THEN** the system returns a structured error with code `UNSUPPORTED_CATEGORY`

#### Scenario: Reject an invalid launch date
- **WHEN** a request includes an invalid `target_launch_date`
- **THEN** the system returns a structured error with code `INVALID_DATE`

### Requirement: Seasonal strategy selection
The system SHALL select one or two active strategy templates for a normalized request using the target market, launch window, and optional occasion tags.

#### Scenario: Select a matching seasonal strategy
- **WHEN** the launch date and request context match an active strategy template
- **THEN** the system includes that strategy in `selected_strategies` with an explanation of why it matched

#### Scenario: Prefer an occasion-aligned strategy
- **WHEN** multiple active strategies match the launch window and one of them also matches the request's `occasion_tags`
- **THEN** the system prioritizes the occasion-aligned strategy for selection

#### Scenario: Fall back to a baseline strategy
- **WHEN** no specific seasonal or occasion strategy matches the request
- **THEN** the system uses a baseline active strategy and records a warning that fallback strategy selection was applied

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

### Requirement: Structured dress concept composition
The system SHALL compose a structured `dress` concept from retrieved candidates instead of generating prompts directly from the raw candidate pool.

#### Scenario: Build a minimum valid concept
- **WHEN** eligible candidates exist for required slots
- **THEN** the system selects at least one `silhouette` and one `fabric` element and returns them in `composed_concept.selected_elements`

#### Scenario: Enforce must-have tags
- **WHEN** the request includes `must_have_tags`
- **THEN** the final composed concept MUST satisfy at least one matching selected element or the system returns a structured error with code `CONSTRAINT_CONFLICT`

#### Scenario: Fail on incomplete concept
- **WHEN** the system cannot produce all required slots after applying filters and constraints
- **THEN** the system returns a structured error with code `INCOMPLETE_CONCEPT`

### Requirement: Mode-specific prompt rendering
The system SHALL render a prompt bundle from the structured concept and selected strategies for either mode `A` or mode `B`.

#### Scenario: Render mode A for concept imagery
- **WHEN** the normalized request uses mode `A`
- **THEN** the prompt bundle emphasizes product appeal, seasonal mood, and ecommerce-friendly presentation

#### Scenario: Render mode B for design clarity
- **WHEN** the normalized request uses mode `B`
- **THEN** the prompt bundle emphasizes garment structure, silhouette, neckline, sleeve, fabric, and relevant development notes

### Requirement: Explainable result packaging
The system SHALL return an explainable result package for every successful generation flow.

#### Scenario: Return a full result package on success
- **WHEN** generation succeeds
- **THEN** the response includes `request_normalized`, `selected_strategies`, `retrieved_elements`, `composed_concept`, `prompt_bundle`, and any warnings

#### Scenario: Return structured errors on failure
- **WHEN** generation fails due to validation, strategy, candidate, or composition issues
- **THEN** the response includes a structured `error` object with a machine-readable error code and human-readable message

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

