## Context

After the MVP, evidence enrichment, and signal-ingestion changes were merged, the main remaining quality gap in `dress` concept generation was local greedy composition. The runtime still picked `pattern` and `detail` independently, which could produce outputs where the elements scored well in isolation but fought each other stylistically.

The approved scope for this change was deliberately narrow:

- fix the user-visible `pattern` / `detail` conflict problem first
- use explicit rule data instead of subjective general-purpose style inference
- preserve the existing top-level request, result, and error contracts
- avoid turning the composition engine into a global solver

## Goals / Non-Goals

**Goals**
- express curated `pattern/detail` compatibility rules as reviewable data
- validate those rules fail-closed before generation uses them
- centralize compatibility evaluation in one module
- rerank only the optional `pattern/detail` pair with strong-conflict rejection and weak-conflict penalties
- surface compatibility behavior through existing explainability fields

**Non-Goals**
- learned ranking or embeddings
- multi-slot global optimization
- prompt-contract changes
- new external dependencies
- expansion to other slot pairs in the first pass

## Decisions

### 1. Store compatibility rules as file-backed evidence

The implementation adds `data/mvp/dress/compatibility_rules.json` for explicit curated `pattern/detail` rules.

Why:
- the problem is missing explicit compatibility knowledge, not missing model complexity
- rule data should stay reviewable and editable outside Python code
- evidence authoring errors should fail during loading instead of silently changing runtime behavior

### 2. Centralize rule loading and pair evaluation

Compatibility loading, validation, and pair evaluation live in `temu_y2_women/compatibility_evaluator.py`.

Why:
- the composition engine should consume compatibility outcomes, not embed rule semantics everywhere
- strong and weak conflicts need one shared interpretation
- tests are simpler when the compatibility surface is isolated

### 3. Keep composition changes local to `pattern/detail`

The runtime keeps:
- required-slot selection greedy
- `neckline` and `sleeve` greedy
- only `pattern/detail` under bounded reranking

Why:
- the user asked to solve the concrete style-conflict issue first
- a local search is enough to improve outputs without rewriting the entire solver
- the design stays proportional to the current evidence quality and product scope

### 4. Reuse existing explainability output

Compatibility notes are written into `constraint_notes`, and weak-conflict penalties are reflected in `concept_score`.

Why:
- the response contract stays stable
- the final result explains both avoided strong conflicts and applied weak penalties
- internal selection logic and external scoring stay aligned

## Risks / Trade-offs

- **Sparse rules may only partially improve style quality**  
  Accepted for v1; the main goal is a stable mechanism, not full coverage.

- **Bad penalty authoring could distort selection behavior**  
  Mitigated by fail-closed validation for finite, non-negative penalties and `strong -> 0.0` semantics.

- **Composition complexity could keep growing**  
  Mitigated by isolating compatibility logic and limiting bounded search to one optional slot pair.

## Migration / Rollout

1. Add and validate compatibility rule data.
2. Add centralized compatibility evaluation.
3. Apply bounded `pattern/detail` reranking in composition.
4. Propagate notes and penalties into final composed concepts.
5. Run regression suites and repository guardrails.

No external contract migration is required because the change stays behind existing request/result shapes.
