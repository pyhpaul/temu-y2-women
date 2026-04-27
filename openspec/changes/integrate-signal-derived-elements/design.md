## Context

Current signal ingestion already produces deterministic `draft_elements.json`, `draft_strategy_hints.json`, and an ingestion report. Promotion review and apply flows can then move accepted drafts into active evidence. That basic chain exists, but it is still thin in three places:
- extraction provenance is not rich enough for reviewers to understand why a draft was emitted
- ingestion reporting is not expressive enough to show coverage and unmatched signals clearly
- promotion review/apply surfaces do not emphasize merge rationale strongly enough for frequent evidence refresh use

This phase should improve those operational qualities without short-circuiting human review or auto-injecting staged drafts into the live generation path.

## Goals / Non-Goals

**Goals:**
- Improve extraction provenance and coverage reporting in staged signal-ingestion outputs.
- Strengthen promotion review/apply semantics for signal-derived updates.
- Keep the entire chain deterministic and staging-first.
- Expand regression coverage for realistic signal-derived element refresh scenarios.

**Non-Goals:**
- Do not make the orchestrator consume staged drafts directly in this phase.
- Do not introduce fuzzy matching, LLM-based extraction, or non-deterministic merge heuristics.
- Do not redesign the active evidence schema beyond what is needed for clearer staged review and promotion.

## Decisions

### 1. Keep ingestion purely staging-oriented

Signal ingestion will continue to write staged artifacts only. Active evidence files will remain unchanged until a reviewed promotion apply run succeeds.

**Why:**  
This preserves the existing safety boundary between raw market signals and runtime evidence used by concept generation.

**Alternative considered:** Allow ingestion to auto-refresh active evidence when confidence is high.  
**Why not now:** The user explicitly wants clarity before automation, and current evidence maturity is not high enough for unattended promotion.

### 2. Add deterministic provenance and coverage metadata instead of fuzzy confidence scores

Staged artifacts and reports will explain which rule matches, signal IDs, and canonical identities led to a draft output. They will not introduce probabilistic confidence layers.

**Why:**  
Reviewers need traceability more than pseudo-precision, and deterministic metadata is easier to test and trust.

**Alternative considered:** Add weighted confidence metrics.  
**Why not now:** The current extraction model is rule-based, so synthetic confidence numbers would overstate certainty.

### 3. Preserve canonical merge identity through review and apply

The same canonical slot/value identity used to stage drafts will remain visible in review templates and promotion validation so create-vs-update semantics stay stable.

**Why:**  
This reduces reviewer ambiguity and makes failed promotion validation easier to reason about.

**Alternative considered:** Recompute merge intent independently during apply.  
**Why not now:** That can create confusing review/apply mismatches for the same draft input.

## Risks / Trade-offs

- **[Risk] Richer staged metadata may increase fixture churn** → Mitigation: keep additions deterministic and reviewable rather than adding broad schema redesign.
- **[Risk] Review templates may become noisier** → Mitigation: prioritize provenance that helps merge decisions and avoid dumping raw normalized text blindly.
- **[Risk] Parallel work on evidence files can conflict with other branches** → Mitigation: keep this phase focused on staging/promotion contracts, not broad active-evidence content updates.

## Migration Plan

1. Extend staged ingestion outputs and report content.
2. Extend review template generation and promotion validation to carry the same merge-ready metadata.
3. Add end-to-end regression fixtures for successful and failing reviewed promotions.

## Open Questions

- None for this phase. Direct orchestrator consumption of signal-derived drafts remains intentionally out of scope.
