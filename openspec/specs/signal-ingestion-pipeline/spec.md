# signal-ingestion-pipeline Specification

## Purpose
Define the stable contract for ingesting file-backed `dress` market signals into deterministic staged draft evidence artifacts without mutating active runtime evidence.
## Requirements
### Requirement: Structured dress signal bundle validation
The system SHALL accept a file-backed `dress` signal bundle and validate its top-level structure plus each raw signal record before normalization begins.

#### Scenario: Accept a valid dress signal bundle
- **WHEN** an ingestion run receives a bundle whose root object and `signals` array match the supported schema for `dress`
- **THEN** the system proceeds to normalization and records the accepted signal count in the ingestion report

#### Scenario: Reject an invalid signal bundle
- **WHEN** the bundle root is malformed, a required field is missing, or a signal record uses an unsupported `category` or `target_market`
- **THEN** the system returns a structured error with code `INVALID_SIGNAL_INPUT` and identifies the offending file, field, and record

### Requirement: Deterministic signal normalization
The system SHALL normalize accepted raw signal records into a canonical intermediate form before any extraction or aggregation logic runs.

#### Scenario: Canonicalize supported signal fields
- **WHEN** a valid signal record contains mixed-case text, repeated tags, or padded string values
- **THEN** the normalized signal output trims, canonicalizes, and deduplicates supported fields while preserving the original `signal_id` and source metadata

#### Scenario: Preserve provenance through normalization
- **WHEN** a signal record is accepted for normalization
- **THEN** the normalized output retains the source metadata needed to trace later draft artifacts back to the originating signal record

### Requirement: Draft element candidate extraction
The system SHALL extract reviewable draft `dress` element candidates from normalized signals using supported phrase rules and the existing evidence taxonomy.

#### Scenario: Extract canonical draft elements from supported phrases
- **WHEN** normalized signal content or manual tags match supported `dress` extraction rules
- **THEN** the system emits draft element candidates with canonical `slot`, `value`, proposed evidence fields, and `status` set to `draft`

#### Scenario: Aggregate repeated element evidence
- **WHEN** multiple normalized signals map to the same canonical `slot` plus `value`
- **THEN** the system merges them into a single draft element candidate that includes the combined source signal IDs and aggregated context fields

### Requirement: Draft strategy hint extraction
The system SHALL derive coarse draft strategy hints from normalized signals without mutating active strategy templates.

#### Scenario: Build draft strategy hints from recurring context
- **WHEN** normalized signals consistently indicate shared market, season, occasion, or slot-preference patterns
- **THEN** the system emits draft strategy hints with provenance, aggregated context, and `status` set to `draft`

#### Scenario: Keep strategy hints isolated from active runtime templates
- **WHEN** an ingestion run completes successfully
- **THEN** the system writes draft strategy hints only to staged output artifacts and does not change `data/mvp/dress/strategy_templates.json`

### Requirement: Staged artifact writing and ingestion reporting
The system SHALL write deterministic staged artifacts and a reviewable ingestion report for every successful run.

#### Scenario: Write reviewable staged artifacts
- **WHEN** an ingestion run succeeds
- **THEN** the system writes normalized signals, draft elements, draft strategy hints, and an ingestion report to the configured staging output directory

#### Scenario: Report skipped or unsupported extraction paths
- **WHEN** a valid signal record yields no supported draft candidates or triggers non-fatal warnings
- **THEN** the ingestion report records that outcome without silently mutating active evidence files

### Requirement: Repeatable ingestion regression coverage
The system SHALL provide deterministic fixtures and automated validation for the signal-ingestion pipeline.

#### Scenario: Validate a successful ingestion fixture
- **WHEN** the regression suite runs against a predefined valid `dress` signal bundle
- **THEN** it verifies that the staged draft outputs and ingestion report match the expected canonical structure

#### Scenario: Validate an invalid ingestion fixture
- **WHEN** the regression suite runs against a predefined invalid signal bundle
- **THEN** it verifies that the system returns the expected `INVALID_SIGNAL_INPUT` failure before staged artifacts are produced

