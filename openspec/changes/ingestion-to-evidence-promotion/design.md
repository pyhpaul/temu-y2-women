## Context

The repository already has:

- validated active evidence under `data/mvp/dress/`
- deterministic staged draft outputs from `signal-ingestion-pipeline`
- a stable `dress-concept-generation` runtime that reads only active evidence

The missing link is promotion. Today, staged drafts are reviewable, but there is no system path that:

1. prepares a reviewer-facing decision file
2. validates those decisions against the same evidence guardrails as runtime data
3. writes approved changes back into active evidence without partial mutation

This gap keeps the ingestion pipeline operationally incomplete. The next step should stay offline, deterministic, and file-backed, just like the existing evidence and ingestion work.

## Goals / Non-Goals

**Goals:**
- generate a deterministic review template from staged draft artifacts
- require explicit accept/reject/edit decisions before active evidence changes
- validate promotion decisions against taxonomy and active-evidence rules
- merge accepted draft elements and strategy hints into active evidence files deterministically
- write a promotion report that preserves provenance and action summaries

**Non-Goals:**
- automatic promotion with no human review gate
- browser-based moderation UI
- network services, databases, or external dependencies
- changing the generation request/result contract
- multi-category support beyond `dress`

## Decisions

### 1. Use a two-step workflow: prepare review input, then apply reviewed decisions

The workflow should have two explicit stages:

- **prepare**: read staged artifacts and emit a review file
- **apply**: validate the edited review file and mutate active evidence if valid

Rationale:
- this preserves the separation between machine-suggested drafts and human-approved evidence
- reviewers need a stable file to edit, diff, and store in git
- apply-time validation can remain strict without forcing reviewers to author the whole structure from scratch

Alternatives considered:
- **Directly promote staged drafts with defaults**: rejected because it removes the explicit review gate
- **Require reviewers to hand-author a promotion file from zero**: rejected because it is too error-prone and wastes the structure already present in staged drafts

### 2. Keep the review file close to active schemas, with decision metadata layered on top

Accepted draft records should be edited inside a promotion review document that includes:

- source `draft_id` / `hint_id`
- `decision` (`accept` or `reject`)
- provenance fields from staged drafts
- reviewer-editable curated fields that are close to the active element or strategy-template schema

Rationale:
- near-active shapes make promotion validation and merging simpler
- reviewers can edit the final curated record directly instead of juggling a separate mapping layer
- the file stays readable in git and deterministic for regression tests

Alternatives considered:
- **Store only decisions and derive final records automatically**: rejected because reviewers need to tune fields like tags, summaries, scores, and IDs
- **Allow a free-form notes-only review format**: rejected because it cannot drive deterministic file mutation

### 3. Make apply validation fail before any file mutation

Promotion apply should validate the full reviewed bundle first:

- all referenced drafts exist in staged artifacts
- all non-rejected records have complete reviewed content
- reviewed elements satisfy the active evidence taxonomy and quality rules
- reviewed strategy templates reference only values that will exist after accepted element promotions are applied

Only after full validation passes should the system write active evidence files.

Rationale:
- partial writes would corrupt the curated runtime store
- the repository already treats evidence validation as fail-closed; promotion should preserve that bar
- all-or-nothing validation is easy to reason about in an offline file-backed workflow

Alternatives considered:
- **Write file-by-file as records validate**: rejected because one late error could leave active evidence in a mixed state
- **Allow unresolved references during review and defer them silently**: rejected because it hides authoring mistakes

### 4. Merge promoted elements by canonical business identity, not just draft identity

For element promotion, merge behavior should be based on active-evidence identity:

- existing active element with the same canonical `slot + value` may be updated in place through the reviewed record
- new canonical `slot + value` should be appended as a new active element
- conflicting duplicate active outcomes should fail validation

For strategy templates:

- existing `strategy_id` may be updated in place
- new `strategy_id` may be appended
- slot preferences must be validated against the post-promotion active evidence set

Rationale:
- draft IDs are staging-only identifiers and cannot be the long-term merge key
- canonical `slot + value` already anchors active element uniqueness rules
- strategy templates already use `strategy_id` as their stable identity

Alternatives considered:
- **Always create new active records**: rejected because it would create duplicates and break uniqueness rules
- **Merge by draft ID into active data**: rejected because draft IDs are not part of the curated runtime contract

### 5. Emit a promotion report alongside writes

Apply should generate a deterministic report that summarizes:

- accepted / rejected counts
- created / updated counts for elements and strategies
- source staged artifact paths
- promoted source IDs and warnings

Rationale:
- promotion is an operational workflow, so reviewers need a machine-readable audit trail
- the report makes regression tests and later feedback analysis easier

Alternatives considered:
- **Rely only on git diff for auditability**: rejected because git diff alone does not summarize decision-level outcomes

## Risks / Trade-offs

- **[Risk] Review files may become verbose** → Mitigation: keep them deterministic, schema-shaped, and scoped to staged draft records only
- **[Risk] Merge semantics for existing active records may surprise reviewers** → Mitigation: make prepare output explicit about whether a draft maps to create vs update paths
- **[Risk] Strategy promotion can fail because element promotion changed the available vocabulary** → Mitigation: validate strategy references against the post-promotion active evidence snapshot
- **[Risk] Manual review still limits throughput** → Mitigation: accept this for now; the goal is a safe bridge from draft artifacts to curated evidence, not fully automated curation

## Migration Plan

1. Add promotion fixtures for staged inputs, review-template outputs, reviewed decision files, and expected active-evidence results.
2. Implement prepare/apply promotion modules plus a dedicated CLI path.
3. Reuse and extend active-evidence validation during apply.
4. Add regression tests for review-template generation, valid promotion, rejected drafts, and fail-before-mutation error paths.

Rollback remains straightforward because the workflow is file-backed and repository-managed; reverted commits restore both the active evidence and the archived promotion artifacts.

## Open Questions

- No blocking open questions remain for the first promotion slice.
- A future change may add richer conflict-resolution tooling or UI review surfaces, but this change should stay file-based.
