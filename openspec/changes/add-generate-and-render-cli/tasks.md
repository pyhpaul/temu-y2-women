## 1. One-shot workflow

- [x] 1.1 Add a dedicated workflow that loads a request JSON, generates a concept result, persists `concept_result.json`, and renders from that persisted result
- [x] 1.2 Add structured invalid-input and concept-result-output failure handling while preserving `concept_result.json` on render-stage failures
- [x] 1.3 Add workflow regression coverage for success, generation error, invalid input, concept-result output failure, and render failure

## 2. One-shot CLI

- [x] 2.1 Add a dedicated CLI that accepts request input, output directory, and provider options
- [x] 2.2 Resolve provider configuration only after `concept_result.json` has been written
- [x] 2.3 Add CLI regression coverage for fake-provider success, OpenAI config failure, and module entrypoint execution outside the repo root

## 3. Verification and completion

- [x] 3.1 Run focused workflow/CLI tests plus the full repository test suite
- [x] 3.2 Run OpenSpec validation and the Python function-length guard
- [x] 3.3 Mark the change tasks complete after all validation passes
