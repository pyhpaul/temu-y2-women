## ADDED Requirements

### Requirement: Factory-spec draft includes deterministic sample-review guidance
The system SHALL emit richer deterministic sample-review guidance inside `factory_spec.inferred` for successful `dress` concept generation results.

#### Scenario: Fabric and detail selections expand sample-review watchpoints
- **WHEN** the selected concept includes production-relevant evidence such as fabric, detail, pattern, silhouette, or avoid-tag fit constraints
- **THEN** `factory_spec.inferred` includes deterministic sample-review watchpoints tied to those inputs
- **AND** those watchpoints remain traceable to repository-local evidence instead of external generated metadata

### Requirement: Factory-spec draft includes deterministic QA review notes
The system SHALL emit deterministic QA-oriented review notes without inventing supplier-grade numeric production values.

#### Scenario: Visible construction priorities expand into QA review notes
- **WHEN** the selected concept includes visible construction cues such as smocking, print placement, hem finish, or neckline shape
- **THEN** `factory_spec.inferred` includes QA review notes about consistency, placement, and visible finishing checks
- **AND** the output omits unsupported numeric production tolerances

### Requirement: Factory-spec draft preserves unresolved production gaps explicitly
The system SHALL continue to surface unresolved production metadata even when richer draft guidance is available.

#### Scenario: Richer guidance does not remove missing production fields
- **WHEN** the draft output includes richer deterministic review notes
- **THEN** unsupported fields such as GSM, fiber content, measurements, seam allowance, tolerance, and BOM-grade trim data remain explicitly unresolved
- **AND** the draft does not present those fields as known or inferred numeric values
