# Evidence-Backed Compatibility Rules Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade curated `dress` compatibility rules from hand-authored weak/strong pairs into a review-gated, evidence-backed rule system without breaking the existing runtime contract.

**Architecture:** Keep runtime concept generation stable by continuing to consume active compatibility rules from file-backed evidence, but expand the rule schema so each rule can carry scope, evidence, confidence, and provenance. Add a parallel staged-review-apply workflow for compatibility rules and a feedback-derived candidate generator that can propose draft conflict rules from reviewed concept feedback. Defer signal-derived candidates until the canonical signal contract from the evidence-refresh change is stable.

**Tech Stack:** Python standard library, JSON evidence files, `unittest`, OpenSpec-style staged artifacts, existing review-gated evidence patterns

---

## Recommended workspace layout

- Change worktree: `../temu-y2-women-conflict-rules`
- Branch: `codex/evidence-backed-compatibility-rules`
- Parallel ownership:
  - Worker A: schema/runtime
  - Worker B: rule review/promotion
  - Worker C: feedback-derived candidates

---

### Task 1: Add compatibility-rule schema v2 and runtime compatibility

**Files:**
- Modify: `temu_y2_women/compatibility_evaluator.py`
- Modify: `data/mvp/dress/compatibility_rules.json`
- Create: `tests/fixtures/evidence/dress/compatibility-rules-v2-valid.json`
- Create: `tests/fixtures/evidence/dress/compatibility-rules-v2-invalid-scope.json`
- Modify: `tests/test_compatibility_evaluator.py`

- [ ] **Step 1: Write failing tests for v2 rule loading and backward compatibility**

Add focused tests in `tests/test_compatibility_evaluator.py` that prove:

1. v1 rules still load unchanged.
2. v2 rules load with evidence metadata present.
3. invalid scope fields fail closed.
4. invalid confidence fields fail closed.
5. runtime evaluation still only uses `severity` and `penalty`.

Suggested test names:

```python
def test_loads_v2_compatibility_rules_with_evidence_metadata(self) -> None: ...
def test_rejects_v2_rule_with_invalid_scope_shape(self) -> None: ...
def test_rejects_v2_rule_with_invalid_confidence(self) -> None: ...
def test_v1_rule_shape_remains_supported(self) -> None: ...
```

- [ ] **Step 2: Add v2 fixture files**

Create `tests/fixtures/evidence/dress/compatibility-rules-v2-valid.json` with one active `pattern/detail` rule carrying:

```json
{
  "schema_version": "compatibility-rules-v2",
  "rules": [
    {
      "rule_id": "dress-pattern-floral-print__detail-smocked-bodice",
      "left_slot": "pattern",
      "left_value": "floral print",
      "right_slot": "detail",
      "right_value": "smocked bodice",
      "severity": "weak",
      "penalty": 0.08,
      "reason": "visual density rises when both are emphasized in the same dress direction",
      "scope": {
        "category": "dress",
        "target_market": "US",
        "season_tags": ["summer"],
        "occasion_tags": ["vacation"],
        "price_bands": ["mid"]
      },
      "evidence_summary": "Low-confidence curated starter rule promoted from reviewed style feedback.",
      "evidence": {
        "review_reject_rate": 0.61,
        "pair_presence_count": 9,
        "source_feedback_ids": ["fb-001", "fb-004"]
      },
      "confidence": 0.74,
      "decision_source": "reviewed_heuristic",
      "status": "active"
    }
  ]
}
```

Create `tests/fixtures/evidence/dress/compatibility-rules-v2-invalid-scope.json` with a malformed `scope` object such as numeric `season_tags`.

- [ ] **Step 3: Implement v2 parsing and validation**

In `temu_y2_women/compatibility_evaluator.py`:

1. Extend the rule model to carry optional metadata fields:
   - `rule_id`
   - `scope`
   - `evidence_summary`
   - `evidence`
   - `confidence`
   - `decision_source`
   - `status`
2. Keep `evaluate_selection_compatibility()` behavior unchanged for runtime scoring.
3. Validate:
   - `confidence` must be numeric and between `0.0` and `1.0`
   - `scope` must be an object when present
   - `season_tags`, `occasion_tags`, `price_bands` must be arrays of strings when present
   - `status` must still require active/inactive semantics compatible with current evidence patterns
4. Accept both:
   - `schema_version = "mvp-v1"` (legacy)
   - `schema_version = "compatibility-rules-v2"` (new)

Implementation constraint:
- Keep parse/validation helpers under 60 lines each.
- Do not let metadata fields affect current scoring semantics yet.

- [ ] **Step 4: Run targeted validation tests**

Run:

```bash
python -m unittest tests.test_compatibility_evaluator -v
```

Expected:
- PASS
- Existing weak/strong conflict tests still pass
- New v2 fixture tests pass

- [ ] **Step 5: Commit**

```bash
git add temu_y2_women/compatibility_evaluator.py data/mvp/dress/compatibility_rules.json tests/test_compatibility_evaluator.py tests/fixtures/evidence/dress/compatibility-rules-v2-valid.json tests/fixtures/evidence/dress/compatibility-rules-v2-invalid-scope.json
git commit -m "feat: add evidence-backed compatibility rule schema"
```

---

### Task 2: Add compatibility-rule review and promotion workflow

**Files:**
- Create: `temu_y2_women/compatibility_rule_promotion.py`
- Create: `temu_y2_women/compatibility_rule_promotion_cli.py`
- Create: `tests/fixtures/compatibility_rules/draft_conflict_rules_valid.json`
- Create: `tests/fixtures/compatibility_rules/reviewed_conflict_rules_valid.json`
- Create: `tests/fixtures/compatibility_rules/reviewed_conflict_rules_invalid.json`
- Create: `tests/test_compatibility_rule_promotion.py`

- [ ] **Step 1: Write failing workflow tests**

Add tests that cover:

```python
def test_prepare_rule_review_builds_expected_template(self) -> None: ...
def test_apply_reviewed_rule_promotion_writes_active_rules_and_report(self) -> None: ...
def test_invalid_review_fails_before_mutation(self) -> None: ...
def test_rejected_rule_is_excluded_from_active_output(self) -> None: ...
```

The tests should mirror the structure used by `temu_y2_women/evidence_promotion.py`:
- one prepare path
- one successful apply path
- one fail-before-mutation path
- one reject path

- [ ] **Step 2: Define staged and reviewed artifact shapes**

Use these file concepts:

- `draft_conflict_rules.json`
- `compatibility-rule-review-v1`
- `compatibility-rule-promotion-report-v1`

Each draft rule should include:
- stable source identifier
- proposed rule payload
- evidence summary
- evidence metrics
- severity suggestion
- penalty suggestion

Each reviewed rule should include:
- `decision: accept | reject`
- curated rule payload for accepts
- merge rationale

- [ ] **Step 3: Implement prepare / validate / apply**

In `temu_y2_women/compatibility_rule_promotion.py`, add:

1. `prepare_compatibility_rule_review(...)`
2. `validate_reviewed_compatibility_rule_promotion(...)`
3. `apply_reviewed_compatibility_rule_promotion(...)`

Behavior:
- load active compatibility rules
- load staged draft rules
- generate deterministic review template
- validate reviewed decisions fail closed
- write updated active rule file atomically
- write promotion report atomically

Follow the same design constraints already used elsewhere:
- all-or-nothing writes
- explicit structured errors
- helper functions under 60 lines

- [ ] **Step 4: Add CLI wrappers**

In `temu_y2_women/compatibility_rule_promotion_cli.py`, support:

```text
prepare --draft-rules --active-rules --output
apply --reviewed --draft-rules --active-rules --report-output
```

Print structured JSON and return non-zero on error, matching existing CLI conventions in the repo.

- [ ] **Step 5: Run targeted workflow tests**

Run:

```bash
python -m unittest tests.test_compatibility_rule_promotion -v
```

Expected:
- PASS
- invalid reviewed artifact test proves no partial mutation

- [ ] **Step 6: Commit**

```bash
git add temu_y2_women/compatibility_rule_promotion.py temu_y2_women/compatibility_rule_promotion_cli.py tests/test_compatibility_rule_promotion.py tests/fixtures/compatibility_rules
git commit -m "feat: add compatibility rule promotion workflow"
```

---

### Task 3: Add feedback-derived conflict candidate generation

**Files:**
- Create: `temu_y2_women/conflict_rule_feedback_deriver.py`
- Create: `temu_y2_women/conflict_rule_feedback_cli.py`
- Create: `tests/fixtures/compatibility_rules/feedback-ledger-sample.json`
- Create: `tests/fixtures/compatibility_rules/draft_conflict_rules_expected.json`
- Create: `tests/test_conflict_rule_feedback_deriver.py`

- [ ] **Step 1: Write failing derivation tests**

Add tests for:

```python
def test_generates_draft_conflict_rules_from_feedback_ledger(self) -> None: ...
def test_ignores_pairs_below_minimum_sample_threshold(self) -> None: ...
def test_maps_high_reject_rate_to_strong_suggestion(self) -> None: ...
def test_maps_moderate_reject_rate_to_weak_suggestion(self) -> None: ...
```

Use fixture data that references known active `pattern/detail` values from `data/mvp/dress/elements.json`.

- [ ] **Step 2: Define derivation heuristics**

For the first pass, keep the heuristic simple and explicit:

- minimum sample threshold: `pair_presence_count >= 3`
- if `reject_rate >= 0.75`: suggest `strong`, `penalty = 0.0`
- if `0.45 <= reject_rate < 0.75`: suggest `weak`, `penalty = 0.08`
- otherwise: no emitted draft rule

Include emitted evidence fields:
- `pair_presence_count`
- `keep_count`
- `reject_count`
- `reject_rate`
- `source_feedback_ids`

Keep the output deterministic by sorting on:
1. descending `reject_rate`
2. descending `pair_presence_count`
3. `rule_id`

- [ ] **Step 3: Implement derivation module**

In `temu_y2_women/conflict_rule_feedback_deriver.py`:

1. load ledger input
2. group feedback by selected `pattern/detail` pair
3. aggregate keep/reject counts
4. build draft rule candidates
5. emit `draft_conflict_rules.json` payload

Design constraints:
- keep logic focused on `pattern/detail` only in v1
- do not mutate active rule files
- do not depend on web signals yet
- return structured errors for malformed input

- [ ] **Step 4: Add a small CLI entrypoint**

In `temu_y2_women/conflict_rule_feedback_cli.py`, support:

```text
derive --ledger --output
```

The command should write the staged draft payload and print a compact report with draft count and skipped-pair count.

- [ ] **Step 5: Run targeted derivation tests**

Run:

```bash
python -m unittest tests.test_conflict_rule_feedback_deriver -v
```

Expected:
- PASS
- draft output matches expected fixture

- [ ] **Step 6: Commit**

```bash
git add temu_y2_women/conflict_rule_feedback_deriver.py temu_y2_women/conflict_rule_feedback_cli.py tests/test_conflict_rule_feedback_deriver.py tests/fixtures/compatibility_rules
git commit -m "feat: derive conflict rule candidates from feedback"
```

---

### Task 4: Integration verification and handoff

**Files:**
- Modify if needed: `docs/superpowers/specs/2026-04-26-harden-ranking-and-constraints-design.md`
- Optional create: `docs/superpowers/specs/2026-04-27-evidence-backed-compatibility-rules-design.md`

- [ ] **Step 1: Run focused regression suites**

Run:

```bash
python -m unittest tests.test_compatibility_evaluator tests.test_compatibility_rule_promotion tests.test_conflict_rule_feedback_deriver -v
```

Expected:
- PASS

- [ ] **Step 2: Run broader concept-generation regression**

Run:

```bash
python -m unittest tests.test_composition_engine tests.test_orchestrator -v
```

Expected:
- PASS
- no change to current runtime weak/strong scoring semantics

- [ ] **Step 3: Run repository guardrails**

Run:

```bash
python -m unittest
python C:\Users\lxy\.codex\rules\hooks\validate_python_function_length.py .
```

Expected:
- full suite green
- function-length guardrail OK

- [ ] **Step 4: Record deferred dependency for Phase 4**

Document that signal-derived conflict candidates are intentionally deferred until the evidence-refresh change stabilizes:
- canonical signal bundle schema
- normalized signal output fields
- season / occasion / price-band enrichment fields

- [ ] **Step 5: Prepare merge / PR handoff**

Use precise staging, keep PR scope limited to:
- schema/runtime
- rule promotion workflow
- feedback-derived conflict candidates

Suggested commit sequence:
1. `feat: add evidence-backed compatibility rule schema`
2. `feat: add compatibility rule promotion workflow`
3. `feat: derive conflict rule candidates from feedback`

---

## Parallel execution map

### Worker A: schema/runtime
- Owns Task 1
- Must not edit promotion or feedback-deriver modules

### Worker B: rule review/promotion
- Owns Task 2
- Must not edit `temu_y2_women/compatibility_evaluator.py` except to consume stable public helpers if absolutely required

### Worker C: feedback-derived candidates
- Owns Task 3
- Must not mutate active-rule loading or promotion logic

### Deferred Worker D: signal-derived candidates
- Not part of this execution batch
- Starts only after canonical signal contract is stable in the evidence-refresh change

---

## Integration checkpoints

1. **Checkpoint A: schema/runtime merged locally**
   - v1/v2 rules load
   - runtime behavior unchanged

2. **Checkpoint B: rule promotion merged locally**
   - staged -> review -> active flow works
   - fail-before-mutation validated

3. **Checkpoint C: feedback-derived draft generation merged locally**
   - ledger -> draft conflict rules works
   - emitted suggestions carry evidence metrics

4. **Checkpoint D: full regression**
   - targeted suites pass
   - broader concept-generation path passes
   - repository guardrails pass

---

## Out of scope for this plan

- signal-derived conflict candidates
- dynamic runtime inference of weak/strong conflicts
- multi-slot global compatibility solving
- automatic promotion of conflict rules without review
