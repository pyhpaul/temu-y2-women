# evidence-promotion-workflow Specification

## Purpose
Define the stable contract for promoting reviewed staged `dress` evidence drafts into the active evidence store with deterministic validation, merge semantics, reporting, and all-or-nothing writes.
## Requirements
### Requirement: Promotion review template generation
The system SHALL generate a deterministic promotion review file from staged `dress` ingestion artifacts before any active evidence files are mutated.

#### Scenario: Build a review template from staged drafts
- **WHEN** the workflow receives valid staged `draft_elements.json` and `draft_strategy_hints.json` artifacts
- **THEN** it emits a review file that includes one decision record per draft artifact with source IDs, provenance context, and reviewer-editable curated fields

#### Scenario: Surface create-versus-update intent in the review template
- **WHEN** a staged draft matches an existing active element or strategy template identity
- **THEN** the generated review file marks that draft as an update candidate instead of a new create candidate

### Requirement: Promotion decision validation
The system SHALL validate reviewed promotion decisions fail-closed before writing active evidence files.

#### Scenario: Reject unresolved or malformed promotion decisions
- **WHEN** a reviewed promotion file contains missing decisions, unsupported decision values, or incomplete curated records for accepted drafts
- **THEN** the system returns a structured error and does not mutate active evidence files

#### Scenario: Reject reviewed records that violate active evidence rules
- **WHEN** an accepted reviewed element or strategy template violates taxonomy membership, uniqueness rules, score bounds, or strategy-reference validation
- **THEN** the system returns a structured error and does not mutate active evidence files

### Requirement: Deterministic active evidence promotion
The system SHALL apply accepted reviewed drafts into the active `dress` evidence store with deterministic merge semantics.

#### Scenario: Create a new active element from an accepted draft
- **WHEN** an accepted reviewed element represents a canonical `slot + value` that does not exist in active evidence
- **THEN** the system appends a new active element record to `data/mvp/dress/elements.json`

#### Scenario: Update an existing active element from an accepted draft
- **WHEN** an accepted reviewed element targets a canonical `slot + value` that already exists in active evidence
- **THEN** the system updates the existing active record in place using the reviewed curated fields

#### Scenario: Reject drafts without mutating active evidence
- **WHEN** a reviewer marks a staged draft as `reject`
- **THEN** the system excludes that draft from active evidence writes and records the rejection in the promotion report

### Requirement: Strategy promotion after element-aware validation
The system SHALL validate and apply reviewed draft strategy hints only against the post-promotion active evidence snapshot.

#### Scenario: Promote a reviewed strategy template
- **WHEN** an accepted reviewed strategy template references only slot values that will exist after accepted element promotions are applied
- **THEN** the system creates or updates the active strategy template in `data/mvp/dress/strategy_templates.json`

#### Scenario: Reject a strategy template with unresolved slot preferences
- **WHEN** an accepted reviewed strategy template points to a slot value that is absent from the post-promotion active evidence set
- **THEN** the system returns a structured error and does not mutate active strategy templates

### Requirement: Promotion reporting
The system SHALL write a deterministic promotion report for every successful apply run.

#### Scenario: Report promotion outcomes
- **WHEN** a promotion apply run succeeds
- **THEN** the system writes a report that records accepted, rejected, created, and updated counts plus the affected draft IDs, strategy hint IDs, and source signal IDs

#### Scenario: Preserve all-or-nothing behavior on failed apply
- **WHEN** validation fails during promotion apply
- **THEN** the system writes no partial active evidence updates and returns the failure before any output files are replaced

### Requirement: Promotion review exposes deterministic merge rationale
The system SHALL generate review templates that preserve deterministic merge rationale for signal-derived create-versus-update decisions.

#### Scenario: Review template surfaces canonical merge identity
- **WHEN** staged drafts are converted into a promotion review template
- **THEN** each review record preserves the canonical identity and deterministic merge rationale used to classify it as `create` or `update`
- **AND** reviewers can see that rationale before any active evidence write occurs

### Requirement: Promotion apply validates reviewed records against staged merge intent
The system SHALL validate reviewed promotion records against the same deterministic merge semantics used during review-template generation.

#### Scenario: Apply rejects reviewed records that break staged merge semantics
- **WHEN** a reviewed promotion record no longer matches the canonical merge identity or deterministic update target established by the staged draft
- **THEN** the apply workflow returns a structured error
- **AND** it leaves active evidence files unchanged

