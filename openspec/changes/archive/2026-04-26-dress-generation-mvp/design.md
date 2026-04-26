## Context

The repository already contains a V2 design for a larger Temu US womenswear generation system, but the project does not yet have a concrete first implementation slice. This change intentionally narrows scope to a single `dress`-only MVP that proves the core chain can run end-to-end before the project expands into evidence-store enrichment, signal ingestion, image generation, or feedback loops.

Current state:

- There is no existing runtime implementation.
- There are no existing OpenSpec capabilities under `openspec/specs/`.
- The system boundaries for the MVP and the next change have already been approved in `docs/superpowers/specs/2026-04-26-dress-generation-mvp-design.md`.

Primary constraint:

- The first implementation change must stay small enough to verify quickly and must return explainable outputs rather than opaque prompt text.

## Goals / Non-Goals

**Goals:**
- Define a minimal end-to-end generation flow for `dress` requests.
- Lock the request, result, and error contracts so later changes build on a stable interface.
- Use a local structured MVP evidence store for elements and strategy templates.
- Produce a structured `composed_concept` and mode-specific prompt bundle instead of mixing all logic into one prompt string.
- Keep validation deterministic with fixed sample requests and expected explainable outcomes.

**Non-Goals:**
- Automated public-signal ingestion.
- Large-scale evidence-store construction or normalization tooling.
- Complex ranking models or learned weights.
- Real image generation API integration.
- Feedback capture or business-loop writeback.
- Multi-category support beyond `dress`.

## Decisions

### 1. Use a single MVP capability centered on concept generation

The change introduces one capability, `dress-concept-generation`, rather than splitting request parsing, evidence loading, and prompt rendering into separate OpenSpec capabilities.

Rationale:
- The user-facing contract is one end-to-end chain.
- Splitting now would create artificial boundaries before there is any implementation pressure to justify them.
- The next change, `enrich-dress-evidence-store`, can extend the data quality of the same capability without redefining the top-level behavior.

Alternatives considered:
- **Multiple MVP capabilities** for request parsing, evidence storage, and rendering: rejected because it would over-model internal structure before the first vertical slice exists.

### 2. Prefer file-backed MVP data over a database

The MVP SHALL read from local structured files:

- `data/mvp/dress/elements.json`
- `data/mvp/dress/strategy_templates.json`

Rationale:
- The first change is validating the chain, not the storage platform.
- File-backed data is easier to inspect, review, and hand-correct during early iterations.
- A later migration to SQLite or Postgres can happen without changing the request/result contract.

Alternatives considered:
- **SQLite from day one**: rejected because it adds schema and migration work without helping prove the main flow.
- **Hard-coded in source**: rejected because it makes evidence updates and review harder than structured data files.

### 3. Use a structured composition boundary before prompt rendering

The generation flow SHALL produce a structured `composed_concept` before prompt rendering.

Rationale:
- It cleanly separates retrieval/composition decisions from prompt wording.
- It keeps A and B modes aligned while allowing different rendering emphasis.
- It makes debugging easier because concept-level defects are visible before prompt construction.

Alternatives considered:
- **Render prompts directly from candidates**: rejected because it hides selection logic in prompt assembly and makes failures harder to explain.

### 4. Keep composition logic transparent and rule-based

The MVP composition engine SHALL use slot-based selection with transparent scoring and a small set of hard constraints:

- `silhouette` and `fabric` are required
- `neckline` and `sleeve` are strongly preferred
- `pattern` and `detail` are optional
- `avoid_tags` exclude candidates
- `must_have_tags` must be satisfied before success

Rationale:
- The first change needs deterministic, explainable behavior.
- A greedy slot-based selection flow is sufficient for validating the chain.
- More advanced ranking and compatibility logic is explicitly deferred to a later change.

Alternatives considered:
- **Backtracking or search-based composition**: rejected as unnecessary complexity for the first slice.
- **Free-form prompt-only generation**: rejected because it would not create a stable contract for later improvements.

### 5. Treat structured errors and repeatable validation as first-class output

The MVP SHALL return structured errors for unsupported requests, missing strategies, missing candidates, constraint conflicts, and incomplete concepts. It SHALL also define fixed validation scenarios that cover both success and failure flows.

Rationale:
- Early-stage systems fail more often on contracts than on happy-path logic.
- Explainable failures are required to keep future ingestion and ranking work debuggable.
- Stable sample requests and golden outputs provide regression safety even before full implementation exists.

Alternatives considered:
- **Ad-hoc exceptions and logs only**: rejected because they are insufficient as a durable external contract.

## Risks / Trade-offs

- **[Risk] Thin MVP data may make outputs look unstable even if the chain is correct** → Mitigation: explicitly scope the next change to evidence-store enrichment instead of overextending this one.
- **[Risk] Greedy slot selection may reject combinations a richer solver could rescue** → Mitigation: keep requirements limited to explainable baseline composition and defer hardening to `harden-ranking-and-constraints`.
- **[Risk] No real image generation in this change may reduce perceived completeness** → Mitigation: document that prompt-bundle output is the completion target for this MVP and keep image integration as a later dedicated change.
- **[Risk] File-backed evidence can drift without validation discipline** → Mitigation: add validation fixtures and keep schema shape explicit in the spec.

## Migration Plan

1. Add the new OpenSpec capability and its requirements.
2. Implement the minimal runtime modules and CLI entrypoint for the end-to-end `dress` flow.
3. Add the local MVP evidence files and sample validation fixtures.
4. Verify fixed sample requests for both success and failure scenarios.
5. Keep the request/result contract stable while later changes extend data quality and downstream integrations.

Rollback is low-risk because this is a net-new capability with no existing runtime to preserve. Reverting the change removes the new capability, local data files, and fixtures without requiring data migration.

## Open Questions

- No blocking open questions remain for this change.
- Real image generation integration, richer ranking, and automated evidence ingestion are intentionally deferred to later changes and are not blockers for this MVP.
