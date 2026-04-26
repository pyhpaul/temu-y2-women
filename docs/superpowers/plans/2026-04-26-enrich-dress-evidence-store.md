# Enrich Dress Evidence Store Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand and harden the local `dress` evidence store so `dress-concept-generation` remains API-stable but behaves more consistently across a broader set of curated requests.

**Architecture:** Keep the existing orchestration and result contract unchanged. Add a file-backed taxonomy document, validate elements and strategies against that taxonomy in `temu_y2_women/evidence_repository.py`, enrich the local JSON evidence files, and broaden deterministic regression coverage with both successful request fixtures and invalid-store fixtures.

**Tech Stack:** Python standard library, JSON evidence files, `unittest`, OpenSpec

---

### Task 1: Add taxonomy-driven evidence validation

**Files:**
- Create: `data/mvp/dress/evidence_taxonomy.json`
- Modify: `temu_y2_women/evidence_repository.py`
- Test: `tests/test_evidence_repository.py`

- [ ] **Step 1: Write the failing validation tests**

```python
def test_reject_unknown_element_tag(self) -> None:
    from temu_y2_women.errors import GenerationError
    from temu_y2_women.evidence_repository import load_elements

    with TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        (temp_root / "evidence_taxonomy.json").write_text(
            json.dumps(
                {
                    "allowed_slots": ["silhouette", "fabric"],
                    "allowed_tags": ["summer", "casual"],
                    "allowed_occasions": ["casual"],
                    "allowed_seasons": ["summer"],
                    "allowed_risk_flags": ["fit_sensitivity"],
                    "summary": {"min_length": 20, "max_length": 140},
                    "base_score": {"min": 0.0, "max": 1.0},
                }
            ),
            encoding="utf-8",
        )
        elements_path = temp_root / "elements.json"
        elements_path.write_text(
            json.dumps(
                {
                    "schema_version": "mvp-v1",
                    "elements": [
                        {
                            "element_id": "dress-silhouette-a-line-001",
                            "category": "dress",
                            "slot": "silhouette",
                            "value": "a-line",
                            "tags": ["unknown-tag"],
                            "base_score": 0.8,
                            "price_bands": ["mid"],
                            "occasion_tags": ["casual"],
                            "season_tags": ["summer"],
                            "risk_flags": [],
                            "evidence_summary": "Commercial summer silhouette with clear casual demand.",
                            "status": "active",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        with self.assertRaises(GenerationError) as error_context:
            load_elements(elements_path, taxonomy_path=temp_root / "evidence_taxonomy.json")

    self.assertEqual(error_context.exception.code, "INVALID_EVIDENCE_STORE")

def test_reject_duplicate_active_slot_value(self) -> None:
    from temu_y2_women.errors import GenerationError
    from temu_y2_women.evidence_repository import load_elements

    with TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        (temp_root / "evidence_taxonomy.json").write_text(
            json.dumps(
                {
                    "allowed_slots": ["silhouette", "fabric"],
                    "allowed_tags": ["summer", "casual", "feminine"],
                    "allowed_occasions": ["casual"],
                    "allowed_seasons": ["summer"],
                    "allowed_risk_flags": ["fit_sensitivity"],
                    "summary": {"min_length": 20, "max_length": 140},
                    "base_score": {"min": 0.0, "max": 1.0},
                }
            ),
            encoding="utf-8",
        )
        elements_path = temp_root / "elements.json"
        elements_path.write_text(
            json.dumps(
                {
                    "schema_version": "mvp-v1",
                    "elements": [
                        {
                            "element_id": "dress-silhouette-a-line-001",
                            "category": "dress",
                            "slot": "silhouette",
                            "value": "a-line",
                            "tags": ["summer", "feminine"],
                            "base_score": 0.82,
                            "price_bands": ["mid"],
                            "occasion_tags": ["casual"],
                            "season_tags": ["summer"],
                            "risk_flags": [],
                            "evidence_summary": "Baseline commercial silhouette with clear summer appeal.",
                            "status": "active",
                        },
                        {
                            "element_id": "dress-silhouette-a-line-002",
                            "category": "dress",
                            "slot": "silhouette",
                            "value": "a-line",
                            "tags": ["summer", "casual"],
                            "base_score": 0.79,
                            "price_bands": ["mid"],
                            "occasion_tags": ["casual"],
                            "season_tags": ["summer"],
                            "risk_flags": [],
                            "evidence_summary": "Duplicate active value used to prove conflict detection.",
                            "status": "active",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        with self.assertRaises(GenerationError) as error_context:
            load_elements(elements_path, taxonomy_path=temp_root / "evidence_taxonomy.json")

    self.assertEqual(error_context.exception.code, "INVALID_EVIDENCE_STORE")

def test_reject_unknown_strategy_slot_preference(self) -> None:
    from temu_y2_women.errors import GenerationError
    from temu_y2_women.evidence_repository import load_strategy_templates

    with TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        (temp_root / "evidence_taxonomy.json").write_text(
            json.dumps(
                {
                    "allowed_slots": ["silhouette", "fabric"],
                    "allowed_tags": ["summer", "casual", "feminine"],
                    "allowed_occasions": ["casual"],
                    "allowed_seasons": ["summer"],
                    "allowed_risk_flags": ["fit_sensitivity"],
                    "summary": {"min_length": 20, "max_length": 140},
                    "base_score": {"min": 0.0, "max": 1.0},
                }
            ),
            encoding="utf-8",
        )
        (temp_root / "elements.json").write_text(
            json.dumps(
                {
                    "schema_version": "mvp-v1",
                    "elements": [
                        {
                            "element_id": "dress-silhouette-a-line-001",
                            "category": "dress",
                            "slot": "silhouette",
                            "value": "a-line",
                            "tags": ["summer", "feminine"],
                            "base_score": 0.82,
                            "price_bands": ["mid"],
                            "occasion_tags": ["casual"],
                            "season_tags": ["summer"],
                            "risk_flags": [],
                            "evidence_summary": "Known silhouette used to validate strategy references.",
                            "status": "active",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        strategies_path = temp_root / "strategy_templates.json"
        strategies_path.write_text(
            json.dumps(
                {
                    "schema_version": "mvp-v1",
                    "strategy_templates": [
                        {
                            "strategy_id": "dress-us-baseline",
                            "category": "dress",
                            "target_market": "US",
                            "priority": 1,
                            "date_window": {"start": "01-01", "end": "12-31"},
                            "occasion_tags": [],
                            "boost_tags": ["summer"],
                            "suppress_tags": [],
                            "slot_preferences": {"silhouette": ["unknown-shape"]},
                            "score_boost": 0.03,
                            "score_cap": 0.08,
                            "prompt_hints": ["baseline"],
                            "reason_template": "baseline",
                            "status": "active",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        with self.assertRaises(GenerationError) as error_context:
            load_strategy_templates(
                strategies_path,
                taxonomy_path=temp_root / "evidence_taxonomy.json",
                elements_path=temp_root / "elements.json",
            )

    self.assertEqual(error_context.exception.code, "INVALID_EVIDENCE_STORE")
```

- [ ] **Step 2: Run the targeted evidence validation tests and verify they fail**

Run: `python -m unittest tests.test_evidence_repository.EvidenceRepositoryValidationTest -v`
Expected: FAIL because `load_elements()` and `load_strategy_templates()` do not yet load or enforce taxonomy rules.

- [ ] **Step 3: Implement taxonomy loading and fail-fast validation**

```python
_DEFAULT_TAXONOMY_PATH = Path("data/mvp/dress/evidence_taxonomy.json")

def load_evidence_taxonomy(path: Path = _DEFAULT_TAXONOMY_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    required_fields = {
        "allowed_slots",
        "allowed_tags",
        "allowed_occasions",
        "allowed_seasons",
        "allowed_risk_flags",
        "summary",
        "base_score",
    }
    missing = sorted(required_fields.difference(payload.keys()))
    if missing:
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message="evidence taxonomy is missing required fields",
            details={"path": str(path), "missing": missing},
        )
    return payload


def load_elements(
    path: Path = _DEFAULT_ELEMENTS_PATH,
    taxonomy_path: Path = _DEFAULT_TAXONOMY_PATH,
) -> list[dict[str, Any]]:
    taxonomy = load_evidence_taxonomy(taxonomy_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    elements = payload.get("elements")
    seen_ids: set[str] = set()
    seen_slot_values: set[tuple[str, str]] = set()
    for index, element in enumerate(elements):
        _validate_element_record(path=path, taxonomy=taxonomy, index=index, element=element)
        if element["status"] != "active":
            continue
        element_id = str(element["element_id"])
        slot_value = (str(element["slot"]), str(element["value"]))
        if element_id in seen_ids or slot_value in seen_slot_values:
            raise GenerationError(
                code="INVALID_EVIDENCE_STORE",
                message="active element duplicates an existing canonical record",
                details={"path": str(path), "index": index, "element_id": element_id, "slot_value": slot_value},
            )
        seen_ids.add(element_id)
        seen_slot_values.add(slot_value)
    return list(elements)


def load_strategy_templates(
    path: Path = _DEFAULT_STRATEGIES_PATH,
    taxonomy_path: Path = _DEFAULT_TAXONOMY_PATH,
    elements_path: Path = _DEFAULT_ELEMENTS_PATH,
) -> list[dict[str, Any]]:
    taxonomy = load_evidence_taxonomy(taxonomy_path)
    elements = load_elements(elements_path, taxonomy_path=taxonomy_path)
    known_values_by_slot = {
        str(element["slot"]): {
            str(item["value"])
            for item in elements
            if item["status"] == "active" and item["slot"] == element["slot"]
        }
        for element in elements
    }
    payload = json.loads(path.read_text(encoding="utf-8"))
    strategies = payload.get("strategy_templates")
    for index, strategy in enumerate(strategies):
        _validate_strategy_record(
            path=path,
            index=index,
            strategy=strategy,
            taxonomy=taxonomy,
            known_values_by_slot=known_values_by_slot,
        )
    return list(strategies)
```

- [ ] **Step 4: Re-run the targeted evidence validation tests and verify they pass**

Run: `python -m unittest tests.test_evidence_repository.EvidenceRepositoryValidationTest -v`
Expected: PASS with the new `INVALID_EVIDENCE_STORE` validation cases covered.

- [ ] **Step 5: Commit**

```bash
git add data/mvp/dress/evidence_taxonomy.json temu_y2_women/evidence_repository.py tests/test_evidence_repository.py
git commit -m "fix(evidence): add taxonomy-driven validation"
```

### Task 2: Enrich curated dress data for broader stable coverage

**Files:**
- Modify: `data/mvp/dress/elements.json`
- Modify: `data/mvp/dress/strategy_templates.json`
- Create: `tests/fixtures/requests/dress-generation-mvp/success-baseline-transitional-mode-a.json`
- Test: `tests/test_orchestrator.py`

- [ ] **Step 1: Add the failing baseline success regression**

```python
def test_successful_baseline_mode_a_flow(self) -> None:
    from temu_y2_women.orchestrator import generate_dress_concept

    result = generate_dress_concept(_read_request("success-baseline-transitional-mode-a.json"))

    self.assertEqual(result["request_normalized"]["mode"], "A")
    self.assertEqual(result["selected_strategies"][0]["strategy_id"], "dress-us-baseline")
    self.assertEqual(result["prompt_bundle"]["mode"], "A")
    self.assertEqual(result["composed_concept"]["selected_elements"]["neckline"]["value"], "v-neckline")
    self.assertIn("must_have_tags satisfied: transitional", result["composed_concept"]["constraint_notes"])
```

`success-baseline-transitional-mode-a.json`

```json
{
  "category": "dress",
  "target_market": "US",
  "target_launch_date": "2026-10-10",
  "mode": "A",
  "price_band": "mid",
  "occasion_tags": ["casual"],
  "must_have_tags": ["transitional"],
  "avoid_tags": ["bodycon"]
}
```

- [ ] **Step 2: Run the baseline orchestrator regression and verify it fails**

Run: `python -m unittest tests.test_orchestrator.OrchestratorTest.test_successful_baseline_mode_a_flow -v`
Expected: FAIL because the current evidence store does not yet contain an active element that can satisfy the `transitional` must-have tag.

- [ ] **Step 3: Expand the curated JSON evidence files**

`data/mvp/dress/elements.json`

```json
{
  "element_id": "dress-neckline-v-neck-001",
  "category": "dress",
  "slot": "neckline",
  "value": "v-neckline",
  "tags": ["feminine", "casual", "transitional"],
  "base_score": 0.74,
  "price_bands": ["mid"],
  "occasion_tags": ["casual"],
  "season_tags": ["spring", "fall"],
  "risk_flags": [],
  "evidence_summary": "Reliable neckline direction for baseline casual dresses with broad US appeal.",
  "status": "active"
}
```

`data/mvp/dress/strategy_templates.json`

```json
{
  "strategy_id": "dress-us-baseline",
  "category": "dress",
  "target_market": "US",
  "priority": 1,
  "date_window": {"start": "01-01", "end": "12-31"},
  "occasion_tags": [],
  "boost_tags": ["dress", "feminine", "casual", "transitional"],
  "suppress_tags": ["holiday", "heavy"],
  "slot_preferences": {
    "silhouette": ["a-line"],
    "fabric": ["cotton poplin"],
    "neckline": ["square neckline", "v-neckline"]
  },
  "score_boost": 0.03,
  "score_cap": 0.08,
  "prompt_hints": ["US ecommerce-ready dress concept"],
  "reason_template": "baseline US dress strategy used when no narrower seasonal strategy outranks it",
  "status": "active"
}
```

- [ ] **Step 4: Re-run the focused orchestrator regression and verify it passes**

Run: `python -m unittest tests.test_orchestrator.OrchestratorTest.test_successful_baseline_mode_a_flow -v`
Expected: PASS with `dress-us-baseline` selected and a complete concept returned.

- [ ] **Step 5: Commit**

```bash
git add data/mvp/dress/elements.json data/mvp/dress/strategy_templates.json tests/fixtures/requests/dress-generation-mvp/success-baseline-transitional-mode-a.json tests/test_orchestrator.py
git commit -m "feat(evidence): enrich curated dress coverage"
```

### Task 3: Add invalid-store fixtures and full regression coverage

**Files:**
- Create: `tests/fixtures/evidence/dress/invalid-unknown-tag-elements.json`
- Create: `tests/fixtures/evidence/dress/invalid-duplicate-elements.json`
- Create: `tests/fixtures/evidence/dress/invalid-strategy-slot-preference.json`
- Modify: `tests/test_evidence_repository.py`

- [ ] **Step 1: Add the failing invalid-store regression tests**

```python
def test_reject_invalid_unknown_tag_fixture(self) -> None:
    from temu_y2_women.errors import GenerationError
    from temu_y2_women.evidence_repository import load_elements

    fixture_path = Path("tests/fixtures/evidence/dress/invalid-unknown-tag-elements.json")
    taxonomy_path = Path("data/mvp/dress/evidence_taxonomy.json")

    with self.assertRaises(GenerationError) as error_context:
        load_elements(fixture_path, taxonomy_path=taxonomy_path)

    self.assertEqual(error_context.exception.code, "INVALID_EVIDENCE_STORE")


def test_reject_invalid_strategy_slot_preference_fixture(self) -> None:
    from temu_y2_women.errors import GenerationError
    from temu_y2_women.evidence_repository import load_strategy_templates

    fixture_path = Path("tests/fixtures/evidence/dress/invalid-strategy-slot-preference.json")
    taxonomy_path = Path("data/mvp/dress/evidence_taxonomy.json")
    elements_path = Path("data/mvp/dress/elements.json")

    with self.assertRaises(GenerationError) as error_context:
        load_strategy_templates(
            fixture_path,
            taxonomy_path=taxonomy_path,
            elements_path=elements_path,
        )

    self.assertEqual(error_context.exception.code, "INVALID_EVIDENCE_STORE")
```

- [ ] **Step 2: Run the new invalid-store tests and verify they fail**

Run: `python -m unittest tests.test_evidence_repository.EvidenceRepositoryValidationTest -v`
Expected: FAIL until the fixture files exist and the invalid-store path is fully asserted.

- [ ] **Step 3: Add invalid fixtures and finish the assertions**

`tests/fixtures/evidence/dress/invalid-unknown-tag-elements.json`

```json
{
  "schema_version": "mvp-v1",
  "elements": [
    {
      "element_id": "dress-pattern-broken-001",
      "category": "dress",
      "slot": "pattern",
      "value": "broken pattern",
      "tags": ["unknown-tag"],
      "base_score": 0.6,
      "price_bands": ["mid"],
      "occasion_tags": ["casual"],
      "season_tags": ["summer"],
      "risk_flags": [],
      "evidence_summary": "Fixture used to prove taxonomy validation rejects unsupported tags.",
      "status": "active"
    }
  ]
}
```

`tests/fixtures/evidence/dress/invalid-duplicate-elements.json`

```json
{
  "schema_version": "mvp-v1",
  "elements": [
    {
      "element_id": "dress-silhouette-a-line-001",
      "category": "dress",
      "slot": "silhouette",
      "value": "a-line",
      "tags": ["summer", "feminine"],
      "base_score": 0.82,
      "price_bands": ["mid"],
      "occasion_tags": ["casual"],
      "season_tags": ["summer"],
      "risk_flags": [],
      "evidence_summary": "Fixture record one.",
      "status": "active"
    },
    {
      "element_id": "dress-silhouette-a-line-002",
      "category": "dress",
      "slot": "silhouette",
      "value": "a-line",
      "tags": ["summer", "casual"],
      "base_score": 0.79,
      "price_bands": ["mid"],
      "occasion_tags": ["casual"],
      "season_tags": ["summer"],
      "risk_flags": [],
      "evidence_summary": "Fixture record two with duplicate active slot and value.",
      "status": "active"
    }
  ]
}
```

`tests/fixtures/evidence/dress/invalid-strategy-slot-preference.json`

```json
{
  "schema_version": "mvp-v1",
  "strategy_templates": [
    {
      "strategy_id": "dress-us-baseline",
      "category": "dress",
      "target_market": "US",
      "priority": 1,
      "date_window": {"start": "01-01", "end": "12-31"},
      "occasion_tags": [],
      "boost_tags": ["dress"],
      "suppress_tags": [],
      "slot_preferences": {"neckline": ["unknown-neckline"]},
      "score_boost": 0.03,
      "score_cap": 0.08,
      "prompt_hints": ["Fixture to reject unknown strategy references."],
      "reason_template": "broken fixture",
      "status": "active"
    }
  ]
}
```

- [ ] **Step 4: Run the full regression suite and OpenSpec validation**

Run: `python -m unittest discover -s tests -t .`
Expected: PASS

Run: `openspec validate enrich-dress-evidence-store`
Expected: `Change 'enrich-dress-evidence-store' is valid`

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/evidence/dress tests/test_evidence_repository.py
git commit -m "test(evidence): add invalid-store regression coverage"
```
