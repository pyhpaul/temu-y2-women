# Harden Ranking and Constraints Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce dress concept outputs where `pattern` and `detail` fight each other by validating explicit compatibility rules and applying them during bounded `pattern/detail` reranking.

**Architecture:** Add a file-backed compatibility rule set under `data/mvp/dress/`, centralize rule loading and pair evaluation in a dedicated `compatibility_evaluator` module, and keep the external request/result contract stable by applying compatibility penalties only inside `composition_engine` for the `pattern/detail` optional pair. Required slots and the other optional slots stay mostly greedy in v1; only `pattern/detail` gets local bounded search with strong-conflict rejection and weak-conflict penalties.

**Tech Stack:** Python 3 standard library, JSON data files, `unittest`, existing `GenerationError` and dataclass-based models.

---

## File Map

- Create: `data/mvp/dress/compatibility_rules.json`
  - Active compatibility rules for the curated `dress` evidence set.
- Create: `tests/fixtures/evidence/dress/invalid-compatibility-rules-unknown-value.json`
  - Invalid compatibility rule fixture that references a nonexistent active `detail` value.
- Create: `temu_y2_women/compatibility_evaluator.py`
  - Load and validate compatibility rules, expose compatibility dataclasses, and evaluate selected `pattern/detail` pairs.
- Create: `tests/test_compatibility_evaluator.py`
  - Unit tests for rule loading, strong conflict evaluation, weak conflict penalties, and explanation notes.
- Modify: `temu_y2_women/composition_engine.py`
  - Keep required-slot selection intact, add bounded `pattern/detail` search, consume compatibility penalties/notes, and keep function lengths under 60 lines.
- Modify: `tests/test_composition_engine.py`
  - Add regression tests for alternative selection, strong conflict avoidance, weak conflict note/score behavior, and must-have conflict failure.

---

### Task 1: Add compatibility rule data and loader validation

**Files:**
- Create: `data/mvp/dress/compatibility_rules.json`
- Create: `tests/fixtures/evidence/dress/invalid-compatibility-rules-unknown-value.json`
- Create: `tests/test_compatibility_evaluator.py`
- Create: `temu_y2_women/compatibility_evaluator.py`

- [ ] **Step 1: Write the failing loader tests**

Add these tests to `tests/test_compatibility_evaluator.py`:

```python
from pathlib import Path
import unittest


class CompatibilityRulesTest(unittest.TestCase):
    def test_load_compatibility_rules_accepts_valid_pattern_detail_rules(self) -> None:
        from temu_y2_women.compatibility_evaluator import load_compatibility_rules

        rules = load_compatibility_rules()

        self.assertTrue(rules)
        self.assertEqual(rules[0].left_slot, "pattern")
        self.assertEqual(rules[0].right_slot, "detail")
        self.assertIn(rules[0].severity, ("strong", "weak"))

    def test_reject_compatibility_rule_with_unknown_detail_value(self) -> None:
        from temu_y2_women.compatibility_evaluator import load_compatibility_rules
        from temu_y2_women.errors import GenerationError

        fixture_path = Path(
            "tests/fixtures/evidence/dress/invalid-compatibility-rules-unknown-value.json"
        )

        with self.assertRaises(GenerationError) as error_context:
            load_compatibility_rules(path=fixture_path)

        self.assertEqual(error_context.exception.code, "INVALID_EVIDENCE_STORE")
        self.assertEqual(error_context.exception.details["field"], "right_value")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
python -m unittest tests.test_compatibility_evaluator.CompatibilityRulesTest -v
```

Expected: FAIL with `ModuleNotFoundError` for `temu_y2_women.compatibility_evaluator`.

- [ ] **Step 3: Write the minimal loader implementation and fixtures**

Create `data/mvp/dress/compatibility_rules.json` with real active values from `elements.json`:

```json
{
  "schema_version": "mvp-v1",
  "rules": [
    {
      "left_slot": "pattern",
      "left_value": "floral print",
      "right_slot": "detail",
      "right_value": "smocked bodice",
      "severity": "weak",
      "penalty": 0.08,
      "reason": "pattern and detail both read busy in the current dress direction"
    }
  ]
}
```

Create `tests/fixtures/evidence/dress/invalid-compatibility-rules-unknown-value.json`:

```json
{
  "schema_version": "mvp-v1",
  "rules": [
    {
      "left_slot": "pattern",
      "left_value": "floral print",
      "right_slot": "detail",
      "right_value": "unknown-detail",
      "severity": "strong",
      "penalty": 0.0,
      "reason": "invalid fixture"
    }
  ]
}
```

Create `temu_y2_women/compatibility_evaluator.py` with the dataclass shell and loader:

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from temu_y2_women.errors import GenerationError
from temu_y2_women.evidence_repository import load_elements

_DEFAULT_COMPATIBILITY_RULES_PATH = Path("data/mvp/dress/compatibility_rules.json")
_DEFAULT_ELEMENTS_PATH = Path("data/mvp/dress/elements.json")


@dataclass(frozen=True, slots=True)
class CompatibilityRule:
    left_slot: str
    left_value: str
    right_slot: str
    right_value: str
    severity: str
    penalty: float
    reason: str


def load_compatibility_rules(
    path: Path = _DEFAULT_COMPATIBILITY_RULES_PATH,
    elements_path: Path = _DEFAULT_ELEMENTS_PATH,
) -> tuple[CompatibilityRule, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rules = payload.get("rules")
    if not isinstance(rules, list):
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message="compatibility rules must contain a 'rules' array",
            details={"path": str(path), "field": "rules"},
        )
    active_values = _active_values_by_slot(load_elements(elements_path))
    return tuple(_validate_rule(path, index, rule, active_values) for index, rule in enumerate(rules))


def _active_values_by_slot(elements: list[dict[str, Any]]) -> dict[str, set[str]]:
    values: dict[str, set[str]] = {}
    for element in elements:
        if element.get("status") != "active":
            continue
        slot = str(element["slot"]).strip().casefold()
        value = str(element["value"]).strip().casefold()
        values.setdefault(slot, set()).add(value)
    return values


def _validate_rule(
    path: Path,
    index: int,
    rule: Any,
    active_values: dict[str, set[str]],
) -> CompatibilityRule:
    if not isinstance(rule, dict):
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message="compatibility rule must be an object",
            details={"path": str(path), "index": index},
        )
    left_slot = str(rule["left_slot"]).strip().casefold()
    right_slot = str(rule["right_slot"]).strip().casefold()
    left_value = str(rule["left_value"]).strip().casefold()
    right_value = str(rule["right_value"]).strip().casefold()
    if left_slot != "pattern" or right_slot != "detail":
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message="compatibility rules must target pattern/detail pairs in v1",
            details={"path": str(path), "index": index, "field": "slot_pair"},
        )
    if left_value not in active_values.get(left_slot, set()):
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message="compatibility rule references unknown active element values",
            details={"path": str(path), "index": index, "field": "left_value", "value": left_value},
        )
    if right_value not in active_values.get(right_slot, set()):
        raise GenerationError(
            code="INVALID_EVIDENCE_STORE",
            message="compatibility rule references unknown active element values",
            details={"path": str(path), "index": index, "field": "right_value", "value": right_value},
        )
    return CompatibilityRule(
        left_slot=left_slot,
        left_value=left_value,
        right_slot=right_slot,
        right_value=right_value,
        severity=str(rule["severity"]).strip().casefold(),
        penalty=float(rule.get("penalty", 0.0)),
        reason=str(rule["reason"]).strip(),
    )
```

- [ ] **Step 4: Run the loader tests to verify they pass**

Run:

```bash
python -m unittest tests.test_compatibility_evaluator.CompatibilityRulesTest -v
```

Expected: PASS for both tests.

- [ ] **Step 5: Commit**

```bash
git add data/mvp/dress/compatibility_rules.json tests/fixtures/evidence/dress/invalid-compatibility-rules-unknown-value.json tests/test_compatibility_evaluator.py temu_y2_women/compatibility_evaluator.py
git commit -m "feat: add compatibility rule loader"
```

---

### Task 2: Add centralized compatibility evaluation

**Files:**
- Modify: `temu_y2_women/compatibility_evaluator.py`
- Modify: `tests/test_compatibility_evaluator.py`

- [ ] **Step 1: Write the failing evaluation tests**

Append these tests to `tests/test_compatibility_evaluator.py`:

```python
from temu_y2_women.models import CandidateElement


class CompatibilityEvaluationTest(unittest.TestCase):
    def test_evaluate_selection_returns_soft_conflict_penalty_and_note(self) -> None:
        from temu_y2_women.compatibility_evaluator import CompatibilityRule, evaluate_selection_compatibility

        selected = {
            "pattern": _candidate("dress-pattern-floral-001", "pattern", "floral print"),
            "detail": _candidate("dress-detail-smocked-bodice-001", "detail", "smocked bodice"),
        }
        rules = (
            CompatibilityRule(
                left_slot="pattern",
                left_value="floral print",
                right_slot="detail",
                right_value="smocked bodice",
                severity="weak",
                penalty=0.08,
                reason="busy pairing",
            ),
        )

        evaluation = evaluate_selection_compatibility(selected, rules)

        self.assertEqual(evaluation.compatibility_penalty, 0.08)
        self.assertEqual(evaluation.hard_conflicts, ())
        self.assertIn("style compatibility penalty applied: floral print + smocked bodice (0.08)", evaluation.compatibility_notes)

    def test_evaluate_selection_returns_hard_conflict(self) -> None:
        from temu_y2_women.compatibility_evaluator import CompatibilityRule, evaluate_selection_compatibility

        selected = {
            "pattern": _candidate("dress-pattern-floral-001", "pattern", "floral print"),
            "detail": _candidate("dress-detail-smocked-bodice-001", "detail", "smocked bodice"),
        }
        rules = (
            CompatibilityRule(
                left_slot="pattern",
                left_value="floral print",
                right_slot="detail",
                right_value="smocked bodice",
                severity="strong",
                penalty=0.0,
                reason="unusable pairing",
            ),
        )

        evaluation = evaluate_selection_compatibility(selected, rules)

        self.assertIn("floral print + smocked bodice", evaluation.hard_conflicts)
        self.assertEqual(evaluation.compatibility_penalty, 0.0)


def _candidate(element_id: str, slot: str, value: str) -> CandidateElement:
    return CandidateElement(
        element_id=element_id,
        category="dress",
        slot=slot,
        value=value,
        tags=(),
        base_score=0.8,
        effective_score=0.8,
        risk_flags=(),
        evidence_summary="fixture",
    )
```

- [ ] **Step 2: Run the new evaluation tests to verify they fail**

Run:

```bash
python -m unittest tests.test_compatibility_evaluator.CompatibilityEvaluationTest -v
```

Expected: FAIL with `ImportError` or `AttributeError` because `evaluate_selection_compatibility` does not exist yet.

- [ ] **Step 3: Implement the evaluation dataclass and evaluator**

Add this to `temu_y2_women/compatibility_evaluator.py`:

```python
from temu_y2_women.models import CandidateElement


@dataclass(frozen=True, slots=True)
class CompatibilityEvaluation:
    hard_conflicts: tuple[str, ...]
    soft_conflicts: tuple[str, ...]
    compatibility_penalty: float
    compatibility_notes: tuple[str, ...]


def evaluate_selection_compatibility(
    selected: dict[str, CandidateElement],
    rules: tuple[CompatibilityRule, ...],
) -> CompatibilityEvaluation:
    pattern = selected.get("pattern")
    detail = selected.get("detail")
    if pattern is None or detail is None:
        return CompatibilityEvaluation((), (), 0.0, ())
    hard_conflicts: list[str] = []
    soft_conflicts: list[str] = []
    notes: list[str] = []
    penalty = 0.0
    for rule in rules:
        if not _rule_matches(rule, pattern, detail):
            continue
        pair_label = f"{pattern.value} + {detail.value}"
        if rule.severity == "strong":
            hard_conflicts.append(pair_label)
            notes.append(f"style conflict avoided: {pair_label}")
            continue
        soft_conflicts.append(pair_label)
        penalty += rule.penalty
        notes.append(f"style compatibility penalty applied: {pair_label} ({rule.penalty:.2f})")
    return CompatibilityEvaluation(tuple(hard_conflicts), tuple(soft_conflicts), round(penalty, 4), tuple(notes))


def _rule_matches(
    rule: CompatibilityRule,
    pattern: CandidateElement,
    detail: CandidateElement,
) -> bool:
    return (
        pattern.slot == rule.left_slot
        and pattern.value.strip().casefold() == rule.left_value
        and detail.slot == rule.right_slot
        and detail.value.strip().casefold() == rule.right_value
    )
```

- [ ] **Step 4: Run the evaluation tests to verify they pass**

Run:

```bash
python -m unittest tests.test_compatibility_evaluator.CompatibilityEvaluationTest -v
```

Expected: PASS for both strong and weak conflict cases.

- [ ] **Step 5: Commit**

```bash
git add tests/test_compatibility_evaluator.py temu_y2_women/compatibility_evaluator.py
git commit -m "feat: add compatibility evaluator"
```

---

### Task 3: Rerank pattern/detail combinations inside composition

**Files:**
- Modify: `temu_y2_women/composition_engine.py`
- Modify: `tests/test_composition_engine.py`

- [ ] **Step 1: Write the failing composition tests for alternative selection and hard-conflict avoidance**

Add these tests to `tests/test_composition_engine.py`:

```python
from temu_y2_women.compatibility_evaluator import CompatibilityRule


def test_weak_conflict_prefers_more_compatible_detail_alternative(self) -> None:
    from temu_y2_women.composition_engine import compose_concept

    request = _request()
    candidates = {
        "silhouette": [_candidate("dress-silhouette-a-line-001", "silhouette", "a-line", 0.91, ("summer",))],
        "fabric": [_candidate("dress-fabric-cotton-poplin-001", "fabric", "cotton poplin", 0.89, ("lightweight",))],
        "pattern": [_candidate("dress-pattern-floral-001", "pattern", "floral print", 0.83, ("floral",))],
        "detail": [
            _candidate("dress-detail-smocked-bodice-001", "detail", "smocked bodice", 0.86, ("smocked",)),
            _candidate("dress-detail-waist-tie-001", "detail", "waist tie", 0.80, ("minimal",)),
        ],
    }
    rules = (
        CompatibilityRule(
            left_slot="pattern",
            left_value="floral print",
            right_slot="detail",
            right_value="smocked bodice",
            severity="weak",
            penalty=0.12,
            reason="busy pairing",
        ),
    )

    concept = compose_concept(request, candidates, compatibility_rules=rules)

    self.assertEqual(concept.selected_elements["detail"].value, "waist tie")


def test_strong_conflict_omits_detail_when_no_valid_alternative_exists(self) -> None:
    from temu_y2_women.composition_engine import compose_concept

    request = _request()
    candidates = {
        "silhouette": [_candidate("dress-silhouette-a-line-001", "silhouette", "a-line", 0.91, ("summer",))],
        "fabric": [_candidate("dress-fabric-cotton-poplin-001", "fabric", "cotton poplin", 0.89, ("lightweight",))],
        "pattern": [_candidate("dress-pattern-floral-001", "pattern", "floral print", 0.83, ("floral",))],
        "detail": [_candidate("dress-detail-smocked-bodice-001", "detail", "smocked bodice", 0.86, ("smocked",))],
    }
    rules = (
        CompatibilityRule(
            left_slot="pattern",
            left_value="floral print",
            right_slot="detail",
            right_value="smocked bodice",
            severity="strong",
            penalty=0.0,
            reason="unusable pairing",
        ),
    )

    concept = compose_concept(request, candidates, compatibility_rules=rules)

    self.assertNotIn("detail", concept.selected_elements)
```

- [ ] **Step 2: Run the composition tests to verify they fail**

Run:

```bash
python -m unittest tests.test_composition_engine.CompositionEngineTest -v
```

Expected: FAIL because `compose_concept()` does not accept `compatibility_rules` and still greedily picks `smocked bodice`.

- [ ] **Step 3: Implement bounded pattern/detail search in `composition_engine.py`**

Refactor `temu_y2_women/composition_engine.py` toward these helpers:

```python
from itertools import product

from temu_y2_women.compatibility_evaluator import CompatibilityRule, CompatibilityEvaluation, evaluate_selection_compatibility, load_compatibility_rules

_OPTIONAL_TOP_K = 3


def compose_concept(
    request: NormalizedRequest,
    candidates_by_slot: dict[str, list[dict[str, Any]]],
    compatibility_rules: tuple[CompatibilityRule, ...] | None = None,
) -> ComposedConcept:
    parsed_candidates = {
        slot: [_parse_candidate(candidate) for candidate in candidates]
        for slot, candidates in candidates_by_slot.items()
    }
    selected = _select_required_slots(parsed_candidates)
    selected.update(_select_standard_optional_slots(parsed_candidates))
    rules = compatibility_rules if compatibility_rules is not None else load_compatibility_rules()
    pattern_detail_result = _select_pattern_detail_pair(parsed_candidates, selected, rules)
    selected.update(pattern_detail_result["selected"])
    constraint_notes = list(_must_have_notes(request, selected))
    constraint_notes.extend(pattern_detail_result["evaluation"].compatibility_notes)
    concept_score = _concept_score(selected, pattern_detail_result["evaluation"])
    return _build_concept(request, selected, concept_score, constraint_notes)


def _select_pattern_detail_pair(
    parsed_candidates: dict[str, list[CandidateElement]],
    selected: dict[str, CandidateElement],
    compatibility_rules: tuple[CompatibilityRule, ...],
) -> dict[str, Any]:
    pattern_options = [None, *_top_candidates(parsed_candidates.get("pattern", []))]
    detail_options = [None, *_top_candidates(parsed_candidates.get("detail", []))]
    best_result: dict[str, Any] | None = None
    for pattern, detail in product(pattern_options, detail_options):
        pair_selected = dict(selected)
        if pattern is not None:
            pair_selected["pattern"] = pattern
        if detail is not None:
            pair_selected["detail"] = detail
        evaluation = evaluate_selection_compatibility(pair_selected, compatibility_rules)
        if evaluation.hard_conflicts:
            continue
        result = {
            "selected": {k: v for k, v in {"pattern": pattern, "detail": detail}.items() if v is not None},
            "evaluation": evaluation,
            "score": _selection_score(pair_selected, evaluation.compatibility_penalty),
        }
        if best_result is None or result["score"] > best_result["score"]:
            best_result = result
    return best_result or {"selected": {}, "evaluation": CompatibilityEvaluation((), (), 0.0, ()), "score": 0.0}
```

Use additional helpers to keep every function under 60 lines:

```python
def _select_required_slots(parsed_candidates: dict[str, list[CandidateElement]]) -> dict[str, CandidateElement]:
    selected: dict[str, CandidateElement] = {}
    for slot in _REQUIRED_SLOTS:
        candidates = parsed_candidates.get(slot, [])
        if not candidates:
            raise GenerationError(
                code="INCOMPLETE_CONCEPT",
                message=f"missing required slot: {slot}",
                details={"slot": slot},
            )
        selected[slot] = _top_candidate(candidates)
    return selected

def _select_standard_optional_slots(parsed_candidates: dict[str, list[CandidateElement]]) -> dict[str, CandidateElement]:
    selected: dict[str, CandidateElement] = {}
    for slot in ("neckline", "sleeve"):
        candidates = parsed_candidates.get(slot, [])
        if candidates:
            selected[slot] = _top_candidate(candidates)
    return selected

def _top_candidates(candidates: list[CandidateElement]) -> list[CandidateElement]:
    return sorted(candidates, key=lambda candidate: (candidate.effective_score, candidate.element_id), reverse=True)[:_OPTIONAL_TOP_K]

def _selection_score(
    selected: dict[str, CandidateElement],
    compatibility_penalty: float,
) -> float:
    return sum(candidate.effective_score for candidate in selected.values()) - compatibility_penalty
```

- [ ] **Step 4: Run the composition tests to verify they pass**

Run:

```bash
python -m unittest tests.test_composition_engine.CompositionEngineTest -v
```

Expected: PASS for the new alternative-selection and hard-conflict tests plus the existing tests.

- [ ] **Step 5: Commit**

```bash
git add temu_y2_women/composition_engine.py tests/test_composition_engine.py
git commit -m "feat: rerank pattern detail combinations"
```

---

### Task 4: Add weak-conflict score/note behavior and must-have failure coverage

**Files:**
- Modify: `temu_y2_women/composition_engine.py`
- Modify: `tests/test_composition_engine.py`

- [ ] **Step 1: Write the failing tests for note/score propagation and must-have failure**

Append these tests to `tests/test_composition_engine.py`:

```python
def test_weak_conflict_keeps_pair_when_no_better_option_exists_and_records_penalty(self) -> None:
    from temu_y2_women.composition_engine import compose_concept

    request = _request()
    candidates = {
        "silhouette": [_candidate("dress-silhouette-a-line-001", "silhouette", "a-line", 0.91, ("summer",))],
        "fabric": [_candidate("dress-fabric-cotton-poplin-001", "fabric", "cotton poplin", 0.89, ("lightweight",))],
        "pattern": [_candidate("dress-pattern-floral-001", "pattern", "floral print", 0.83, ("floral",))],
        "detail": [_candidate("dress-detail-smocked-bodice-001", "detail", "smocked bodice", 0.81, ("smocked",))],
    }
    rules = (
        CompatibilityRule(
            left_slot="pattern",
            left_value="floral print",
            right_slot="detail",
            right_value="smocked bodice",
            severity="weak",
            penalty=0.03,
            reason="busy pairing",
        ),
    )

    concept = compose_concept(request, candidates, compatibility_rules=rules)

    self.assertEqual(concept.selected_elements["detail"].value, "smocked bodice")
    self.assertIn(
        "style compatibility penalty applied: floral print + smocked bodice (0.03)",
        concept.constraint_notes,
    )
    self.assertEqual(concept.concept_score, round((0.91 + 0.89 + 0.83 + 0.81 - 0.03) / 4, 4))


def test_strong_conflict_causes_constraint_conflict_when_must_have_requires_dropped_detail(self) -> None:
    from temu_y2_women.composition_engine import compose_concept
    from temu_y2_women.errors import GenerationError

    request = _request(must_have_tags=("smocked",))
    candidates = {
        "silhouette": [_candidate("dress-silhouette-a-line-001", "silhouette", "a-line", 0.91, ("summer",))],
        "fabric": [_candidate("dress-fabric-cotton-poplin-001", "fabric", "cotton poplin", 0.89, ("lightweight",))],
        "pattern": [_candidate("dress-pattern-floral-001", "pattern", "floral print", 0.83, ("floral",))],
        "detail": [_candidate("dress-detail-smocked-bodice-001", "detail", "smocked bodice", 0.81, ("smocked",))],
    }
    rules = (
        CompatibilityRule(
            left_slot="pattern",
            left_value="floral print",
            right_slot="detail",
            right_value="smocked bodice",
            severity="strong",
            penalty=0.0,
            reason="unusable pairing",
        ),
    )

    with self.assertRaises(GenerationError) as error_context:
        compose_concept(request, candidates, compatibility_rules=rules)

    self.assertEqual(error_context.exception.code, "CONSTRAINT_CONFLICT")
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run:

```bash
python -m unittest tests.test_composition_engine.CompositionEngineTest.test_weak_conflict_keeps_pair_when_no_better_option_exists_and_records_penalty tests.test_composition_engine.CompositionEngineTest.test_strong_conflict_causes_constraint_conflict_when_must_have_requires_dropped_detail -v
```

Expected: FAIL because `constraint_notes` and `concept_score` still do not reflect the compatibility penalty path exactly.

- [ ] **Step 3: Complete the scoring and note propagation implementation**

Tighten `temu_y2_women/composition_engine.py` with these helpers:

```python
def _concept_score(
    selected: dict[str, CandidateElement],
    evaluation: CompatibilityEvaluation,
) -> float:
    total = sum(candidate.effective_score for candidate in selected.values()) - evaluation.compatibility_penalty
    return round(total / len(selected), 4)


def _build_concept(
    request: NormalizedRequest,
    selected: dict[str, CandidateElement],
    concept_score: float,
    constraint_notes: list[str],
) -> ComposedConcept:
    return ComposedConcept(
        category=request.category,
        concept_score=concept_score,
        selected_elements={
            slot: ComposedElement(element_id=candidate.element_id, value=candidate.value)
            for slot, candidate in selected.items()
        },
        style_summary=_style_summary(selected),
        constraint_notes=tuple(constraint_notes),
    )
```

Keep `_must_have_notes()` unchanged so it naturally raises `CONSTRAINT_CONFLICT` after a strong conflict forces the incompatible detail out of the selected set.

- [ ] **Step 4: Run the focused composition tests to verify they pass**

Run:

```bash
python -m unittest tests.test_composition_engine.CompositionEngineTest -v
```

Expected: PASS for the new score/note tests and the existing composition cases.

- [ ] **Step 5: Commit**

```bash
git add temu_y2_women/composition_engine.py tests/test_composition_engine.py
git commit -m "feat: explain and score compatibility penalties"
```

---

### Task 5: Run regression and enforce repo guardrails

**Files:**
- Modify: none expected
- Test: `tests/test_compatibility_evaluator.py`
- Test: `tests/test_composition_engine.py`
- Test: `tests/test_orchestrator.py`

- [ ] **Step 1: Run the focused compatibility and composition suites**

Run:

```bash
python -m unittest tests.test_compatibility_evaluator -v
python -m unittest tests.test_composition_engine -v
```

Expected: PASS.

- [ ] **Step 2: Run the end-to-end orchestrator regression**

Run:

```bash
python -m unittest tests.test_orchestrator -v
```

Expected: PASS with no request/result contract changes.

- [ ] **Step 3: Run the full repository regression**

Run:

```bash
python -m unittest discover -s tests -t .
```

Expected: all tests PASS.

- [ ] **Step 4: Run the Python function-length hook**

Run:

```bash
python C:\Users\lxy\.codex\rules\hooks\validate_python_function_length.py .
```

Expected: `OK`.

- [ ] **Step 5: Commit the final hardening pass**

```bash
git add data/mvp/dress/compatibility_rules.json tests/fixtures/evidence/dress/invalid-compatibility-rules-unknown-value.json temu_y2_women/compatibility_evaluator.py temu_y2_women/composition_engine.py tests/test_compatibility_evaluator.py tests/test_composition_engine.py
git commit -m "feat: harden pattern detail ranking constraints"
```
