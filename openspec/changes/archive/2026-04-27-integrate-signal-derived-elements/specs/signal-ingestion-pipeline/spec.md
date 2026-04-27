## ADDED Requirements

### Requirement: Signal-ingestion outputs include deterministic extraction provenance
The system SHALL expose deterministic extraction provenance for each emitted draft element and draft strategy hint.

#### Scenario: Draft elements preserve why they were emitted
- **WHEN** normalized signal content matches supported extraction rules
- **THEN** the staged draft output preserves the source signal IDs and deterministic extraction provenance needed to explain the emitted canonical `slot` and `value`
- **AND** the provenance remains reviewable without mutating active evidence

### Requirement: Ingestion reporting exposes coverage and unmatched paths
The system SHALL report how much of an ingestion run produced supported drafts and which accepted signals remained unmatched.

#### Scenario: Successful ingestion records coverage and unmatched signals
- **WHEN** an ingestion run completes successfully
- **THEN** the ingestion report records emitted draft counts plus explicit coverage or unmatched-signal outcomes
- **AND** unsupported or unmatched extraction paths are surfaced instead of being silently absorbed
