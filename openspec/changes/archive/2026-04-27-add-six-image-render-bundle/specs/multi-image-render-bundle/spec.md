## ADDED Requirements

### Requirement: Successful concept results include a deterministic six-image render job set
The system SHALL attach a deterministic six-job render bundle to every successful `dress` concept result that uses the current multi-image prompt contract.

#### Scenario: Emit the fixed hero and detail job set
- **WHEN** a `dress` concept generation flow succeeds
- **THEN** the result includes `prompt_bundle.render_jobs`
- **AND** the job set contains `hero_front`, `hero_three_quarter`, `hero_back`, `construction_closeup`, `fabric_print_closeup`, and `hem_and_drape_closeup`

### Requirement: Render jobs preserve stable classification and output naming
The system SHALL label each render job with stable metadata so downstream render workflows can publish a predictable asset bundle.

#### Scenario: Render jobs expose group and output names
- **WHEN** a successful concept result includes `prompt_bundle.render_jobs`
- **THEN** each job records a stable `prompt_id`, `group`, `output_name`, and non-empty `prompt`
- **AND** hero jobs and detail jobs remain distinguishable without inferring that from the file name alone
