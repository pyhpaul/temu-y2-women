## MODIFIED Requirements

### Requirement: Explainable result packaging
The system SHALL return an explainable result package for every successful generation flow.

#### Scenario: Return a full result package on success
- **WHEN** generation succeeds
- **THEN** the response includes `request_normalized`, `selected_strategies`, `retrieved_elements`, `composed_concept`, `prompt_bundle`, `factory_spec`, and any warnings

#### Scenario: Return structured errors on failure
- **WHEN** generation fails due to validation, strategy, candidate, or composition issues
- **THEN** the response includes a structured `error` object with a machine-readable error code and human-readable message
