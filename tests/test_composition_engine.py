from datetime import date
import unittest
from unittest.mock import patch

from temu_y2_women.models import NormalizedRequest


class CompositionEngineTest(unittest.TestCase):
    def test_build_minimum_valid_concept(self) -> None:
        from temu_y2_women.composition_engine import compose_concept

        request = _request(must_have_tags=("floral",))
        candidates = {
            "silhouette": [
                _candidate("dress-silhouette-a-line-001", "silhouette", "a-line", 0.91, ("summer",)),
            ],
            "fabric": [
                _candidate("dress-fabric-cotton-poplin-001", "fabric", "cotton poplin", 0.89, ("lightweight",)),
            ],
            "pattern": [
                _candidate("dress-pattern-floral-001", "pattern", "floral", 0.82, ("floral", "vacation")),
            ],
        }

        concept = compose_concept(request, candidates)

        self.assertEqual(concept.category, "dress")
        self.assertEqual(concept.selected_elements["silhouette"].value, "a-line")
        self.assertEqual(concept.selected_elements["fabric"].value, "cotton poplin")
        self.assertIn("must_have_tags satisfied: floral", concept.constraint_notes)

    def test_fail_when_must_have_tags_cannot_be_satisfied(self) -> None:
        from temu_y2_women.composition_engine import compose_concept
        from temu_y2_women.errors import GenerationError

        request = _request(must_have_tags=("velvet",))
        candidates = {
            "silhouette": [
                _candidate("dress-silhouette-a-line-001", "silhouette", "a-line", 0.91, ("summer",)),
            ],
            "fabric": [
                _candidate("dress-fabric-cotton-poplin-001", "fabric", "cotton poplin", 0.89, ("lightweight",)),
            ],
        }

        with self.assertRaises(GenerationError) as error_context:
            compose_concept(request, candidates)

        self.assertEqual(error_context.exception.code, "CONSTRAINT_CONFLICT")

    def test_fail_when_required_slot_is_missing(self) -> None:
        from temu_y2_women.composition_engine import compose_concept
        from temu_y2_women.errors import GenerationError

        request = _request()
        candidates = {
            "silhouette": [
                _candidate("dress-silhouette-a-line-001", "silhouette", "a-line", 0.91, ("summer",)),
            ]
        }

        with self.assertRaises(GenerationError) as error_context:
            compose_concept(request, candidates)

        self.assertEqual(error_context.exception.code, "INCOMPLETE_CONCEPT")

    def test_prefers_alternative_detail_when_top_detail_has_weak_conflict(self) -> None:
        from temu_y2_women.compatibility_evaluator import CompatibilityRule
        from temu_y2_women.composition_engine import compose_concept

        request = _request()
        candidates = {
            "silhouette": [
                _candidate("dress-silhouette-a-line-001", "silhouette", "a-line", 0.91, ("summer",)),
            ],
            "fabric": [
                _candidate("dress-fabric-cotton-poplin-001", "fabric", "cotton poplin", 0.89, ("lightweight",)),
            ],
            "pattern": [
                _candidate("dress-pattern-floral-print-001", "pattern", "floral print", 0.84, ("vacation",)),
            ],
            "detail": [
                _candidate("dress-detail-smocked-bodice-001", "detail", "smocked bodice", 0.83, ("romantic",)),
                _candidate("dress-detail-waist-tie-001", "detail", "waist tie", 0.74, ("defined-waist",)),
            ],
        }
        rules = (
            CompatibilityRule("pattern", "floral print", "detail", "smocked bodice", "weak", 0.12, "fixture"),
        )

        concept = compose_concept(request, candidates, compatibility_rules=rules)

        self.assertEqual(concept.selected_elements["pattern"].value, "floral print")
        self.assertEqual(concept.selected_elements["detail"].value, "waist tie")

    def test_omits_detail_when_only_available_detail_has_strong_conflict(self) -> None:
        from temu_y2_women.compatibility_evaluator import CompatibilityRule
        from temu_y2_women.composition_engine import compose_concept

        request = _request()
        candidates = {
            "silhouette": [
                _candidate("dress-silhouette-a-line-001", "silhouette", "a-line", 0.91, ("summer",)),
            ],
            "fabric": [
                _candidate("dress-fabric-cotton-poplin-001", "fabric", "cotton poplin", 0.89, ("lightweight",)),
            ],
            "pattern": [
                _candidate("dress-pattern-floral-print-001", "pattern", "floral print", 0.84, ("vacation",)),
            ],
            "detail": [
                _candidate("dress-detail-smocked-bodice-001", "detail", "smocked bodice", 0.83, ("romantic",)),
            ],
        }
        rules = (
            CompatibilityRule("pattern", "floral print", "detail", "smocked bodice", "strong", 0.0, "fixture"),
        )

        concept = compose_concept(request, candidates, compatibility_rules=rules)

        self.assertEqual(concept.selected_elements["pattern"].value, "floral print")
        self.assertNotIn("detail", concept.selected_elements)

    def test_loads_default_compatibility_rules_when_not_provided(self) -> None:
        from temu_y2_women.compatibility_evaluator import CompatibilityRule
        from temu_y2_women.composition_engine import compose_concept

        request = _request()
        candidates = _pattern_detail_candidates()
        rules = [
            CompatibilityRule("pattern", "floral print", "detail", "smocked bodice", "weak", 0.12, "fixture"),
        ]

        with patch("temu_y2_women.composition_engine.load_compatibility_rules", return_value=rules) as load_rules:
            concept = compose_concept(request, candidates)

        load_rules.assert_called_once_with()
        self.assertEqual(concept.selected_elements["detail"].value, "waist tie")

    def test_explicit_compatibility_rules_override_default_loader(self) -> None:
        from temu_y2_women.compatibility_evaluator import CompatibilityRule
        from temu_y2_women.composition_engine import compose_concept

        request = _request()
        candidates = _pattern_detail_candidates()
        explicit_rules = (
            CompatibilityRule("pattern", "floral print", "detail", "smocked bodice", "weak", 0.12, "fixture"),
        )
        default_rules = [
            CompatibilityRule("pattern", "floral print", "detail", "waist tie", "strong", 0.0, "fixture"),
        ]

        with patch("temu_y2_women.composition_engine.load_compatibility_rules", return_value=default_rules) as load_rules:
            concept = compose_concept(request, candidates, compatibility_rules=explicit_rules)

        load_rules.assert_not_called()
        self.assertEqual(concept.selected_elements["detail"].value, "waist tie")


def _request(
    must_have_tags: tuple[str, ...] = (),
    ) -> NormalizedRequest:
    return NormalizedRequest(
        category="dress",
        target_market="US",
        target_launch_date=date(2026, 6, 15),
        mode="A",
        price_band=None,
        occasion_tags=("vacation",),
        must_have_tags=must_have_tags,
        avoid_tags=(),
    )


def _pattern_detail_candidates() -> dict[str, list[dict[str, object]]]:
    return {
        "silhouette": [
            _candidate("dress-silhouette-a-line-001", "silhouette", "a-line", 0.91, ("summer",)),
        ],
        "fabric": [
            _candidate("dress-fabric-cotton-poplin-001", "fabric", "cotton poplin", 0.89, ("lightweight",)),
        ],
        "pattern": [
            _candidate("dress-pattern-floral-print-001", "pattern", "floral print", 0.84, ("vacation",)),
        ],
        "detail": [
            _candidate("dress-detail-smocked-bodice-001", "detail", "smocked bodice", 0.83, ("romantic",)),
            _candidate("dress-detail-waist-tie-001", "detail", "waist tie", 0.74, ("defined-waist",)),
        ],
    }


def _candidate(
    element_id: str,
    slot: str,
    value: str,
    effective_score: float,
    tags: tuple[str, ...],
) -> dict[str, object]:
    return {
        "element_id": element_id,
        "category": "dress",
        "slot": slot,
        "value": value,
        "tags": list(tags),
        "base_score": effective_score,
        "effective_score": effective_score,
        "risk_flags": [],
        "evidence_summary": "fixture",
    }
