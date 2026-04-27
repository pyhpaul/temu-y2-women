## Context

The repository already has a stable offline chain for `dress` request normalization, evidence-backed retrieval, structured composition, prompt rendering, promotion, feedback apply, and isolated feedback experiments. What is still missing is the last user-visible step in the original V2 flow: turning a successful concept result into an actual image artifact.

That missing step changes the engineering profile of the system. Unlike the existing workflows, image rendering depends on an external provider, non-deterministic model output, credentials, and binary artifact handling. The design therefore needs to protect the deterministic core from provider volatility while still letting operators run a real render path from the repository.

## Goals / Non-Goals

**Goals:**
- Add a dedicated downstream workflow that renders image artifacts from a saved successful `dress` concept result.
- Keep `generate_dress_concept()` and the existing result contract stable so generation logic remains deterministic and testable without network access.
- Introduce a provider interface with one real provider implementation and one fake test path.
- Write deterministic output metadata and fail-closed output files for provider success and failure cases.
- Provide a dedicated CLI that operators can run against saved result JSON files.

**Non-Goals:**
- Reworking the existing `cli.py` into a network-dependent end-to-end command.
- Building batch queues, browser galleries, or experiment visualization for rendered images.
- Adding image-level feedback scoring, strategy feedback, or auto-promotion based on image quality.
- Supporting multiple production providers in the first slice beyond one real provider plus the testing fake.

## Decisions

### 1. Keep image rendering as a downstream workflow, not part of core concept generation

The new workflow should consume a saved successful concept result JSON instead of modifying `generate_dress_concept()` to call an image provider inline.

Why:
- preserves the stable deterministic generation contract
- keeps provider credentials and network behavior out of the core orchestration path
- matches the repository's existing pattern of file-backed downstream workflows such as promotion, feedback apply, and experiments

Alternatives considered:
- **Call the provider directly inside `generate_dress_concept()`**: rejected because it mixes deterministic generation with external network effects and would make core tests brittle.
- **Extend `cli.py` to always generate images after prompt rendering**: rejected because it would turn the current local generation CLI into a provider-coupled command and remove the ability to save/replay successful concept results separately.

### 2. Introduce a provider adapter boundary with a fake test implementation and one real provider

The workflow should build a normalized render request from the concept result and pass it to a provider adapter that returns binary image data plus provider metadata. Tests should use a fake provider that returns stable bytes and metadata without network access.

Why:
- isolates provider-specific request and response handling
- lets the repository regression suite stay offline
- makes later provider replacement or expansion possible without changing the workflow contract

Alternatives considered:
- **Embed provider HTTP calls directly in the CLI**: rejected because it would make validation, failure handling, and testing much harder to isolate.
- **Mock the network layer only**: rejected because the workflow still needs a stable internal contract for provider results and binary outputs.

### 3. Write a deterministic artifact bundle on success

Successful renders should produce a caller-specified output directory containing the rendered image file and a machine-readable render report that records source-result provenance, prompt fingerprint, provider name, model/config metadata, and output paths.

Why:
- gives operators a replayable and reviewable artifact set
- captures the non-deterministic provider call in a deterministic local report
- keeps binary outputs and structured metadata together for later comparison or audit

Alternatives considered:
- **Return only base64 in stdout**: rejected because it is hard to review, diff, and persist safely.
- **Write only the image file with no report**: rejected because provider parameters, prompt provenance, and failure debugging would be lost.

### 4. Fail closed on provider and output-write errors

The workflow should validate the input result before provider dispatch and use staged writes for final artifacts so failed runs do not leave a partial image/report bundle behind.

Why:
- matches the repository's existing all-or-nothing write posture
- keeps failed provider or filesystem runs easy to reason about
- prevents stale images from being mistaken for a successful render

Alternatives considered:
- **Best-effort writes with partial outputs**: rejected because partial artifact directories are ambiguous and operationally noisy.

### 5. Keep the first slice single-image and CLI-first

The first change should render one primary image per successful concept result and expose that through a dedicated CLI module.

Why:
- keeps scope aligned with the repository's existing file-backed MVP pattern
- minimizes provider cost and orchestration complexity in the first real rendering slice
- gets to visible end-user output faster than introducing batch or multi-variant generation now

Alternatives considered:
- **Generate multiple variants per request**: rejected because it expands selection, ranking, and artifact management before the single-image path is proven.
- **Add browser UI first**: rejected because the main gap is missing render capability, not missing presentation of existing render outputs.

## Risks / Trade-offs

- **[Risk] Provider output is non-deterministic even when the prompt is fixed** -> Mitigation: keep deterministic regression assertions on request shaping, metadata, and file outputs, not on pixel-perfect image content.
- **[Risk] Provider API failures or credential issues could look like workflow bugs** -> Mitigation: validate provider config explicitly, isolate provider exceptions behind structured workflow errors, and keep fake-provider tests offline.
- **[Risk] Binary output handling can leave confusing partial artifacts** -> Mitigation: stage final artifact writes and only publish the image/report pair together on success.
- **[Risk] A downstream render-only CLI adds one more operator step after generation** -> Mitigation: keep the input contract simple (`successful concept result JSON`) and defer one-shot generate-and-render orchestration until the rendering slice proves stable.

## Migration Plan

No data migration is required. This change only adds downstream rendering modules, a new CLI, and a new capability spec. Rollback is straightforward: remove the image-rendering workflow and CLI without changing existing generation, promotion, feedback, or experiment data.

## Open Questions

- Which concrete provider configuration surface should be exposed in the CLI for the first production adapter: strictly environment-driven defaults, or environment plus a small set of explicit override flags?
- Should the first image artifact filename be fixed (for example `rendered_image.png`) or derived from provider-returned format metadata when multiple output formats are possible?
