## 1. Compatibility rule data and loader validation

- [x] 1.1 Add `data/mvp/dress/compatibility_rules.json` plus invalid compatibility-rule fixtures
- [x] 1.2 Implement fail-closed compatibility rule loading and validation in `temu_y2_women/compatibility_evaluator.py`
- [x] 1.3 Add loader regression coverage for malformed data, unknown values, severity rules, and penalty semantics

## 2. Centralized compatibility evaluation

- [x] 2.1 Add compatibility rule and evaluation dataclasses plus pair-evaluation helpers
- [x] 2.2 Add regression coverage for weak conflicts, strong conflicts, empty-slot handling, and note formatting

## 3. Compatibility-aware composition reranking

- [x] 3.1 Add bounded reranking for optional `pattern/detail` combinations
- [x] 3.2 Preserve required-slot and standard optional-slot behavior outside the `pattern/detail` pair
- [x] 3.3 Add regression coverage for alternative selection, default rule loading, explicit override behavior, and strong-conflict omission

## 4. Notes, scoring, and final hardening

- [x] 4.1 Propagate compatibility penalties into `concept_score`
- [x] 4.2 Propagate compatibility notes into `constraint_notes`
- [x] 4.3 Preserve `must_have_tags` failure behavior after strong-conflict omission
- [x] 4.4 Tighten final constraint handling for avoided-conflict notes and invalid penalty authoring

## 5. Regression and guardrails

- [x] 5.1 Run focused compatibility and composition suites
- [x] 5.2 Run orchestrator and full-repository regression coverage
- [x] 5.3 Run the Python function-length guardrail
