## 1. Feedback fixtures and artifact definitions

- [ ] 1.1 Add feedback fixtures for successful concept payloads, deterministic review templates, reviewed keep/reject files, expected ledger snapshots, expected reports, and expected post-apply element stores
- [ ] 1.2 Define the deterministic review-template shape, ledger shape, and report shape for concept-level feedback
- [ ] 1.3 Replace the placeholder Purpose text in `openspec/specs/signal-ingestion-pipeline/spec.md`

## 2. Review-template generation and reviewed-feedback validation

- [ ] 2.1 Implement successful concept-result loading and validation for feedback inputs
- [ ] 2.2 Implement deterministic concept-feedback review template generation with locked target fields and reviewer-editable decision/notes fields
- [ ] 2.3 Implement fail-closed validation for reviewed feedback decisions, locked-field tampering, and missing active element targets

## 3. Feedback apply, ledger persistence, and reporting

- [ ] 3.1 Implement bounded `keep` / `reject` score adjustment for selected active elements using taxonomy-aware clamping
- [ ] 3.2 Implement ledger append plus deterministic feedback reporting for successful apply runs
- [ ] 3.3 Implement all-or-nothing file replacement and rollback across active elements, ledger, and report outputs

## 4. CLI and regression coverage

- [ ] 4.1 Add a dedicated feedback-loop CLI flow for prepare and apply operations
- [ ] 4.2 Add regression tests for deterministic review generation, successful keep/reject application, clamping, fail-before-mutation validation, and write-stage rollback
- [ ] 4.3 Run change/spec validation and repository guardrails needed before merge
