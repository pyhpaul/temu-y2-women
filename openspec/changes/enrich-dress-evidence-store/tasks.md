## 1. Taxonomy and curated evidence data

- [ ] 1.1 Add `data/mvp/dress/evidence_taxonomy.json` with the supported `slot`, `tag`, `season`, `occasion`, and `risk` dictionaries plus authoring guardrails
- [ ] 1.2 Expand `data/mvp/dress/elements.json` to a curated `dress` set with broader slot/value coverage and no duplicate or conflicting active records
- [ ] 1.3 Update `data/mvp/dress/strategy_templates.json` where needed so active strategy tags and slot preferences stay aligned with the taxonomy and enriched element set

## 2. Validation hardening in the runtime

- [ ] 2.1 Load the taxonomy alongside elements and strategies in `temu_y2_women/evidence_repository.py`
- [ ] 2.2 Enforce dictionary membership, unique active records, score bounds, `evidence_summary` authoring rules, and strategy-reference validation with `INVALID_EVIDENCE_STORE`
- [ ] 2.3 Keep candidate retrieval and downstream result contracts unchanged while switching generation to validated curated records

## 3. Regression and invalid-store coverage

- [ ] 3.1 Add request fixtures for multiple successful `dress` archetypes that rely on the enriched evidence store
- [ ] 3.2 Add invalid evidence-store fixtures for unsupported dictionary values, duplicate/conflicting records, and authoring-quality failures
- [ ] 3.3 Expand automated tests to cover enriched-store validation plus stable retrieval and composition behavior across the request matrix
