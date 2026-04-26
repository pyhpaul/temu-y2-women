## Context

`dress-generation-mvp` is now merged and archived, and the repository has a live `dress-concept-generation` capability under `openspec/specs/dress-concept-generation/spec.md`. The runtime can already normalize requests, select strategies, retrieve local evidence, compose a concept, and render prompts, but the current evidence store is intentionally minimal: a single happy-path seasonal cluster plus a small negative-control set.

Current state:

- `data/mvp/dress/elements.json` contains only a handful of active elements.
- `data/mvp/dress/strategy_templates.json` is lightly validated and tuned around the MVP flow.
- `temu_y2_women/evidence_repository.py` validates field presence and a few strategy shapes, but it does not yet enforce explicit slot/tag/risk dictionaries, duplicate detection, or authoring-quality rules.
- The current regression suite proves the chain works, but it does not yet prove the offline evidence store is broad and disciplined enough for the next phases.

Primary constraints:

- The top-level request, result, and error contracts for `dress-concept-generation` must remain stable.
- This change must stay in the offline evidence-store layer; it must not expand into automated ingestion, ranking-model work, or image-generation integration.
- The implementation should remain dependency-light and keep the current Python standard-library stack.

## Goals / Non-Goals

**Goals:**
- Upgrade the local `dress` evidence store from demo-quality data to a curated offline asset with broader element coverage.
- Centralize supported `slot`, `tag`, and `risk` vocabularies so evidence authoring rules are explicit and reviewable.
- Harden evidence validation so invalid, duplicate, conflicting, or low-quality records fail fast with `INVALID_EVIDENCE_STORE`.
- Expand deterministic validation coverage across multiple request archetypes and invalid-store fixtures.

**Non-Goals:**
- Automated web scraping or signal ingestion.
- Learned ranking, compatibility search, or other scoring-model changes.
- Real image generation integration.
- Multi-category expansion beyond `dress`.
- Database migration away from file-backed storage.
- Changes to the external request, result, prompt-mode, or structured-error contracts except where invalid-store validation becomes more explicit.

## Decisions

### 1. Keep the existing capability contract and treat this as a data-quality change

This change modifies `dress-concept-generation` instead of introducing a new capability or a new external API.

Rationale:
- The first change already established the top-level contract and proved the main chain.
- The current problem is data stability, not missing orchestration behavior.
- Keeping the external contract stable lets later changes focus on ingestion, ranking, and output integrations without reopening the same boundary.

Alternatives considered:
- **Create a separate evidence-management capability**: rejected because this change still serves the existing generation path and does not yet create a standalone user-facing workflow.

### 2. Introduce a dedicated taxonomy file for evidence dictionaries

The curated store should add a file-backed taxonomy document, such as `data/mvp/dress/evidence_taxonomy.json`, that defines the supported `slot`, `tag`, `season`, `occasion`, and `risk` vocabularies plus authoring guardrails used during validation.

Rationale:
- The approved scope explicitly calls for solidifying `slot / tag / risk` dictionaries.
- A dedicated taxonomy file keeps the rules inspectable and editable without hard-coding them in Python.
- The same taxonomy can validate both element records and strategy references.

Alternatives considered:
- **Hard-code dictionaries in `evidence_repository.py`**: rejected because it hides reviewable business data inside implementation code.
- **Document the rules only in Markdown**: rejected because prose-only rules cannot gate invalid data at runtime.

### 3. Prefer validation-first loading over permissive filtering

Evidence loading should fail fast when active records violate structural, dictionary, or quality rules instead of silently skipping bad data.

Validation should cover at least:
- supported dictionary membership for slots, tags, seasons, occasions, and risk flags
- unique active `element_id` values
- no duplicate active `slot` + `value` combinations for `dress`
- bounded `base_score` values and stable authoring rules for `evidence_summary`
- active strategy references that point only to known slot values and supported tags

Rationale:
- Silent filtering would make later failures difficult to interpret.
- This change is explicitly about making the offline store stable enough to build on.
- Failing fast keeps data-review feedback tight and testable.

Alternatives considered:
- **Skip invalid records and continue generation**: rejected because it would hide taxonomy drift and make deterministic validation unreliable.

### 4. Expand curated element coverage without changing the retrieval contract

The implementation should broaden `elements.json` so required and optional slots have enough active coverage for more than the original vacation-only happy path, but the runtime should still expose the same `retrieved_elements` and `composed_concept` shapes.

Rationale:
- The user-approved scope is to make the data layer more stable, not to redesign downstream payloads.
- Broader data coverage can improve stability immediately without forcing prompt, composition, or API rewrites.
- This keeps the next changes focused on signal ingestion and ranking hardening instead of contract repair.

Alternatives considered:
- **Add new downstream fields to explain scoring provenance now**: rejected because that broadens the API surface before the data-quality baseline is settled.

### 5. Treat validation fixtures as part of the evidence-store contract

The validation suite should expand from a minimal MVP pair to a small request matrix plus invalid-store fixtures.

At minimum it should cover:
- multiple successful request archetypes that rely on different parts of the enriched store
- at least one constrained failure path
- invalid evidence fixtures for dictionary violations, duplicate/conflicting records, and other quality-rule failures

Rationale:
- The change definition is about whether the evidence store is stable enough, so the verification surface must move with it.
- Fixed fixtures keep future data edits reviewable and reproducible.

Alternatives considered:
- **Rely on ad-hoc manual checks after data edits**: rejected because they are too weak for a change whose main output is curated data quality.

## Risks / Trade-offs

- **[Risk] A taxonomy that is too strict could block legitimate future evidence additions** → Mitigation: keep the taxonomy explicitly dress-only for now and version it as file-backed data.
- **[Risk] Broader data coverage may shift deterministic outputs in existing tests** → Mitigation: update the validation suite to lock expected outcomes for the approved request matrix.
- **[Risk] Authoring-quality rules can drift into subjective style judgments** → Mitigation: keep runtime validation limited to structural and maintainability rules rather than fashion-opinion scoring.
- **[Risk] Strategy references may become the hidden source of store inconsistency** → Mitigation: validate strategy tags and slot preferences against the same taxonomy and active element values.

## Migration Plan

1. Add the new taxonomy file and enrich the curated `dress` evidence data.
2. Harden `evidence_repository.py` so taxonomy, duplicate, score, summary, and strategy-reference validation happen before retrieval.
3. Add request fixtures and invalid evidence-store fixtures that prove both broader success coverage and fail-fast behavior.
4. Run the automated regression suite and OpenSpec validation for the change.

Rollback remains low-risk because the system is still file-backed and this change does not alter persisted production data or external integrations. Reverting the change restores the previous evidence files and validation rules.

## Open Questions

- No blocking open questions remain for this change.
- More advanced score decomposition, ingestion provenance, and ranking-model inputs remain intentionally deferred to later changes.
