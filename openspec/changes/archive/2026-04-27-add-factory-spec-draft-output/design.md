## Context

The repository now produces stronger production-oriented visual prompts, but the successful `dress` concept result still stops at concept, prompt, and warning outputs. Reviewers can inspect the generated hero image and prompt text, yet they still lack a deterministic draft artifact that summarizes production-relevant facts, visible construction priorities, and known data gaps.

Current evidence records only model high-level concept elements such as silhouette, fabric name, neckline, sleeve, pattern, and detail. They do not yet store full production metadata like fiber content, GSM, lining, closure specs, measurements, tolerances, or BOM details. That means the next output must stay explicitly draft-oriented and must not invent unsupported manufacturing values.

## Goals / Non-Goals

**Goals:**
- Add a deterministic `factory_spec` draft artifact to successful `dress` concept generation results.
- Separate production-facing information into `known`, `inferred`, and `unresolved` sections so downstream users can tell which fields are explicit, which are rule-derived, and which still require authoring.
- Reuse existing selected elements, request context, and deterministic rules rather than introducing model-generated production metadata.
- Record the future expansion path for detailed production metadata in a formal project artifact.

**Non-Goals:**
- Do not generate a full tech pack, BOM, size chart, tolerance table, or supplier-ready sewing instructions.
- Do not invent fiber percentages, GSM values, lining specs, closure specs, measurement values, or other unsupported numeric production data.
- Do not change the current image-render workflow contract or require new render artifacts in this change.

## Decisions

### 1. Embed `factory_spec` inside the successful concept result package

The initial draft output will be returned as a new `factory_spec` field inside the successful generation result, not as a separate standalone file contract.

**Why:**  
The concept result is already the stable handoff artifact for prompt rendering, image generation, and experiment review. Embedding the draft spec there keeps the new output attached to the same deterministic concept snapshot and allows one-shot workflows to persist it automatically inside `concept_result.json`.

**Alternative considered:** Emit a separate `factory_spec.json` file from generation workflows.  
**Why not now:** That would add file-publication behavior and new CLI/output-surface complexity before the schema itself is validated.

### 2. Use a three-part draft schema: `known`, `inferred`, `unresolved`

The draft spec will classify output into:
- `known`: directly selected or preserved concept facts
- `inferred`: deterministic production-facing guidance derived from known facts
- `unresolved`: explicit missing fields that require future evidence metadata or human authoring

**Why:**  
This matches the current data maturity of the repository. Reviewers need something usable now, but they also need to know which fields are still placeholders or future expansion areas.

**Alternative considered:** Flatten everything into one object.  
**Why not now:** That would blur the line between supported facts and provisional guidance, making it easier to over-trust the draft output.

### 3. Keep the inference layer rule-based and repository-local

The `inferred` section will be generated through deterministic rules tied to selected elements and request context, such as:
- `fabric` → fabric-handfeel and visible texture expectations
- `detail` → construction review focus
- `avoid_tags` / fit-related selections → fit-intent notes
- seasonal/occasion context → review context for commercial plausibility

**Why:**  
The project currently relies on deterministic, local evidence. Extending that pattern avoids hallucinated production details and keeps regression coverage straightforward.

**Alternative considered:** Use an LLM or image model prompt to synthesize production notes.  
**Why not now:** That would undermine the repository’s deterministic contracts and create unsupported production claims.

### 4. Treat detailed production metadata as an explicit follow-up direction

The design will record a follow-up path for richer metadata on at least:
- fabric composition
- GSM / weight range
- lining
- closure details
- measurement / POM data
- seam allowance
- tolerance
- BOM-grade trim data

**Why:**  
The user explicitly wants the current output only as a draft, with detailed production information as a later expansion. Writing that into the design prevents scope creep in this change and clarifies the roadmap.

## Risks / Trade-offs

- **[Risk] Draft output may be mistaken for a factory-ready spec** → Mitigation: keep the schema explicitly labeled as draft-oriented and expose unresolved fields rather than silent blanks.
- **[Risk] Deterministic inference may feel too generic at first** → Mitigation: scope initial guidance to high-confidence fields and grow coverage only when evidence metadata is added.
- **[Risk] Embedding `factory_spec` into the success payload expands the result contract** → Mitigation: document the change in the modified `dress-concept-generation` spec and cover it with regression fixtures.
- **[Risk] Future richer metadata may require schema evolution** → Mitigation: version the draft schema from the start and isolate richer production metadata behind future follow-up changes.
