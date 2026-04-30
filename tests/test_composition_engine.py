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

    def test_prefers_available_surface_candidate_that_satisfies_must_have_tags(self) -> None:
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
                _candidate("dress-pattern-polka-dot-001", "pattern", "polka dot", 0.92, ("polka-dot",)),
                _candidate("dress-pattern-floral-001", "pattern", "floral print", 0.65, ("floral", "vacation")),
            ],
        }

        concept = compose_concept(request, candidates)

        self.assertEqual(concept.selected_elements["pattern"].value, "floral print")
        self.assertIn("must_have_tags satisfied: floral", concept.constraint_notes)

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
        self.assertIn(
            "style conflict avoided: floral print + smocked bodice",
            concept.constraint_notes,
        )

    def test_keeps_weak_conflict_pair_and_applies_penalty_when_no_better_option(self) -> None:
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
                _candidate("dress-pattern-floral-print-001", "pattern", "floral print", 0.83, ("vacation",)),
            ],
            "detail": [
                _candidate("dress-detail-smocked-bodice-001", "detail", "smocked bodice", 0.81, ("romantic",)),
            ],
        }
        rules = (
            CompatibilityRule("pattern", "floral print", "detail", "smocked bodice", "weak", 0.03, "fixture"),
        )

        concept = compose_concept(request, candidates, compatibility_rules=rules)

        self.assertEqual(concept.selected_elements["pattern"].value, "floral print")
        self.assertEqual(concept.selected_elements["detail"].value, "smocked bodice")
        self.assertIn(
            "style compatibility penalty applied: floral print + smocked bodice (0.03)",
            concept.constraint_notes,
        )
        self.assertEqual(concept.concept_score, round((0.91 + 0.89 + 0.83 + 0.81 - 0.03) / 4, 4))

    def test_fail_when_strong_conflict_drops_must_have_detail(self) -> None:
        from temu_y2_women.compatibility_evaluator import CompatibilityRule
        from temu_y2_women.composition_engine import compose_concept
        from temu_y2_women.errors import GenerationError

        request = _request(must_have_tags=("smocked",))
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
                _candidate("dress-detail-smocked-bodice-001", "detail", "smocked bodice", 0.83, ("romantic", "smocked")),
            ],
        }
        rules = (
            CompatibilityRule("pattern", "floral print", "detail", "smocked bodice", "strong", 0.0, "fixture"),
        )

        with self.assertRaises(GenerationError) as error_context:
            compose_concept(request, candidates, compatibility_rules=rules)

        self.assertEqual(error_context.exception.code, "CONSTRAINT_CONFLICT")

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

    def test_selects_new_objective_slots_for_a_line_vacation_concept(self) -> None:
        from temu_y2_women.composition_engine import compose_concept

        request = _request()
        candidates = {
            "silhouette": [_candidate("dress-silhouette-a-line-001", "silhouette", "a-line", 0.91, ("summer",))],
            "fabric": [_candidate("dress-fabric-cotton-poplin-001", "fabric", "cotton poplin", 0.89, ("lightweight",))],
            "dress_length": [
                _candidate("dress-length-mini-001", "dress_length", "mini", 0.81, ("mini",)),
                _candidate("dress-length-midi-001", "dress_length", "midi", 0.78, ("midi",)),
            ],
            "waistline": [_candidate("dress-waistline-drop-waist-001", "waistline", "drop waist", 0.82, ("drop-waist",))],
            "color_family": [_candidate("dress-color-family-white-001", "color_family", "white", 0.8, ("white",))],
            "opacity_level": [_candidate("dress-opacity-level-sheer-001", "opacity_level", "sheer", 0.74, ("sheer",))],
            "pattern": [_candidate("dress-pattern-polka-dot-001", "pattern", "polka dot", 0.77, ("polka-dot",))],
            "print_scale": [_candidate("dress-print-scale-micro-print-001", "print_scale", "micro print", 0.75, ("micro-print",))],
        }

        concept = compose_concept(request, candidates)

        self.assertEqual(concept.selected_elements["dress_length"].value, "mini")
        self.assertEqual(concept.selected_elements["waistline"].value, "drop waist")
        self.assertEqual(concept.selected_elements["color_family"].value, "white")
        self.assertEqual(concept.selected_elements["opacity_level"].value, "sheer")
        self.assertEqual(concept.selected_elements["pattern"].value, "polka dot")
        self.assertEqual(concept.selected_elements["print_scale"].value, "micro print")

    def test_omits_print_scale_when_pattern_is_missing(self) -> None:
        from temu_y2_women.composition_engine import compose_concept

        request = _request()
        candidates = {
            "silhouette": [_candidate("dress-silhouette-a-line-001", "silhouette", "a-line", 0.91, ("summer",))],
            "fabric": [_candidate("dress-fabric-cotton-poplin-001", "fabric", "cotton poplin", 0.89, ("lightweight",))],
            "print_scale": [_candidate("dress-print-scale-micro-print-001", "print_scale", "micro print", 0.75, ("micro-print",))],
        }

        concept = compose_concept(request, candidates)

        self.assertNotIn("print_scale", concept.selected_elements)

    def test_prefers_natural_waist_when_drop_waist_conflicts_with_bodycon(self) -> None:
        from temu_y2_women.composition_engine import compose_concept

        request = _request()
        candidates = {
            "silhouette": [_candidate("dress-silhouette-bodycon-001", "silhouette", "bodycon", 0.9, ("bodycon",))],
            "fabric": [_candidate("dress-fabric-cotton-poplin-001", "fabric", "cotton poplin", 0.89, ("lightweight",))],
            "waistline": [
                _candidate("dress-waistline-drop-waist-001", "waistline", "drop waist", 0.84, ("drop-waist",)),
                _candidate("dress-waistline-natural-waist-001", "waistline", "natural waist", 0.74, ("feminine",)),
            ],
        }

        concept = compose_concept(request, candidates)

        self.assertEqual(concept.selected_elements["waistline"].value, "natural waist")
        self.assertIn("structural conflict avoided: bodycon + drop waist", concept.constraint_notes)


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
