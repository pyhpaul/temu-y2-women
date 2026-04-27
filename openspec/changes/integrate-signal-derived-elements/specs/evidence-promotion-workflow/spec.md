## ADDED Requirements

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
