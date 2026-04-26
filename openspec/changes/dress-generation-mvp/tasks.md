## 1. Contracts and project skeleton

- [ ] 1.1 Create the MVP module structure for request normalization, strategy selection, evidence loading, composition, prompt rendering, result packaging, and orchestration
- [ ] 1.2 Define the request, result, and structured error shapes for `dress` concept generation
- [ ] 1.3 Add the CLI entrypoint for running the MVP flow from a request file

## 2. Local MVP evidence store

- [ ] 2.1 Add `data/mvp/dress/elements.json` with a minimal but valid set of active `dress` elements across required and optional slots
- [ ] 2.2 Add `data/mvp/dress/strategy_templates.json` with baseline and seasonal strategy templates for the US `dress` MVP
- [ ] 2.3 Implement evidence loading and validation for the local MVP files

## 3. Core generation flow

- [ ] 3.1 Implement request normalization and validation for supported `dress` requests
- [ ] 3.2 Implement strategy selection with launch-window matching, occasion preference, and baseline fallback
- [ ] 3.3 Implement candidate retrieval, scoring, and `avoid_tags` filtering from the local evidence store
- [ ] 3.4 Implement structured concept composition with required-slot enforcement and `must_have_tags` checks

## 4. Prompt rendering and result packaging

- [ ] 4.1 Implement mode `A` prompt rendering for concept imagery output
- [ ] 4.2 Implement mode `B` prompt rendering for design-clarity output
- [ ] 4.3 Implement explainable result packaging for success responses and structured error packaging for failure responses

## 5. Validation and regression coverage

- [ ] 5.1 Add fixed sample requests for successful A-mode and B-mode generation flows
- [ ] 5.2 Add fixed failure samples for no-candidate and constraint-conflict paths
- [ ] 5.3 Add automated validation that checks normalized requests, selected strategies, composed concepts, prompt bundles, and expected structured errors
