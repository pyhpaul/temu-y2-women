## 1. Promotion fixtures and schema definitions

- [x] 1.1 Add staged-promotion fixtures for valid draft inputs, reviewed decision files, and expected promotion reports
- [x] 1.2 Add expected active-evidence snapshots for successful create and update promotion paths
- [x] 1.3 Define the deterministic review-template shape for draft elements and draft strategy hints

## 2. Review-template generation and decision validation

- [x] 2.1 Implement staged draft loading and validation for promotion inputs
- [x] 2.2 Implement deterministic review-template generation with create-versus-update hints
- [x] 2.3 Implement fail-closed validation for reviewed promotion decisions and curated overrides

## 3. Active evidence merge and reporting

- [ ] 3.1 Implement element promotion with deterministic create/update merge semantics against active evidence
- [ ] 3.2 Implement strategy-template promotion against the post-promotion active evidence snapshot
- [ ] 3.3 Implement promotion reporting and all-or-nothing file replacement behavior

## 4. CLI and regression coverage

- [ ] 4.1 Add a dedicated promotion CLI flow for prepare and apply operations
- [ ] 4.2 Add regression tests for review-template generation, successful promotion, rejected drafts, and fail-before-mutation errors
- [ ] 4.3 Run repository validation for promotion fixtures, targeted tests, and any guardrails needed before merge
