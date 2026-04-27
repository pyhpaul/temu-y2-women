## 1. Prompt bundle contract

- [ ] 1.1 Add a deterministic six-job render bundle to `prompt_bundle` with fixed hero and detail prompt IDs
- [ ] 1.2 Preserve a backward-compatible hero prompt field while making `render_jobs` the canonical downstream contract
- [ ] 1.3 Add prompt-renderer regression coverage for job metadata, group labels, and stable output names

## 2. Saved-result rendering bundle

- [ ] 2.1 Extend saved-result render input loading so workflows consume `render_jobs` when present and fall back to legacy single-prompt mode otherwise
- [ ] 2.2 Extend image-generation workflow output publication so successful bundle renders write six named image artifacts plus one machine-readable report
- [ ] 2.3 Add regression coverage for six-image success, legacy single-image fallback, and fail-closed bundle publication

## 3. One-shot workflow and verification

- [ ] 3.1 Extend the one-shot generate-and-render workflow and CLI to publish the full six-image bundle
- [ ] 3.2 Update fixtures and integration tests for the new output directory layout and bundle report structure
- [ ] 3.3 Verify the six-image bundle with focused tests, the full repository test suite, and at least one real-provider smoke run
