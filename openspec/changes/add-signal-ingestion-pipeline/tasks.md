## 1. Signal input schema and staged data assets

- [x] 1.1 Add `dress` raw-signal fixtures and staged-output expectations for at least one valid bundle and one invalid bundle
- [x] 1.2 Add file-backed `dress` phrase-mapping rules and any supporting staged directory placeholders needed by the ingestion flow
- [x] 1.3 Define the canonical staged artifact shapes for normalized signals, draft elements, draft strategy hints, and the ingestion report

## 2. Ingestion pipeline implementation

- [x] 2.1 Implement raw signal bundle loading and validation with structured `INVALID_SIGNAL_INPUT` failures
- [x] 2.2 Implement deterministic signal normalization that canonicalizes supported fields while preserving source provenance
- [x] 2.3 Implement taxonomy-aware draft element extraction and aggregation by canonical `slot` plus `value`
- [x] 2.4 Implement draft strategy hint extraction, staged artifact writing, and ingestion report generation without mutating active evidence files

## 3. Entry point and regression coverage

- [x] 3.1 Add a dedicated ingestion CLI entrypoint that reads a raw signal bundle and writes staged artifacts to an output directory
- [x] 3.2 Add automated tests for successful ingestion, invalid input failure, deterministic aggregation, and staged-output isolation from active runtime evidence
- [x] 3.3 Run the relevant unit and integration regression suite for both generation and ingestion paths
