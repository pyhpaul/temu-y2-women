## Context

The current prompt bundle already contains one hero prompt plus three detail-prompt strings, but the render pipeline ignores those detail prompts and only writes a single `rendered_image.png`. The user now wants the first truly reviewable asset bundle: three hero angles (`front`, `three-quarter`, `back`) and three detail images (`construction`, `fabric`, `hem/drape`) produced from one concept result.

This change crosses prompt rendering, saved-result image rendering, and one-shot workflow surfaces. It also needs to coexist with already persisted concept results that only contain the older single-prompt contract.

## Goals / Non-Goals

**Goals:**
- Generate a deterministic six-job render bundle for successful `dress` concept results.
- Preserve stable job IDs, hero/detail grouping, and file names so downstream review can rely on a fixed output set.
- Upgrade saved-result and one-shot render flows to publish six images plus one machine-readable bundle report.
- Preserve fail-closed behavior and backward compatibility for legacy single-prompt concept results.

**Non-Goals:**
- Do not add user-configurable angle selection, optional subsets, or market-specific asset presets in this phase.
- Do not change provider semantics, add new providers, or parallelize provider dispatch yet.
- Do not redesign `factory_spec` or signal-ingestion behavior as part of this change.

## Decisions

### 1. Use a fixed six-job set in the prompt bundle

Successful concept results will emit a canonical `render_jobs` array with exactly six entries:
- `hero_front`
- `hero_three_quarter`
- `hero_back`
- `construction_closeup`
- `fabric_print_closeup`
- `hem_and_drape_closeup`

**Why:**  
The user has already chosen the target asset set, and a fixed job list keeps tests, file naming, and downstream review deterministic.

**Alternative considered:** Make the render-job set configurable now.  
**Why not now:** That expands CLI and workflow scope before the base six-image contract is stable.

### 2. Preserve the existing `prompt` field as the legacy hero entry

`prompt_bundle.prompt` will remain populated for backward compatibility, while `prompt_bundle.render_jobs` becomes the canonical downstream render contract. The `hero_front` job will act as the default hero equivalent.

**Why:**  
This lets existing success-result consumers and historical fixtures continue to validate while new workflows move to the richer job array.

**Alternative considered:** Replace `prompt` entirely with `render_jobs`.  
**Why not now:** That would make this a wider consumer-breaking change and complicate stacked work already built on the current result contract.

### 3. Render workflows consume `render_jobs` first and fall back to legacy single-image mode

The image-render input loader will expose the six-job set when present. If a saved result only contains the older single prompt, rendering will continue to produce one image and one report entry.

**Why:**  
The repository already contains persisted success fixtures and CLIs that assume the older contract. Fallback behavior keeps old payloads usable while the new bundle rolls out.

**Alternative considered:** Fail fast on legacy payloads.  
**Why not now:** It would force immediate fixture migrations and reduce the value of historical result artifacts.

### 4. Publish one bundle report with one image entry per render job

The machine-readable report will stay at `image_render_report.json`, but it will now record an `images` collection that contains per-job prompt IDs, group labels, output paths, and prompt fingerprints.

**Why:**  
One manifest is easier to persist, compare, and attach to experiments than six separate reports.

**Alternative considered:** Write one report per image.  
**Why not now:** It adds more file-surface complexity without improving determinism or review flow.

## Risks / Trade-offs

- **[Risk] Real render runs will cost more and take longer** → Mitigation: keep the fixed job set small and deterministic at six images only.
- **[Risk] Backward compatibility adds code branching** → Mitigation: isolate fallback behavior in the image-render input/loading layer rather than spreading it across CLIs.
- **[Risk] Bundle-wide failure semantics may become harder to reason about** → Mitigation: keep fail-closed publication and explicitly test legacy single-image plus six-image paths.
- **[Risk] Shared fixtures may conflict with `factory_spec` changes in parallel branches** → Mitigation: centralize final fixture reconciliation during integration instead of letting multiple agents own the same file.

## Migration Plan

1. Add the six-job prompt contract and tests first.
2. Upgrade saved-result rendering to understand the new contract while keeping single-prompt fallback behavior.
3. Upgrade one-shot workflow and CLI outputs to publish the full bundle.
4. Re-run real-provider smoke tests against the six-image output directory layout.

## Open Questions

- None for this phase. Angle selection is frozen to `front / three-quarter / back`, and image subset configurability is intentionally deferred.
