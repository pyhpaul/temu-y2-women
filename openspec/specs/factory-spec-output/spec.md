# factory-spec-output Specification

## Purpose
Define the stable contract for deterministic `factory_spec` draft output attached to successful `dress` concept generation results.
## Requirements
### Requirement: Deterministic factory-spec draft output
The system SHALL generate a structured `factory_spec` draft artifact for every successful `dress` concept generation result.

#### Scenario: Successful generation includes a factory-spec draft
- **WHEN** a `dress` concept generation flow succeeds
- **THEN** the result includes a `factory_spec` object
- **AND** the object records a schema version plus deterministic production-review content for the generated concept

### Requirement: Factory-spec draft classifies certainty levels
The system SHALL classify production-facing output into explicit `known`, `inferred`, and `unresolved` sections.

#### Scenario: Selected concept facts are preserved as known fields
- **WHEN** the final concept selects concrete elements such as `fabric`, `neckline`, `sleeve`, or `detail`
- **THEN** the `factory_spec.known` section preserves those selected facts without rewriting them as guessed production metadata

#### Scenario: Rule-derived review guidance is emitted as inferred fields
- **WHEN** the system has deterministic production-review guidance that can be derived from the selected concept and request context
- **THEN** it records that guidance under `factory_spec.inferred`
- **AND** it does not mix those rule-derived statements into `known`

#### Scenario: Unsupported production data is listed as unresolved
- **WHEN** the repository does not model required production metadata such as fiber content, GSM, lining, closure details, measurements, tolerances, or BOM-grade trim data
- **THEN** the `factory_spec.unresolved` section lists those fields explicitly instead of inventing values

### Requirement: Factory-spec draft must stay non-fabricated
The system SHALL avoid generating unsupported numeric or supplier-ready production values in the draft factory spec.

#### Scenario: Missing numeric production values remain unresolved
- **WHEN** the active evidence store does not contain numeric production data for the selected concept
- **THEN** the draft output omits fabricated numeric values
- **AND** it records the missing production fields as unresolved

### Requirement: Deterministic production-review guidance from existing evidence
The system SHALL derive draft production guidance only from repository-local evidence, selected elements, and deterministic rules.

#### Scenario: Fabric and detail selections influence inferred review guidance
- **WHEN** the selected concept includes production-relevant selections such as `cotton poplin` fabric or `smocked bodice` detail
- **THEN** the `factory_spec.inferred` section includes deterministic review guidance about visible texture, drape, construction focus, or other supported review priorities
- **AND** that guidance remains traceable to the selected concept rather than external generated metadata

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

