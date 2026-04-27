## 1. Signal-ingestion staging improvements

- [ ] 1.1 Extend staged draft outputs with deterministic extraction provenance that explains why each draft element or strategy hint was emitted
- [ ] 1.2 Expand ingestion reporting so successful runs surface coverage, unmatched signals, and reviewable extraction outcomes
- [ ] 1.3 Add focused ingestion regression fixtures for richer staged outputs and reporting

## 2. Promotion review and apply hardening

- [ ] 2.1 Extend promotion review template generation with deterministic merge rationale and canonical identity visibility
- [ ] 2.2 Validate reviewed promotion records against the same staged merge semantics during apply
- [ ] 2.3 Add end-to-end regression coverage for successful and failing signal-derived promotion flows

## 3. Verification

- [ ] 3.1 Run focused signal-ingestion and promotion tests plus the full repository suite
- [ ] 3.2 Run the Python function-length guard and confirm staged-to-active behavior remains deterministic
