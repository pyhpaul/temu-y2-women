## MODIFIED Requirements

### Requirement: Curated evidence-store validation
The system SHALL validate the local `dress` evidence store, including compatibility rules for curated `pattern/detail` pairs, against explicit dictionaries and quality rules before strategy selection, candidate retrieval, or composition uses it.

#### Scenario: Reject compatibility rules that reference unknown active values
- **WHEN** a compatibility rule points to a `pattern` or `detail` value that does not exist in validated active `dress` evidence
- **THEN** the system returns a structured error with code `INVALID_EVIDENCE_STORE`

#### Scenario: Reject invalid compatibility-rule penalty semantics
- **WHEN** a compatibility rule uses a negative `penalty` or a `strong` rule uses a non-zero `penalty`
- **THEN** the system returns a structured error with code `INVALID_EVIDENCE_STORE`

### Requirement: Structured dress concept composition
The system SHALL compose a structured `dress` concept from retrieved candidates and apply compatibility-aware reranking to the optional `pattern` and `detail` pair.

#### Scenario: Prefer a more compatible detail alternative
- **WHEN** the top-scoring `pattern/detail` pair hits a weak compatibility conflict and an alternative detail yields a better compatibility-adjusted score
- **THEN** the system selects the alternative detail for the final concept

#### Scenario: Omit an incompatible optional detail
- **WHEN** the only available `detail` forms a strong compatibility conflict with the selected `pattern`
- **THEN** the system omits that optional detail instead of returning the incompatible pair

#### Scenario: Reflect compatibility notes and penalties
- **WHEN** compatibility rules influence the selected `pattern/detail` outcome
- **THEN** the system records compatibility notes in `composed_concept.constraint_notes` and incorporates weak-conflict penalties into `concept_score`

#### Scenario: Fail when a removed conflicting element was the only must-have match
- **WHEN** a strong conflict forces removal of the only selected element that satisfies `must_have_tags`
- **THEN** the system returns a structured error with code `CONSTRAINT_CONFLICT`
