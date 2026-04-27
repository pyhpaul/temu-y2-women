## ADDED Requirements

### Requirement: One-shot generate-and-render CLI
The system SHALL provide a dedicated CLI that reads a `dress` request JSON, persists a successful concept result as `concept_result.json`, and renders image artifacts from that persisted result in one command.

#### Scenario: One-shot CLI writes the persisted concept result and render artifacts
- **WHEN** an operator runs the one-shot CLI with a valid `dress` request JSON, an output directory, and a valid image provider configuration
- **THEN** the workflow writes `concept_result.json`, `rendered_image.png`, and `image_render_report.json`
- **AND** the CLI prints the final render report JSON and exits successfully

#### Scenario: Generation failure stops before any output is written
- **WHEN** concept generation returns a structured error for the request input
- **THEN** the one-shot workflow returns that structured error
- **AND** it writes no local output artifacts

#### Scenario: Invalid request input is rejected before generation
- **WHEN** the one-shot workflow cannot read the request file, the JSON is invalid, or the request root is not an object
- **THEN** it returns a structured invalid-input error
- **AND** it writes no local output artifacts

#### Scenario: Render-stage failure preserves the persisted concept result
- **WHEN** concept generation succeeds and `concept_result.json` is written, but provider configuration, provider dispatch, or render output publication fails afterward
- **THEN** the workflow returns a structured render-stage error
- **AND** it keeps the successful `concept_result.json`
- **AND** it leaves no partial final render bundle behind
