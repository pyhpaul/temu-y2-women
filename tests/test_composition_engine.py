from datetime import date
import unittest

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
