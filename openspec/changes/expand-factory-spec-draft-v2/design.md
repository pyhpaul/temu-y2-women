## Context

The repository already emits `factory_spec` with `known`, `inferred`, and `unresolved` sections. That solved the first contract gap, but the current guidance is still narrow: it highlights fabric/detail checks and visible construction priorities, yet it does not surface enough deterministic notes for sample review, QA review, and commercial handoff discussions.

This phase should make the draft more useful without crossing the line into fake precision. The evidence store still lacks supplier-grade fields like fiber percentages, GSM, measurement specs, seam allowance, tolerance, and BOM detail, so the richer draft must remain guidance-oriented and evidence-backed.

## Goals / Non-Goals

**Goals:**
- Expand deterministic `factory_spec` guidance so reviewers get clearer sample-review and QA watchpoints.
- Preserve the existing top-level `known / inferred / unresolved` structure to reduce contract churn during parallel work.
- Improve how request context and concept evidence are reflected in the draft output.
- Keep all unsupported numeric production fields explicit and unresolved.

**Non-Goals:**
- Do not generate supplier-ready tech packs, BOMs, size charts, seam allowances, or tolerances.
- Do not introduce LLM-generated production notes or any non-deterministic inference layer.
- Do not require new evidence-source files or manual authoring flows in this change.

## Decisions

### 1. Keep the top-level `factory_spec` shape stable

The draft will continue to expose `known`, `inferred`, and `unresolved` at the top level. Enhancements will be additive inside those sections.

**Why:**  
This change is running in parallel with other result-contract work, so keeping the top-level shape stable reduces unnecessary integration conflicts.

**Alternative considered:** Introduce a breaking `factory-spec-v2` top-level schema with nested sections and grouped unresolved objects.  
**Why not now:** The user needs richer draft output, not a full contract redesign.

### 2. Add richer deterministic review notes under `inferred`

New inferred fields will focus on:
- sampling watchpoints
- QA review notes
- fit/commercial review cues
- visible construction and print-balance checks
- open questions that must stay unresolved until real production inputs exist

**Why:**  
The current evidence can support qualitative review priorities, and those are the most useful next step before supplier-grade metadata exists.

**Alternative considered:** Expand `known` aggressively with guessed construction fields.  
**Why not now:** That would blur the line between preserved concept facts and rule-derived guidance.

### 3. Preserve unresolved numeric production fields explicitly

Unsupported fields such as GSM, fiber percentages, measurements, seam allowance, tolerance, and BOM-grade trim data will remain unresolved and visible in the draft output.

**Why:**  
This protects the system from overclaiming production readiness while still showing what inputs are missing.

**Alternative considered:** Hide unresolved fields until a later phase.  
**Why not now:** Reviewers need to see the gap list to understand the current maturity level.

## Risks / Trade-offs

- **[Risk] Added guidance may feel generic if over-expanded** → Mitigation: only add fields that can be tied directly to existing request context and selected elements.
- **[Risk] Result fixtures may conflict with parallel image-bundle work** → Mitigation: keep the top-level shape stable and centralize final fixture reconciliation during integration.
- **[Risk] Consumers may mistake richer notes for supplier-ready data** → Mitigation: continue surfacing unresolved production fields explicitly and avoid numeric fabrication entirely.

## Migration Plan

1. Extend `factory_spec_builder.py` with additive inferred guidance fields.
2. Update result packaging and fixtures.
3. Add focused regression tests, then re-run the full repository suite.

## Open Questions

- None for this phase. Supplier-grade numeric production metadata remains a future phase with separate data-source requirements.
