## Context

`dress-concept-generation` now runs against a curated local evidence store under `data/mvp/dress/`, and that runtime contract is stable. The remaining gap is upstream: there is still no repeatable path that converts raw market observations into reviewable evidence candidates, so every data refresh depends on manual editing of active JSON files.

Current state:

- `temu_y2_women/orchestrator.py` reads only validated active evidence files.
- `temu_y2_women/evidence_repository.py` now enforces schema, taxonomy, and authoring rules for active evidence.
- The repository has no ingestion-specific modules, no raw-signal fixtures, and no staged draft area separate from active evidence.

Primary constraints:

- The existing `dress-concept-generation` request/result/error contract must remain unchanged.
- This change must stay offline and dependency-light; it should not introduce browser automation, network scraping, LLM extraction, or database infrastructure.
- Outputs must be deterministic and reviewable so later ranking work can rely on them.

## Goals / Non-Goals

**Goals:**
- Define a stable file-backed schema for raw `dress` signal bundles that can be prepared manually or by future scrapers.
- Normalize and validate raw signals before extraction so bad input fails fast with structured ingestion errors.
- Produce draft element candidates and draft strategy hints in a staging area without mutating active evidence files.
- Preserve provenance from each draft artifact back to one or more source signal records.
- Add deterministic CLI and fixture-driven test coverage for ingestion success and failure paths.

**Non-Goals:**
- Automated web scraping or source crawling.
- Direct writes into `data/mvp/dress/elements.json` or `strategy_templates.json`.
- Learned extraction, LLM-assisted parsing, or external NLP dependencies.
- Ranking-model changes, prompt rendering changes, or image-generation integration.
- Multi-category support beyond `dress`.

## Decisions

### 1. Introduce a separate staging pipeline instead of writing into active evidence files

This change should add a staging area such as `data/staging/dress/` and keep active runtime data under `data/mvp/dress/` untouched.

The staged outputs should include:
- `normalized_signals.json`
- `draft_elements.json`
- `draft_strategy_hints.json`
- `ingestion_report.json`

Rationale:
- The current runtime already treats active evidence as validated production input.
- Signal ingestion is inherently noisier than curated evidence authoring.
- A separate staging area keeps review and promotion explicit and prevents ingestion mistakes from silently affecting generation.

Alternatives considered:
- **Write draft results directly into active evidence files**: rejected because it would mix noisy upstream data with runtime-critical curated assets.
- **Keep staging only in memory**: rejected because reviewable artifacts are part of the change value.

### 2. Use a structured raw-signal schema instead of scraping-oriented free text blobs

The ingestion input should be a file-backed signal bundle such as `raw_signals.json` with records that include explicit fields like:
- `signal_id`
- `source_type`
- `source_url`
- `captured_at`
- `target_market`
- `category`
- `title`
- `summary`
- `observed_price_band`
- `observed_occasion_tags`
- `observed_season_tags`
- `manual_tags`
- `status`

Rationale:
- This keeps the change offline and testable.
- Future scrapers can target this schema without forcing ingestion logic to understand site-specific HTML.
- Explicit fields reduce ambiguity and make fixture-driven validation straightforward.

Alternatives considered:
- **Accept arbitrary HTML or copied page dumps**: rejected because it would couple this change to unstable source-specific parsing.
- **Reuse the active evidence schema as input**: rejected because raw signals and curated evidence serve different stages of the pipeline.

### 3. Keep extraction deterministic with file-backed phrase rules plus the existing evidence taxonomy

Extraction should remain rule-based. The implementation should add a small phrase-mapping file for `dress` signal interpretation and reuse `data/mvp/dress/evidence_taxonomy.json` for allowed slots, tags, seasons, occasions, and risk flags.

The extraction flow should:
- canonicalize normalized text and manual tags
- match supported phrases to canonical slot/value pairs
- derive supported tags, seasons, occasions, and price-band context
- reject unsupported output before any draft artifact is written

Rationale:
- Deterministic rules fit the current standard-library stack and are easy to regression test.
- The taxonomy already defines the runtime vocabulary; reusing it keeps ingestion and generation aligned.
- File-backed phrase rules are easier to review than hidden extraction logic in Python code.

Alternatives considered:
- **Hard-code phrase rules in Python**: rejected because business mappings would become harder to inspect and revise.
- **Use an LLM or external NLP library for extraction**: rejected because it would add nondeterminism and external dependencies too early.

### 4. Aggregate draft outputs by canonical business keys and preserve provenance

Draft element candidates should aggregate by canonical `slot + value`, and draft strategy hints should aggregate by stable market/season/occasion context. Each draft record should include:
- merged source signal IDs
- a generated evidence summary or reasoning note
- proposed tags and context fields
- a deterministic suggested score or priority signal
- `status: draft`

Rationale:
- Multiple raw signals often point to the same commercial direction.
- Aggregation reduces reviewer noise and makes promotion into curated evidence easier.
- Provenance must survive aggregation so later reviewers can trace where a draft came from.

Alternatives considered:
- **Emit one draft record per source signal**: rejected because reviewers would need to deduplicate obvious repeats by hand.
- **Drop provenance after aggregation**: rejected because later evidence promotion would become unauditable.

### 5. Add a dedicated ingestion entrypoint instead of changing the existing generation CLI contract

The existing `temu_y2_women/cli.py` should keep its current generation-oriented interface. This change should add a separate ingestion entrypoint that reads a raw signal file and writes staged artifacts to an output directory.

Rationale:
- The current generation CLI is already covered by regression tests and should stay stable.
- Ingestion and generation are different workflows with different inputs and outputs.
- A separate entrypoint keeps migration risk low and avoids forcing a breaking CLI redesign now.

Alternatives considered:
- **Convert the current CLI to subcommands in this change**: rejected because it broadens scope and risks unnecessary churn in a stable path.

## Risks / Trade-offs

- **[Risk] Rule-based extraction may miss legitimate fashion phrasing** → Mitigation: keep mappings file-backed, test against fixed fixtures, and stage outputs for manual review instead of assuming completeness.
- **[Risk] Draft strategy hints could overfit sparse signals** → Mitigation: keep them explicitly marked as `draft` and derive only coarse season/occasion/context hints in this change.
- **[Risk] Staging artifacts may drift from the active evidence schema over time** → Mitigation: keep draft element fields intentionally close to the curated element schema and validate against the same taxonomy.
- **[Risk] Provenance-heavy artifacts can become verbose** → Mitigation: aggregate by canonical business keys and store source references compactly as IDs plus summary counts.

## Migration Plan

1. Add raw signal fixtures, phrase rules, and a staging directory convention for `dress`.
2. Implement ingestion modules for bundle loading, signal normalization, deterministic extraction, aggregation, and report writing.
3. Add a dedicated ingestion CLI entrypoint plus regression tests for valid and invalid fixtures.
4. Keep `dress-concept-generation` runtime loading unchanged, with staged outputs reviewed manually before any future promotion flow is added.

Rollback remains low-risk because this change is additive and does not alter the active generation contract or mutate production evidence files.

## Open Questions

- No blocking open questions remain for the first implementation slice.
- Automatic promotion from staged drafts into curated active evidence is intentionally deferred to a later change after ingestion outputs prove stable.
