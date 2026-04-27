## 1. Factory-spec draft schema and packaging

- [x] 1.1 Add a deterministic `factory_spec` draft builder for successful `dress` concept results
- [x] 1.2 Extend successful result packaging so `factory_spec` is included alongside `prompt_bundle`
- [x] 1.3 Add fixtures that cover the expected draft schema with `known`, `inferred`, and `unresolved` sections

## 2. Deterministic draft guidance rules

- [x] 2.1 Map selected concept elements into `factory_spec.known` without fabricating unsupported production metadata
- [x] 2.2 Add deterministic production-review guidance rules for `fabric`, `detail`, fit-intent, and visible construction priorities under `factory_spec.inferred`
- [x] 2.3 Add an explicit unresolved-field list for future production metadata such as fiber content, GSM, lining, closure details, measurements, tolerances, and BOM-grade trim data

## 3. Validation and roadmap preservation

- [x] 3.1 Add regression tests for successful factory-spec draft generation and unchanged structured error behavior
- [x] 3.2 Verify concept-generation CLI and persisted result flows include the draft `factory_spec` output
- [x] 3.3 Preserve the follow-up expansion direction for detailed production metadata in project docs and OpenSpec artifacts without promoting unsupported numeric values into the draft output
