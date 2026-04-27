# image-generation-output Specification

## Purpose
Define the stable contract for rendering reviewable image artifacts from successful `dress` concept results through a provider-backed, file-oriented output workflow.
## Requirements
### Requirement: Successful concept result validation for image rendering
The system SHALL accept image-render requests only from successful `dress` concept result payloads that contain a valid `prompt_bundle`.

#### Scenario: Accept a successful `dress` concept result
- **WHEN** the workflow receives a successful `dress` concept result JSON with `request_normalized`, `composed_concept`, and `prompt_bundle`
- **THEN** it proceeds to build an image-render request from that saved result

#### Scenario: Reject unsupported render sources
- **WHEN** the workflow receives an error payload, a non-`dress` result, or a result that does not contain a valid `prompt_bundle`
- **THEN** it returns a structured error and does not call the image provider

### Requirement: Provider-backed image render dispatch
The system SHALL build one or more image-generation requests from the saved concept result and dispatch each through the configured image-provider adapter.

#### Scenario: Render a six-image bundle from canonical render jobs
- **WHEN** the saved concept result contains `prompt_bundle.render_jobs`
- **THEN** the workflow dispatches one provider render request per render job
- **AND** each request preserves the saved prompt content and associated prompt ID for that job

#### Scenario: Fall back to legacy single-image rendering
- **WHEN** the saved concept result does not contain `prompt_bundle.render_jobs` but still contains a valid legacy `prompt_bundle.prompt`
- **THEN** the workflow renders one image from the legacy prompt instead of failing

### Requirement: Deterministic output artifact bundle
The system SHALL write a deterministic local artifact bundle for each successful image render.

#### Scenario: Write the six-image bundle and report artifacts on success
- **WHEN** the provider returns successful render results for a saved concept result with canonical render jobs
- **THEN** the workflow writes one image artifact per render job using the saved stable output names
- **AND** it writes one machine-readable render report into the caller-specified output location

#### Scenario: Preserve per-image render provenance in the report
- **WHEN** a bundle render succeeds
- **THEN** the render report records the source concept-result reference, provider identity, provider response metadata, and final output path for each rendered image entry

### Requirement: Fail-closed render output behavior
The system SHALL leave no partial final artifact bundle behind when provider dispatch or output publication fails.

#### Scenario: Provider failure prevents artifact publication
- **WHEN** any provider render request in the bundle returns an error or the provider adapter cannot complete the request
- **THEN** the workflow returns a structured error and writes no final image or render report artifacts for that bundle

#### Scenario: Output write failure rolls back staged artifacts
- **WHEN** bundle rendering succeeds but final artifact publication fails
- **THEN** the workflow returns a structured error and leaves no partial final artifact bundle in the target output location

### Requirement: Dedicated image-generation CLI
The system SHALL provide a dedicated CLI for rendering images from saved successful concept results.

#### Scenario: CLI renders from a saved concept result
- **WHEN** an operator runs the image-generation CLI with a valid successful concept result path and output location
- **THEN** the CLI writes the render artifacts, prints the render report JSON, and exits successfully

#### Scenario: CLI surfaces structured render failures
- **WHEN** validation, provider configuration, provider dispatch, or output publication fails during CLI execution
- **THEN** the CLI prints a structured error payload and exits with a failure status

### Requirement: One-shot generate-and-render CLI
The system SHALL provide a dedicated CLI that reads a `dress` request JSON, persists a successful concept result as `concept_result.json`, and renders image artifacts from that persisted result in one command.

#### Scenario: One-shot CLI writes the persisted concept result and six-image bundle
- **WHEN** an operator runs the one-shot CLI with a valid `dress` request JSON, an output directory, and a valid image provider configuration for a result that uses canonical render jobs
- **THEN** the workflow writes `concept_result.json`, six named image artifacts, and `image_render_report.json`
- **AND** the CLI prints the final render report JSON and exits successfully

#### Scenario: Generation failure stops before any output is written
- **WHEN** concept generation returns a structured error for the request input
- **THEN** the one-shot workflow returns that structured error
- **AND** it writes no local output artifacts

#### Scenario: Concept-result write failure stops before provider setup
- **WHEN** concept generation succeeds but writing `concept_result.json` fails
- **THEN** the one-shot workflow returns a structured concept-result-output error
- **AND** it does not enter provider configuration, provider dispatch, or render output publication
- **AND** it leaves no local output artifacts

#### Scenario: Invalid request input is rejected before generation
- **WHEN** the one-shot workflow cannot read the request file, the JSON is invalid, or the request root is not an object
- **THEN** it returns a structured invalid-input error
- **AND** it writes no local output artifacts

#### Scenario: Render-stage failure preserves the persisted concept result
- **WHEN** concept generation succeeds and `concept_result.json` is written, but provider configuration, provider dispatch, or render output publication fails afterward
- **THEN** the workflow returns a structured render-stage error
- **AND** it keeps the successful `concept_result.json`
- **AND** it leaves no partial final render bundle behind

#### Scenario: One-shot CLI reuses the existing render CLI provider option contract
- **WHEN** an operator runs the one-shot CLI with provider configuration options supported by the existing saved-result render CLI
- **THEN** the one-shot CLI accepts the same provider configuration surface for image provider selection and configuration
- **AND** it preserves the existing provider parameter semantics without introducing conflicting meanings for those options

