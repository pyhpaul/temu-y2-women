## Context

The repository already has:

- a deterministic `dress-concept-generation` flow that returns a structured success payload
- file-backed active evidence under `data/mvp/dress/`
- review-gated ingestion and evidence promotion workflows that safely curate new active records

What is still missing is the last operational loop: when a reviewer likes or rejects a generated concept, there is no repository-managed path that captures that decision, preserves it as an audit trail, and turns it into a bounded update to curated evidence. The next slice should stay offline, deterministic, and file-backed so it fits the current architecture and can be regression-tested with fixtures.

## Goals / Non-Goals

**Goals:**
- generate a deterministic concept-feedback review file from a successful `dress` concept result payload
- require explicit `keep` or `reject` review decisions before active evidence scores change
- append each applied review decision to a persistent feedback ledger
- apply bounded score deltas only to the selected active `dress` elements from the reviewed concept
- write a deterministic feedback report and preserve all-or-nothing file replacement behavior
- fix the remaining placeholder Purpose text in the main `signal-ingestion-pipeline` spec

**Non-Goals:**
- strategy-template feedback or prompt-template feedback
- image-satisfaction scoring or post-launch business metrics
- dynamic runtime ledger overlays during retrieval
- automatic deduplication or idempotency rules for repeated feedback on the same concept
- support beyond the `dress` category in this slice

## Decisions

### 1. Use a two-step workflow: prepare review input, then apply reviewed feedback

The workflow should mirror the successful promotion pattern:

- **prepare**: read a successful concept result payload and emit a review template
- **apply**: validate the edited review file, append a ledger entry, update active element scores, and write a feedback report

Rationale:
- this keeps machine-produced concept output separate from human approval
- reviewers get a stable file they can diff, store, and discuss in git
- apply-time validation stays strict without forcing reviewers to author the full structure manually

Alternatives considered:
- **Write feedback directly from the result payload with no review file**: rejected because it removes the explicit review gate and leaves no review artifact
- **Store only an ad hoc note next to the result JSON**: rejected because it cannot drive deterministic score application

### 2. Keep the feedback unit at the concept level, but lock the selected-element target set

The review template should be concept-level, not element-level. It should contain locked target fields derived from the successful result payload:

- `request_normalized`
- selected element summaries and `selected_element_ids`
- `concept_score`
- stable request and concept fingerprints

Reviewers should edit only:

- `decision` (`keep` or `reject`)
- `notes`

Rationale:
- this preserves the lightweight reviewer experience the user asked for
- the selected element IDs already identify the active evidence records that should receive score changes
- locked fields make tampering easy to detect during apply validation

Alternatives considered:
- **Element-by-element review**: rejected because it adds friction and over-scopes the MVP
- **Allow free editing of the target set in the review file**: rejected because it would turn apply into a mutable remapping workflow instead of a closed feedback confirmation

### 3. Persist feedback in a ledger, then apply bounded score deltas into active evidence

Apply should write an immutable ledger record and then update `base_score` on the selected active elements:

- `keep` -> `+0.02`
- `reject` -> `-0.02`
- clamp the result to the taxonomy `base_score` min/max bounds

The generation runtime should continue reading only `elements.json`; it should not dynamically merge ledger state on each request.

Rationale:
- this keeps the runtime path simple and stable
- the ledger preserves traceability and rollback context
- the bounded delta matches the MVP goal of gentle, explainable tuning instead of aggressive model-like learning

Alternatives considered:
- **Write only to a ledger and aggregate at runtime**: rejected because it complicates retrieval and scoring on every request
- **Mutate active evidence with no ledger**: rejected because it loses auditability and makes repeated experiments harder to explain

### 4. Validate the full reviewed bundle before any file mutation and write all outputs atomically

Apply should fail before mutation unless all of these are true:

- the source result payload is a successful `dress` concept result
- the reviewed file matches the deterministic template on all locked fields
- the decision is `keep` or `reject`
- every targeted `element_id` still exists in active evidence
- every score change can be clamped within the taxonomy bounds

Once validation passes, the workflow should write:

- updated `elements.json`
- updated `feedback_ledger.json`
- a `feedback_report.json`

using temp files plus replace/rollback semantics.

Rationale:
- active evidence is a curated runtime dependency and cannot be partially mutated
- the repository already uses fail-closed evidence workflows; feedback should keep the same operational bar

Alternatives considered:
- **Write ledger first, then best-effort apply**: rejected because write-stage failures could desynchronize ledger and active evidence
- **Allow missing element IDs and skip them silently**: rejected because it hides data drift that reviewers need to know about

### 5. Keep the generation success contract stable and derive feedback artifacts from it

This slice should not change `generate_dress_concept()` output shape. The feedback prepare step should derive its deterministic template entirely from the existing success payload plus active evidence context.

Rationale:
- the current generation contract is already covered by fixtures and tests
- keeping the runtime response stable reduces change surface and regression risk
- the feedback workflow is operationally downstream of concept generation, not part of the generation API itself

Alternatives considered:
- **Add feedback-only fields directly into generation results**: rejected because the current payload already contains enough information for this MVP

## Risks / Trade-offs

- **[Risk] Repeated keep/reject actions on the same concept can compound** -> Mitigation: accept this in MVP and keep the ledger explicit so future dedupe rules can be added with evidence
- **[Risk] Concept-level feedback may reward or penalize a weak element together with stronger neighbors** -> Mitigation: accept equal-weight concept feedback now and defer finer-grained element review to a future change
- **[Risk] Active evidence may drift between prepare and apply** -> Mitigation: fail apply if selected element IDs no longer exist in active evidence
- **[Risk] Ledger and active evidence could diverge on write failure** -> Mitigation: use temp-file staging plus rollback across all outputs

## Migration Plan

1. Add feedback fixtures for successful concept payloads, expected review templates, reviewed keep/reject files, expected ledger outputs, expected report outputs, and expected post-apply active evidence snapshots.
2. Implement prepare/apply feedback modules plus a dedicated CLI path.
3. Reuse active evidence taxonomy validation to clamp score updates safely.
4. Add regression coverage for deterministic review generation, valid keep/reject application, clamping, tamper detection, missing-target failures, and write-stage rollback.
5. Replace the remaining placeholder Purpose text in the main `signal-ingestion-pipeline` spec.

Rollback stays straightforward because the workflow is file-backed and repository-managed; reverting the feedback apply commit restores both active evidence and the ledger/report artifacts.

## Open Questions

- No blocking open questions remain for the concept-level `keep` / `reject` MVP.
- A future change may add strategy feedback, image-satisfaction feedback, or idempotency rules, but this slice should not include them.
