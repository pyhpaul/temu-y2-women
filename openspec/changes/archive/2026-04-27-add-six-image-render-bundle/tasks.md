## 1. Prompt bundle contract

- [x] 1.1 Add a deterministic six-job render bundle to `prompt_bundle` with fixed hero and detail prompt IDs
- [x] 1.2 Preserve a backward-compatible hero prompt field while making `render_jobs` the canonical downstream contract
- [x] 1.3 Add prompt-renderer regression coverage for job metadata, group labels, and stable output names

## 2. Saved-result rendering bundle

- [x] 2.1 Extend saved-result render input loading so workflows consume `render_jobs` when present and fall back to legacy single-prompt mode otherwise
- [x] 2.2 Extend image-generation workflow output publication so successful bundle renders write six named image artifacts plus one machine-readable report
- [x] 2.3 Add regression coverage for six-image success, legacy single-image fallback, and fail-closed bundle publication

## 3. One-shot workflow and verification

- [x] 3.1 Extend the one-shot generate-and-render workflow and CLI to publish the full six-image bundle
- [x] 3.2 Update fixtures and integration tests for the new output directory layout and bundle report structure
- [x] 3.3 Verify the six-image bundle with focused tests, the full repository test suite, and at least one real-provider smoke run
