## ADDED Requirements

### Requirement: Successful concept result validation for image rendering
The system SHALL accept image-render requests only from successful `dress` concept result payloads that contain a valid `prompt_bundle`.

#### Scenario: Accept a successful `dress` concept result
- **WHEN** the workflow receives a successful `dress` concept result JSON with `request_normalized`, `composed_concept`, and `prompt_bundle`
- **THEN** it proceeds to build an image-render request from that saved result

#### Scenario: Reject unsupported render sources
- **WHEN** the workflow receives an error payload, a non-`dress` result, or a result that does not contain a valid `prompt_bundle`
- **THEN** it returns a structured error and does not call the image provider

### Requirement: Provider-backed image render dispatch
The system SHALL build an image-generation request from the saved concept result and dispatch it through the configured image-provider adapter.

#### Scenario: Render mode A concept imagery
- **WHEN** the saved concept result uses mode `A`
- **THEN** the provider request uses the saved mode `A` prompt content and preserves the concept-imagery intent recorded in the source result

#### Scenario: Render mode B development imagery
- **WHEN** the saved concept result uses mode `B`
- **THEN** the provider request uses the saved mode `B` prompt content and preserves the development-reference intent recorded in the source result

### Requirement: Deterministic output artifact bundle
The system SHALL write a deterministic local artifact bundle for each successful image render.

#### Scenario: Write image and report artifacts on success
- **WHEN** the provider returns a successful image render result
- **THEN** the workflow writes the rendered image artifact plus a machine-readable render report into the caller-specified output location

#### Scenario: Preserve render provenance in the report
- **WHEN** a render succeeds
- **THEN** the render report records the source concept-result reference, prompt fingerprint, provider identity, provider response metadata, and final output paths

### Requirement: Fail-closed render output behavior
The system SHALL leave no partial final artifact bundle behind when provider dispatch or output publication fails.

#### Scenario: Provider failure prevents artifact publication
- **WHEN** the provider returns an error or the provider adapter cannot complete the request
- **THEN** the workflow returns a structured error and writes no final image or render report artifacts

#### Scenario: Output write failure rolls back staged artifacts
- **WHEN** the provider succeeds but final artifact publication fails
- **THEN** the workflow returns a structured error and leaves no partial final artifact bundle in the target output location

### Requirement: Dedicated image-generation CLI
The system SHALL provide a dedicated CLI for rendering images from saved successful concept results.

#### Scenario: CLI renders from a saved concept result
- **WHEN** an operator runs the image-generation CLI with a valid successful concept result path and output location
- **THEN** the CLI writes the render artifacts, prints the render report JSON, and exits successfully

#### Scenario: CLI surfaces structured render failures
- **WHEN** validation, provider configuration, provider dispatch, or output publication fails during CLI execution
- **THEN** the CLI prints a structured error payload and exits with a failure status
